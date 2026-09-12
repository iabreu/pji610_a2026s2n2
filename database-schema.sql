-- Schema do banco de dados (Supabase / PostgreSQL)
-- Executar no SQL Editor do Supabase.
-- Depois, expor o schema em Settings > API > Exposed schemas.

CREATE SCHEMA IF NOT EXISTS pji610;

DROP VIEW  IF EXISTS pji610.vw_leituras_analise    CASCADE;
DROP VIEW  IF EXISTS pji610.vw_dispositivos_status CASCADE;
DROP TABLE IF EXISTS pji610.alertas                CASCADE;
DROP TABLE IF EXISTS pji610.baselines              CASCADE;
DROP TABLE IF EXISTS pji610.leituras               CASCADE;
DROP TABLE IF EXISTS pji610.dispositivos           CASCADE;

CREATE TABLE pji610.dispositivos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome            TEXT NOT NULL,
    localizacao     TEXT NOT NULL,
    api_key         TEXT NOT NULL UNIQUE,

    temperatura_min NUMERIC(5,2) NOT NULL DEFAULT 18.0,
    temperatura_max NUMERIC(5,2) NOT NULL DEFAULT 30.0,
    umidade_min     NUMERIC(5,2) NOT NULL DEFAULT 30.0,
    umidade_max     NUMERIC(5,2) NOT NULL DEFAULT 70.0,

    z_limite                NUMERIC(4,2) NOT NULL DEFAULT 3.0,
    janela_baseline_minutos INTEGER      NOT NULL DEFAULT 180,

    intervalo_offline_segundos INTEGER NOT NULL DEFAULT 120,

    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_temperatura_limites CHECK (temperatura_min < temperatura_max),
    CONSTRAINT chk_umidade_limites     CHECK (umidade_min     < umidade_max),
    CONSTRAINT chk_z_limite            CHECK (z_limite BETWEEN 1.0 AND 10.0),
    CONSTRAINT chk_janela_baseline     CHECK (janela_baseline_minutos BETWEEN 10 AND 10080)
);

CREATE INDEX idx_dispositivos_api_key ON pji610.dispositivos(api_key);
CREATE INDEX idx_dispositivos_ativo   ON pji610.dispositivos(ativo) WHERE ativo = TRUE;

CREATE TABLE pji610.leituras (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispositivo_id  UUID NOT NULL REFERENCES pji610.dispositivos(id) ON DELETE CASCADE,
    temperatura     NUMERIC(5,2) NOT NULL,
    umidade         NUMERIC(5,2) NOT NULL,

    amostras            INTEGER      NOT NULL DEFAULT 1,
    descartadas         INTEGER      NOT NULL DEFAULT 0,
    desvio_temperatura  NUMERIC(6,3),
    desvio_umidade      NUMERIC(6,3),

    registrado_em   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_temperatura_valida CHECK (temperatura BETWEEN -50 AND 100),
    CONSTRAINT chk_umidade_valida     CHECK (umidade     BETWEEN   0 AND 100),
    CONSTRAINT chk_amostras           CHECK (amostras    >= 1),
    CONSTRAINT chk_descartadas        CHECK (descartadas >= 0)
);

CREATE INDEX idx_leituras_dispositivo_data ON pji610.leituras(dispositivo_id, registrado_em DESC);
CREATE INDEX idx_leituras_data             ON pji610.leituras(registrado_em DESC);

CREATE TABLE pji610.baselines (
    dispositivo_id     UUID NOT NULL REFERENCES pji610.dispositivos(id) ON DELETE CASCADE,
    janela_minutos     INTEGER      NOT NULL,
    media_temperatura  NUMERIC(6,3) NOT NULL,
    desvio_temperatura NUMERIC(6,3) NOT NULL,
    media_umidade      NUMERIC(6,3) NOT NULL,
    desvio_umidade     NUMERIC(6,3) NOT NULL,
    amostras           INTEGER      NOT NULL,
    calculado_em       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    PRIMARY KEY (dispositivo_id, janela_minutos)
);

CREATE TABLE pji610.alertas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispositivo_id  UUID NOT NULL REFERENCES pji610.dispositivos(id) ON DELETE CASCADE,
    leitura_id      UUID NOT NULL REFERENCES pji610.leituras(id)     ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN (
        'temperatura_alta',     'temperatura_baixa',
        'umidade_alta',         'umidade_baixa',
        'anomalia_temperatura', 'anomalia_umidade'
    )),
    metodo          TEXT NOT NULL DEFAULT 'limiar_fixo'
                    CHECK (metodo IN ('limiar_fixo', 'limiar_dinamico')),
    valor_medido    NUMERIC(5,2) NOT NULL,
    limite          NUMERIC(6,3) NOT NULL,
    escore_z        NUMERIC(6,3),
    registrado_em   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_alertas_leitura_tipo UNIQUE (leitura_id, tipo)
);

CREATE INDEX idx_alertas_dispositivo_data ON pji610.alertas(dispositivo_id, registrado_em DESC);
CREATE INDEX idx_alertas_data             ON pji610.alertas(registrado_em DESC);
CREATE INDEX idx_alertas_tipo             ON pji610.alertas(tipo);
CREATE INDEX idx_alertas_metodo           ON pji610.alertas(metodo);

CREATE OR REPLACE FUNCTION pji610.fn_gerar_alertas() RETURNS TRIGGER AS $$
DECLARE
    v_dispositivo pji610.dispositivos%ROWTYPE;
BEGIN
    SELECT * INTO v_dispositivo
    FROM pji610.dispositivos
    WHERE id = NEW.dispositivo_id;

    IF NEW.temperatura > v_dispositivo.temperatura_max THEN
        INSERT INTO pji610.alertas (dispositivo_id, leitura_id, tipo, metodo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'temperatura_alta', 'limiar_fixo',
                NEW.temperatura, v_dispositivo.temperatura_max, NEW.registrado_em)
        ON CONFLICT (leitura_id, tipo) DO NOTHING;
    ELSIF NEW.temperatura < v_dispositivo.temperatura_min THEN
        INSERT INTO pji610.alertas (dispositivo_id, leitura_id, tipo, metodo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'temperatura_baixa', 'limiar_fixo',
                NEW.temperatura, v_dispositivo.temperatura_min, NEW.registrado_em)
        ON CONFLICT (leitura_id, tipo) DO NOTHING;
    END IF;

    IF NEW.umidade > v_dispositivo.umidade_max THEN
        INSERT INTO pji610.alertas (dispositivo_id, leitura_id, tipo, metodo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'umidade_alta', 'limiar_fixo',
                NEW.umidade, v_dispositivo.umidade_max, NEW.registrado_em)
        ON CONFLICT (leitura_id, tipo) DO NOTHING;
    ELSIF NEW.umidade < v_dispositivo.umidade_min THEN
        INSERT INTO pji610.alertas (dispositivo_id, leitura_id, tipo, metodo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'umidade_baixa', 'limiar_fixo',
                NEW.umidade, v_dispositivo.umidade_min, NEW.registrado_em)
        ON CONFLICT (leitura_id, tipo) DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = pji610, pg_temp;

CREATE TRIGGER trg_leituras_gerar_alertas
    AFTER INSERT ON pji610.leituras
    FOR EACH ROW
    EXECUTE FUNCTION pji610.fn_gerar_alertas();

CREATE OR REPLACE FUNCTION pji610.fn_atualizar_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = pji610, pg_temp;

CREATE TRIGGER trg_dispositivos_atualizado_em
    BEFORE UPDATE ON pji610.dispositivos
    FOR EACH ROW
    EXECUTE FUNCTION pji610.fn_atualizar_timestamp();

CREATE OR REPLACE FUNCTION pji610.fn_recalcular_baseline(p_dispositivo_id UUID)
RETURNS VOID AS $$
DECLARE
    v_janela INTEGER;
BEGIN
    SELECT janela_baseline_minutos INTO v_janela
    FROM pji610.dispositivos
    WHERE id = p_dispositivo_id;

    IF v_janela IS NULL THEN
        RETURN;
    END IF;

    INSERT INTO pji610.baselines (
        dispositivo_id, janela_minutos,
        media_temperatura, desvio_temperatura,
        media_umidade,     desvio_umidade,
        amostras, calculado_em
    )
    SELECT
        p_dispositivo_id,
        v_janela,
        AVG(temperatura),
        COALESCE(STDDEV_SAMP(temperatura), 0),
        AVG(umidade),
        COALESCE(STDDEV_SAMP(umidade), 0),
        COUNT(*),
        NOW()
    FROM pji610.leituras
    WHERE dispositivo_id = p_dispositivo_id
      AND registrado_em >= NOW() - (v_janela || ' minutes')::INTERVAL
    HAVING COUNT(*) >= 2
    ON CONFLICT (dispositivo_id, janela_minutos) DO UPDATE SET
        media_temperatura  = EXCLUDED.media_temperatura,
        desvio_temperatura = EXCLUDED.desvio_temperatura,
        media_umidade      = EXCLUDED.media_umidade,
        desvio_umidade     = EXCLUDED.desvio_umidade,
        amostras           = EXCLUDED.amostras,
        calculado_em       = EXCLUDED.calculado_em;
END;
$$ LANGUAGE plpgsql SET search_path = pji610, pg_temp;

CREATE OR REPLACE VIEW pji610.vw_leituras_analise AS
SELECT
    l.id,
    l.dispositivo_id,
    l.temperatura,
    l.umidade,
    l.amostras,
    l.descartadas,
    l.registrado_em,
    AVG(l.temperatura) OVER janela AS media_movel_temperatura,
    STDDEV_SAMP(l.temperatura) OVER janela AS desvio_movel_temperatura,
    AVG(l.umidade) OVER janela AS media_movel_umidade,
    STDDEV_SAMP(l.umidade) OVER janela AS desvio_movel_umidade
FROM pji610.leituras l
WINDOW janela AS (
    PARTITION BY l.dispositivo_id
    ORDER BY l.registrado_em
    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
);

CREATE OR REPLACE VIEW pji610.vw_dispositivos_status AS
SELECT
    d.id,
    d.nome,
    d.localizacao,
    d.temperatura_min,
    d.temperatura_max,
    d.umidade_min,
    d.umidade_max,
    d.z_limite,
    d.janela_baseline_minutos,
    d.intervalo_offline_segundos,
    d.ativo,
    d.criado_em,
    d.atualizado_em,
    l.temperatura  AS ultima_temperatura,
    l.umidade      AS ultima_umidade,
    l.registrado_em AS ultima_leitura_em,
    CASE
        WHEN l.registrado_em IS NULL THEN 'offline'
        WHEN l.registrado_em < NOW() - (d.intervalo_offline_segundos || ' seconds')::INTERVAL
            THEN 'offline'
        ELSE 'online'
    END AS status
FROM pji610.dispositivos d
LEFT JOIN LATERAL (
    SELECT temperatura, umidade, registrado_em
    FROM pji610.leituras
    WHERE dispositivo_id = d.id
    ORDER BY registrado_em DESC
    LIMIT 1
) l ON TRUE;

GRANT USAGE ON SCHEMA pji610 TO anon, authenticated, service_role;

GRANT SELECT ON ALL TABLES IN SCHEMA pji610 TO anon, authenticated;
GRANT ALL    ON ALL TABLES IN SCHEMA pji610 TO service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA pji610
    GRANT SELECT ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA pji610
    GRANT ALL ON TABLES TO service_role;

GRANT UPDATE ON pji610.dispositivos TO authenticated;

ALTER TABLE pji610.dispositivos ENABLE ROW LEVEL SECURITY;
ALTER TABLE pji610.leituras     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pji610.alertas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE pji610.baselines    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dispositivos_select_authenticated"
    ON pji610.dispositivos FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "dispositivos_update_authenticated"
    ON pji610.dispositivos FOR UPDATE
    TO authenticated
    USING (TRUE)
    WITH CHECK (TRUE);

CREATE POLICY "leituras_select_authenticated"
    ON pji610.leituras FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "alertas_select_authenticated"
    ON pji610.alertas FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "baselines_select_authenticated"
    ON pji610.baselines FOR SELECT
    TO authenticated
    USING (TRUE);

DO $$
DECLARE
    v_tabela TEXT;
BEGIN
    FOREACH v_tabela IN ARRAY ARRAY['leituras', 'alertas', 'dispositivos'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
            WHERE pubname = 'supabase_realtime'
              AND schemaname = 'pji610'
              AND tablename = v_tabela
        ) THEN
            EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE pji610.%I', v_tabela);
        END IF;
    END LOOP;
END $$;

INSERT INTO pji610.dispositivos (nome, localizacao, api_key,
                                 temperatura_min, temperatura_max,
                                 umidade_min,     umidade_max)
VALUES
    ('ESP32-001', 'Itupeva, SP',
     encode(gen_random_bytes(32), 'hex'),
     18.0, 30.0, 30.0, 70.0),
    ('ESP32-002', 'Itupeva, SP',
     encode(gen_random_bytes(32), 'hex'),
     18.0, 30.0, 30.0, 70.0);
