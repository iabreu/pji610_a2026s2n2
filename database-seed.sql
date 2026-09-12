-- Seed: dados de teste para desenvolvimento do frontend
--
-- Gera 24 horas de leituras (uma a cada 5 minutos) para cada dispositivo ativo,
-- com curva de temperatura realista e alguns spikes fora dos limites para popular alertas.
--
-- Pré-requisito: execute database-schema.sql primeiro.

-- Limpar leituras existentes (CASCADE remove alertas associados também)
TRUNCATE pji610.leituras CASCADE;

-- Gerar 24h de leituras a cada 5 minutos para cada dispositivo ativo
DO $$
DECLARE
    v_dispositivo  RECORD;
    v_timestamp    TIMESTAMPTZ;
    v_temperatura  NUMERIC;
    v_umidade      NUMERIC;
    v_hora_do_dia  INTEGER;
BEGIN
    FOR v_dispositivo IN SELECT id, nome FROM pji610.dispositivos WHERE ativo LOOP
        v_timestamp := NOW() - INTERVAL '24 hours';

        WHILE v_timestamp <= NOW() LOOP
            v_hora_do_dia := EXTRACT(HOUR FROM v_timestamp);

            -- Curva diária: pico ~18h, mínimo ~6h, base 22°C +/- 6°C, ruído +/- 1°C
            v_temperatura := 22 + 6 * SIN((v_hora_do_dia - 6) * PI() / 12)
                                + (RANDOM() - 0.5) * 2;

            -- Umidade: ~50-75%, anti-correlacionada com temperatura
            v_umidade     := 60 + 10 * SIN((v_hora_do_dia - 18) * PI() / 12)
                                + (RANDOM() - 0.5) * 5;

            -- ~2% das leituras: spike de temperatura para gerar alertas
            IF RANDOM() < 0.02 THEN
                v_temperatura := v_temperatura + 8;
            END IF;

            -- ~1% das leituras: queda de umidade para gerar alerta
            IF RANDOM() < 0.01 THEN
                v_umidade := v_umidade - 35;
            END IF;

            INSERT INTO pji610.leituras (
                dispositivo_id, temperatura, umidade,
                amostras, descartadas, desvio_temperatura, desvio_umidade,
                registrado_em
            )
            VALUES (v_dispositivo.id,
                    ROUND(v_temperatura::NUMERIC, 2),
                    ROUND(GREATEST(LEAST(v_umidade, 100), 0)::NUMERIC, 2),
                    6,
                    CASE WHEN RANDOM() < 0.05 THEN 1 ELSE 0 END,
                    ROUND((RANDOM() * 0.4)::NUMERIC, 3),
                    ROUND((RANDOM() * 1.2)::NUMERIC, 3),
                    v_timestamp);

            v_timestamp := v_timestamp + INTERVAL '5 minutes';
        END LOOP;
    END LOOP;
END $$;

-- Calcular o baseline inicial de cada dispositivo sobre os dados gerados
DO $$
DECLARE
    v_id UUID;
BEGIN
    FOR v_id IN SELECT id FROM pji610.dispositivos WHERE ativo LOOP
        PERFORM pji610.fn_recalcular_baseline(v_id);
    END LOOP;
END $$;

-- Resumo das leituras geradas
SELECT
    d.nome,
    d.localizacao,
    COUNT(l.id)                              AS total_leituras,
    MIN(l.registrado_em)                     AS primeira_leitura,
    MAX(l.registrado_em)                     AS ultima_leitura,
    ROUND(AVG(l.temperatura)::NUMERIC, 2)    AS temperatura_media,
    ROUND(MIN(l.temperatura)::NUMERIC, 2)    AS temperatura_min,
    ROUND(MAX(l.temperatura)::NUMERIC, 2)    AS temperatura_max,
    ROUND(AVG(l.umidade)::NUMERIC, 2)        AS umidade_media
FROM pji610.dispositivos d
LEFT JOIN pji610.leituras l ON l.dispositivo_id = d.id
GROUP BY d.id, d.nome, d.localizacao
ORDER BY d.nome;

-- Alertas gerados pelo trigger
SELECT
    d.nome,
    a.metodo,
    a.tipo,
    COUNT(*) AS quantidade
FROM pji610.dispositivos d
JOIN pji610.alertas a ON a.dispositivo_id = d.id
GROUP BY d.id, d.nome, a.metodo, a.tipo
ORDER BY d.nome, a.metodo, a.tipo;
