"""Pruebas de transmisión asíncrona y síncrona (transmision.py)."""

import pytest

from tele_ir_link.transmision import (
    BANDERA,
    ConfigAsincrona,
    comparar,
    desentramar_asincrono,
    entramar_asincrono,
    entramar_sincrono,
    quitar_relleno,
    rellenar,
    rendimiento_sincrono,
    separar_bloques,
)

MENSAJE = b"Hola TELE"


def test_formato_de_un_caracter():
    # 'A' = 0x41 = 0100 0001 -> LSB primero: 1 0 0 0 0 0 1 0
    assert entramar_asincrono(b"A") == [0, 1, 0, 0, 0, 0, 0, 1, 0, 1]


def test_asincrono_ida_y_vuelta():
    configs = (ConfigAsincrona(), ConfigAsincrona(paridad="impar", bits_paro=2))
    for config in configs:
        bits = entramar_asincrono(MENSAJE, config)
        resultado = desentramar_asincrono(bits, config)
        assert resultado.datos == MENSAJE
        assert resultado.errores_trama == 0
        assert resultado.errores_paridad == 0


def test_rendimiento_asincrono():
    assert ConfigAsincrona().rendimiento == pytest.approx(8 / 10)
    con_extras = ConfigAsincrona(paridad="par", bits_paro=2)
    assert con_extras.rendimiento == pytest.approx(8 / 12)


@pytest.mark.parametrize("opciones", [
    {"bits_datos": 9},
    {"paridad": "Par"},
    {"bits_paro": 3},
])
def test_configuracion_invalida(opciones):
    with pytest.raises(ValueError):
        ConfigAsincrona(**opciones)


def test_error_en_un_dato_solo_dana_un_caracter():
    bits = entramar_asincrono(MENSAJE)
    bits[3 * 10 + 4] ^= 1               # un bit de datos del 4.º carácter
    recibido = desentramar_asincrono(bits).datos
    distintos = [i for i, (a, b) in enumerate(zip(MENSAJE, recibido)) if a != b]
    assert distintos == [3]


def test_la_paridad_detecta_el_error():
    config = ConfigAsincrona(paridad="par")
    bits = entramar_asincrono(MENSAJE, config)
    bits[2] ^= 1
    assert desentramar_asincrono(bits, config).errores_paridad == 1


def test_paro_danado_es_error_de_trama():
    bits = entramar_asincrono(b"AB")
    bits[9] = 0                         # bit de paro del primer carácter
    assert desentramar_asincrono(bits).errores_trama >= 1


def test_se_resincroniza_tras_perder_el_arranque():
    bits = entramar_asincrono(b"\xff" * 10)
    bits[0] = 1                         # se pierde el arranque del 1.er carácter
    # En 0xFF los únicos ceros son los arranques: solo se pierde un carácter.
    assert desentramar_asincrono(bits).datos == b"\xff" * 9


def test_relleno_escapa_bandera_y_escape():
    entrada = bytes([0x01, 0x7E, 0x7D, 0x02])
    esperado = bytes([0x01, 0x7D, 0x5E, 0x7D, 0x5D, 0x02])
    assert rellenar(entrada) == esperado


def test_relleno_ida_y_vuelta():
    datos = bytes(range(256))
    assert quitar_relleno(rellenar(datos)) == datos
    assert BANDERA not in rellenar(datos)


def test_bloques_se_separan_aunque_los_datos_traigan_7e():
    b1, b2 = b"uno\x7euno", b"dos\x7ddos"
    flujo = entramar_sincrono(b1) + entramar_sincrono(b2)
    assert separar_bloques(flujo) == [b1, b2]


def test_rendimiento_sincrono_de_las_laminas():
    # bloque de 1024 bytes con 10 de control: más del 99 %
    assert rendimiento_sincrono(1024, 10) > 0.99


def test_sincrono_rinde_mas_con_bloques_grandes():
    tabla = comparar([16, 128, 1024])
    asinc = [a for _, a, _ in tabla]
    sinc = [s for _, _, s in tabla]
    assert asinc == [0.8, 0.8, 0.8]
    assert sinc == sorted(sinc)
    assert sinc[0] < 0.8 < sinc[-1]