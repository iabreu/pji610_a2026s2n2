import time
import math
import network
import urequests
import ujson
import dht

from machine import Pin

import config


def conectar_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    if not sta.isconnected():
        print("[wifi] conectando em '{}'...".format(config.WIFI_SSID))
        sta.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

        tentativas = 0

        while not sta.isconnected() and tentativas < 30:
            time.sleep(1)
            tentativas += 1

    if sta.isconnected():
        print("[wifi] conectado. IP: {}".format(sta.ifconfig()[0]))
        return True
    else:
        print("[wifi] falha ao conectar")
        return False


def ler_sensor(sensor):
    try:
        sensor.measure()
        return sensor.temperature(), sensor.humidity()
    except OSError as e:
        print("[sensor] erro: {}".format(e))
        return None, None


def leitura_valida(temperatura, umidade):
    """Descarta leitura fora da faixa operacional do DHT22."""
    if temperatura is None or umidade is None:
        return False
    if not config.TEMP_VALIDA_MIN <= temperatura <= config.TEMP_VALIDA_MAX:
        return False
    if not config.UMID_VALIDA_MIN <= umidade <= config.UMID_VALIDA_MAX:
        return False
    return True


def media(valores):
    return sum(valores) / len(valores)


def desvio_padrao(valores, m):
    """Desvio-padrao amostral. Zero com menos de duas amostras."""
    if len(valores) < 2:
        return 0.0
    variancia = sum((v - m) ** 2 for v in valores) / (len(valores) - 1)
    return math.sqrt(variancia)


def enviar_leitura(payload):
    corpo = ujson.dumps(payload)

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": config.API_KEY
    }

    for tentativa in range(1, config.MAX_TENTATIVAS + 1):
        try:
            print("[http] POST {} (tentativa {})".format(
                config.ENDPOINT_LEITURAS,
                tentativa
            ))

            resp = urequests.post(
                config.ENDPOINT_LEITURAS,
                data=corpo,
                headers=headers
            )

            status = resp.status_code
            resp.close()

            if 200 <= status < 300:
                print("[http] ok ({})".format(status))
                return True
            else:
                print("[http] erro http {}".format(status))

        except Exception as e:
            print("[http] excecao: {}".format(e))

        if tentativa < config.MAX_TENTATIVAS:
            time.sleep(2 * tentativa)

    return False


print("\n=== Projeto Integrador VI - UNIVESP ===")
print("Inicializando ESP32...")

if conectar_wifi():

    sensor = dht.DHT22(Pin(config.PINO_DHT22))

    print("[main] sensor DHT22 no pino {}".format(config.PINO_DHT22))
    print("[main] amostra a cada {}s, envio a cada {} amostras ({}s)\n".format(
        config.INTERVALO_AMOSTRA_SEGUNDOS,
        config.AMOSTRAS_POR_ENVIO,
        config.INTERVALO_AMOSTRA_SEGUNDOS * config.AMOSTRAS_POR_ENVIO
    ))

    time.sleep(2)

    temperaturas = []
    umidades = []
    descartadas = 0

    while True:

        temperatura, umidade = ler_sensor(sensor)

        if leitura_valida(temperatura, umidade):
            temperaturas.append(temperatura)
            umidades.append(umidade)

            print("[amostra] {}/{} | temp: {:.1f} C | umid: {:.1f} %".format(
                len(temperaturas),
                config.AMOSTRAS_POR_ENVIO,
                temperatura,
                umidade
            ))
        else:
            descartadas += 1
            print("[amostra] invalida, descartada ({} no ciclo)".format(
                descartadas
            ))

        if len(temperaturas) >= config.AMOSTRAS_POR_ENVIO:

            media_temp = media(temperaturas)
            media_umid = media(umidades)

            payload = {
                "temperatura": round(media_temp, 2),
                "umidade": round(media_umid, 2),
                "amostras": len(temperaturas),
                "descartadas": descartadas,
                "desvio_temperatura": round(
                    desvio_padrao(temperaturas, media_temp), 3
                ),
                "desvio_umidade": round(
                    desvio_padrao(umidades, media_umid), 3
                ),
            }

            print(
                "[agregado] temp: {:.2f} C (s={:.3f}) | "
                "umid: {:.2f} % (s={:.3f}) | "
                "{} amostras, {} descartadas".format(
                    payload["temperatura"],
                    payload["desvio_temperatura"],
                    payload["umidade"],
                    payload["desvio_umidade"],
                    payload["amostras"],
                    payload["descartadas"]
                )
            )

            enviar_leitura(payload)

            temperaturas = []
            umidades = []
            descartadas = 0

        time.sleep(config.INTERVALO_AMOSTRA_SEGUNDOS)

else:
    print("[main] sem wifi, parando.")
