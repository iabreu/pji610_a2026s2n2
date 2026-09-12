# No Wokwi, use "Wokwi-GUEST" sem senha.
# Em hardware real, coloque o SSID/senha da sua rede.
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

# URL do FastAPI no Vercel (sem barra final).
# No dev local, use o IP da máquina na LAN ou um túnel (ngrok), não localhost.
API_BASE_URL = "https://seu-backend.vercel.app"
ENDPOINT_LEITURAS = API_BASE_URL + "/leituras"

# Chave do dispositivo (gerada no Supabase).
# NUNCA comitar o valor real — edite apenas no editor do Wokwi.
API_KEY = "troque_esta_chave_pelo_valor_real_do_supabase"

# Pré-processamento na borda ------------------------------------------------
# Intervalo entre amostras do sensor, em segundos (o DHT22 exige >= 2s).
INTERVALO_AMOSTRA_SEGUNDOS = 10

# Amostras válidas acumuladas antes de enviar uma leitura agregada.
# 6 amostras x 10s = um POST por minuto, contra seis sem a agregação.
AMOSTRAS_POR_ENVIO = 6

# Faixa operacional do DHT22: leitura fora disso é descartada na borda.
TEMP_VALIDA_MIN = -40.0
TEMP_VALIDA_MAX = 80.0
UMID_VALIDA_MIN = 0.0
UMID_VALIDA_MAX = 100.0

PINO_DHT22 = 4
TIMEOUT_HTTP_SEGUNDOS = 10
MAX_TENTATIVAS = 3
