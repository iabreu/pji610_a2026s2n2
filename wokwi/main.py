import time
import network
import urequests
import ujson
import dht
import random

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
        temperatura = round(random.uniform(18.0, 35.0), 1)
        umidade = round(random.uniform(40.0, 85.0), 1)
        return temperatura, umidade
    except OSError as e:
        print("[sensor] erro: {}".format(e))
        return None, None


def enviar_leitura(temperatura, umidade):
    payload = ujson.dumps({
        "temperatura": temperatura,
        "umidade": umidade
    })

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
                data=payload,
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
    print("[main] intervalo: {}s\n".format(
        config.INTERVALO_LEITURA_SEGUNDOS
    ))

    time.sleep(2)

    while True:

        temperatura, umidade = ler_sensor(sensor)

        if temperatura is not None:

            print(
                "[leitura] temp: {:.1f} C | umid: {:.1f} %".format(
                    temperatura,
                    umidade
                )
            )

            enviar_leitura(temperatura, umidade)

        else:
            print("[leitura] falhou, pulando")

        time.sleep(config.INTERVALO_LEITURA_SEGUNDOS)

else:
    print("[main] sem wifi, parando.")
