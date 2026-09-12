-- Schema do banco de dados (Supabase / PostgreSQL)
--
-- Como executar:
--   1. Abra o SQL Editor no painel do Supabase
--   2. Cole este arquivo inteiro e execute
--   3. (Opcional) Execute database-seed.sql para popular com dados de teste
--   4. Veja README.md na raiz para o passo a passo completo

-- Limpar objetos existentes (idempotente para re-execução durante desenvolvimento)
DROP VIEW  IF EXISTS vw_dispositivos_status CASCADE;
DROP TABLE IF EXISTS alertas               CASCADE;
DROP TABLE IF EXISTS leituras              CASCADE;
DROP TABLE IF EXISTS dispositivos          CASCADE;

--
-- dispositivos
--
CREATE TABLE dispositivos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome            TEXT NOT NULL,
    localizacao     TEXT NOT NULL,
    api_key         TEXT NOT NULL UNIQUE,

    -- Limites (thresholds) configuráveis pela UI
    temperatura_min NUMERIC(5,2) NOT NULL DEFAULT 18.0,
    temperatura_max NUMERIC(5,2) NOT NULL DEFAULT 30.0,
    umidade_min     NUMERIC(5,2) NOT NULL DEFAULT 30.0,
    umidade_max     NUMERIC(5,2) NOT NULL DEFAULT 70.0,

    -- Tempo (em segundos) sem leitura para considerar dispositivo offline
    intervalo_offline_segundos INTEGER NOT NULL DEFAULT 120,

    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_temperatura_limites CHECK (temperatura_min < temperatura_max),
    CONSTRAINT chk_umidade_limites     CHECK (umidade_min     < umidade_max)
);

CREATE INDEX idx_dispositivos_api_key ON dispositivos(api_key);
CREATE INDEX idx_dispositivos_ativo   ON dispositivos(ativo) WHERE ativo = TRUE;

COMMENT ON TABLE  dispositivos          IS 'Cadastro dos ESP32 que enviam leituras de temperatura e umidade';
COMMENT ON COLUMN dispositivos.api_key  IS 'Chave de autenticação usada pelo ESP32 ao enviar leituras (header X-API-Key)';
COMMENT ON COLUMN dispositivos.intervalo_offline_segundos
                                        IS 'Tempo sem leitura para o dispositivo ser considerado offline';

--
-- leituras
--
CREATE TABLE leituras (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispositivo_id  UUID NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    temperatura     NUMERIC(5,2) NOT NULL,
    umidade         NUMERIC(5,2) NOT NULL,
    registrado_em   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_temperatura_valida CHECK (temperatura BETWEEN -50 AND 100),
    CONSTRAINT chk_umidade_valida     CHECK (umidade     BETWEEN   0 AND 100)
);

CREATE INDEX idx_leituras_dispositivo_data ON leituras(dispositivo_id, registrado_em DESC);
CREATE INDEX idx_leituras_data             ON leituras(registrado_em DESC);

COMMENT ON TABLE leituras IS 'Histórico de leituras de temperatura e umidade';

--
-- alertas
--
CREATE TABLE alertas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispositivo_id  UUID NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    leitura_id      UUID NOT NULL REFERENCES leituras(id)     ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN (
        'temperatura_alta', 'temperatura_baixa',
        'umidade_alta',     'umidade_baixa'
    )),
    valor_medido    NUMERIC(5,2) NOT NULL,
    limite          NUMERIC(5,2) NOT NULL,
    registrado_em   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alertas_dispositivo_data ON alertas(dispositivo_id, registrado_em DESC);
CREATE INDEX idx_alertas_data             ON alertas(registrado_em DESC);
CREATE INDEX idx_alertas_tipo             ON alertas(tipo);

COMMENT ON TABLE alertas IS 'Eventos disparados quando uma leitura viola os limites configurados';

--
-- Trigger: gerar alertas ao inserir leitura fora dos limites
--
CREATE OR REPLACE FUNCTION fn_gerar_alertas() RETURNS TRIGGER AS $$
DECLARE
    v_dispositivo dispositivos%ROWTYPE;
BEGIN
    SELECT * INTO v_dispositivo
    FROM dispositivos
    WHERE id = NEW.dispositivo_id;

    -- Temperatura
    IF NEW.temperatura > v_dispositivo.temperatura_max THEN
        INSERT INTO alertas (dispositivo_id, leitura_id, tipo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'temperatura_alta',
                NEW.temperatura, v_dispositivo.temperatura_max, NEW.registrado_em);
    ELSIF NEW.temperatura < v_dispositivo.temperatura_min THEN
        INSERT INTO alertas (dispositivo_id, leitura_id, tipo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'temperatura_baixa',
                NEW.temperatura, v_dispositivo.temperatura_min, NEW.registrado_em);
    END IF;

    -- Umidade
    IF NEW.umidade > v_dispositivo.umidade_max THEN
        INSERT INTO alertas (dispositivo_id, leitura_id, tipo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'umidade_alta',
                NEW.umidade, v_dispositivo.umidade_max, NEW.registrado_em);
    ELSIF NEW.umidade < v_dispositivo.umidade_min THEN
        INSERT INTO alertas (dispositivo_id, leitura_id, tipo, valor_medido, limite, registrado_em)
        VALUES (NEW.dispositivo_id, NEW.id, 'umidade_baixa',
                NEW.umidade, v_dispositivo.umidade_min, NEW.registrado_em);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leituras_gerar_alertas
    AFTER INSERT ON leituras
    FOR EACH ROW
    EXECUTE FUNCTION fn_gerar_alertas();

--
-- Trigger: atualizar campo atualizado_em
--
CREATE OR REPLACE FUNCTION fn_atualizar_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dispositivos_atualizado_em
    BEFORE UPDATE ON dispositivos
    FOR EACH ROW
    EXECUTE FUNCTION fn_atualizar_timestamp();

--
-- View: status atual dos dispositivos (última leitura + online/offline)
--
CREATE OR REPLACE VIEW vw_dispositivos_status AS
SELECT
    d.id,
    d.nome,
    d.localizacao,
    d.temperatura_min,
    d.temperatura_max,
    d.umidade_min,
    d.umidade_max,
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
FROM dispositivos d
LEFT JOIN LATERAL (
    SELECT temperatura, umidade, registrado_em
    FROM leituras
    WHERE dispositivo_id = d.id
    ORDER BY registrado_em DESC
    LIMIT 1
) l ON TRUE;

COMMENT ON VIEW vw_dispositivos_status IS 'Status atual de cada dispositivo, com a última leitura e o status online/offline calculado';

--
-- Row Level Security (RLS)
--
-- Backend FastAPI usa service_role key (bypassa RLS) para gravar leituras.
-- Frontend Next.js usa anon key + sessão de usuário autenticado para ler.

ALTER TABLE dispositivos ENABLE ROW LEVEL SECURITY;
ALTER TABLE leituras     ENABLE ROW LEVEL SECURITY;
ALTER TABLE alertas      ENABLE ROW LEVEL SECURITY;

-- dispositivos: SELECT e UPDATE para usuários autenticados
CREATE POLICY "dispositivos_select_authenticated"
    ON dispositivos FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "dispositivos_update_authenticated"
    ON dispositivos FOR UPDATE
    TO authenticated
    USING (TRUE)
    WITH CHECK (TRUE);

-- leituras: SELECT para usuários autenticados
CREATE POLICY "leituras_select_authenticated"
    ON leituras FOR SELECT
    TO authenticated
    USING (TRUE);

-- alertas: SELECT para usuários autenticados
CREATE POLICY "alertas_select_authenticated"
    ON alertas FOR SELECT
    TO authenticated
    USING (TRUE);

--
-- Realtime
--
-- Após DROP TABLE no início, as entradas são removidas da publicação,
-- então podemos adicionar com segurança.

ALTER PUBLICATION supabase_realtime ADD TABLE leituras;
ALTER PUBLICATION supabase_realtime ADD TABLE alertas;
ALTER PUBLICATION supabase_realtime ADD TABLE dispositivos;

--
-- Dados iniciais: dispositivos do projeto
--
-- IMPORTANTE: substitua as api_keys por valores aleatórios em produção.
-- Gere com: SELECT encode(gen_random_bytes(32), 'hex');

INSERT INTO dispositivos (nome, localizacao, api_key,
                          temperatura_min, temperatura_max,
                          umidade_min,     umidade_max)
VALUES
    ('ESP32-001', 'Artur Nogueira, SP',
     'troque_esta_chave_artur_nogueira',
     18.0, 30.0, 30.0, 70.0),
    ('ESP32-002', 'Itupeva, SP',
     'troque_esta_chave_itupeva',
     18.0, 30.0, 30.0, 70.0);
