# Wokwi — ESP32 + DHT22 (MicroPython)

Código que roda no ESP32 simulado no [Wokwi](https://wokwi.com). Lê temperatura e umidade do DHT22 a cada 10 segundos, descarta leituras inválidas e envia a média de 6 amostras para o backend FastAPI via HTTP POST.

## Arquivos

| Arquivo | Função |
|---|---|
| `boot.py`      | Executado uma vez ao ligar (mínimo, só inicialização) |
| `main.py`      | Loop principal: Wi-Fi → sensor → envio HTTP |
| `config.py`    | Credenciais, URL do backend, pino do DHT22 |
| `diagram.json` | Circuito do Wokwi (ESP32 + DHT22 ligados no GPIO4) |

## Circuito

```
ESP32          DHT22
─────          ─────
3V3   ───────► VCC
GND   ───────► GND
GPIO4  ──────► SDA (data)
```

## Como rodar no Wokwi

1. Acesse [wokwi.com](https://wokwi.com) e clique **+ New Project → MicroPython on ESP32**
2. Você verá três abas: `main.py`, `boot.py`, e `diagram.json`
3. **Cole o conteúdo** dos arquivos desta pasta nas abas correspondentes
4. Crie uma nova aba clicando no `+` e adicione `config.py` com o conteúdo do nosso arquivo
5. Edite `config.py`:
   - `API_BASE_URL` — URL do backend deployado no Vercel
   - `API_KEY` — a `api_key` do dispositivo no banco (ver `database-schema.sql` na raiz)
6. Clique em **▶ Start the simulation**
7. Acompanhe o console — você verá os logs de Wi-Fi, leituras e envios HTTP

## Como rodar duas placas (Artur Nogueira + Itupeva)

Crie **dois projetos separados** no Wokwi, cada um com sua própria `API_KEY`. Cada projeto envia para o mesmo backend, mas é identificado pelo dispositivo correspondente no banco.

## Wokwi-CLI (opcional)

Se preferir editar localmente e simular via terminal, instale a [wokwi-cli](https://docs.wokwi.com/wokwi-ci/cli-installation):

```bash
npm install -g @wokwi/cli
cd wokwi/
wokwi-cli .
```

## Fluxo completo

```
┌─────────────────┐
│  ESP32 boot.py  │ → inicializa
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  main.py        │
│  ───────────    │
│  conectar_wifi  │
│  → DHT22        │
│  → POST /leitur │ ──── X-API-Key ────► FastAPI ──► Supabase
│  → sleep 30s    │
│  ↺ loop         │
└─────────────────┘
```

## Solução de problemas

**"falha ao conectar" no Wi-Fi**
No Wokwi, sempre use `WIFI_SSID = "Wokwi-GUEST"` com senha vazia.

**"erro http 401"**
A `API_KEY` em `config.py` não bate com nenhuma `dispositivos.api_key` no Supabase. Verifique se copiou corretamente.

**"erro http 422"**
O payload está malformado. Confira que `temperatura` e `umidade` são números (não strings).

**Console mudo**
Verifique se o `diagram.json` inclui as conexões do `$serialMonitor` e se o DHT22 está no circuito.
