"""Pruebas del ARQ (arq.py) sobre el canal simulado.

Usan un método de detección de prueba (CRC-16 de la biblioteca estándar) para no
depender de deteccion.py, que es de Raúl.
"""

import binascii

import pytest

from tele_ir_link import tramas
from tele_ir_link.arq import (
    MODOS,
    Estadisticas,
    enviar_mensaje,
    recibir_mensaje,
    transmitir_simulado,
)
from tele_ir_link.canal import CanalSimulado, ConfigRuido
from tele_ir_link.tramas import Metodo

MENSAJE = bytes(range(256)) * 2 + b"fin del mensaje"  # 527 bytes: varias tramas
RAPIDO = {"timeout": 0.03}


@pytest.fixture(autouse=True)
def metodo_de_prueba(monkeypatch):
    monkeypatch.setitem(tramas.METODOS, "crc_prueba", Metodo(2, lambda c: binascii.crc_hqx(c, 0)))


@pytest.mark.parametrize("modo", MODOS)
def test_sin_ruido_llega_igual_y_sin_retransmisiones(modo):
    recibido, stats = transmitir_simulado(MENSAJE, modo, "crc_prueba", **RAPIDO)
    assert recibido == MENSAJE
    assert stats.retransmisiones == 0
    assert stats.tramas_enviadas == stats.tramas_utiles
    assert stats.eficiencia == 1.0


@pytest.mark.parametrize("modo", MODOS)
def test_mensaje_vacio(modo):
    recibido, stats = transmitir_simulado(b"", modo, "crc_prueba", **RAPIDO)
    assert recibido == b""
    assert stats.tramas_utiles == 1  # solo el FIN


@pytest.mark.parametrize("modo", MODOS)
def test_mensaje_de_un_fragmento(modo):
    recibido, _ = transmitir_simulado(b"hola", modo, "crc_prueba", **RAPIDO)
    assert recibido == b"hola"


@pytest.mark.parametrize("modo", MODOS)
def test_con_ruido_el_mensaje_llega_igual_y_hay_retransmisiones(modo):
    ruido = ConfigRuido(prob_bit=0.002, prob_rafaga=0.10, prob_perdida=0.05)
    recibido, stats = transmitir_simulado(MENSAJE, modo, "crc_prueba", ruido, semilla=1, **RAPIDO)
    assert recibido == MENSAJE
    assert stats.retransmisiones > 0
    assert stats.errores_corregidos > 0
    assert stats.eficiencia < 1.0


@pytest.mark.parametrize("modo", MODOS)
def test_con_perdidas_el_temporizador_reenvia(modo):
    ruido = ConfigRuido(prob_perdida=0.3)
    recibido, stats = transmitir_simulado(MENSAJE, modo, "crc_prueba", ruido, semilla=2, **RAPIDO)
    assert recibido == MENSAJE
    assert stats.timeouts > 0


@pytest.mark.parametrize("modo", MODOS)
def test_canal_muerto_agota_los_reintentos(modo):
    a, _ = CanalSimulado.crear_enlace(ConfigRuido(prob_perdida=1.0))
    with pytest.raises(ConnectionError):
        enviar_mensaje(a, b"hola", modo, "crc_prueba", timeout=0.01, max_reintentos=3)


@pytest.mark.parametrize("modo", MODOS)
def test_receptor_sin_emisor_lanza_timeout(modo):
    _, b = CanalSimulado.crear_enlace()
    with pytest.raises(TimeoutError):
        recibir_mensaje(b, modo, "crc_prueba", timeout=0.01, max_reintentos=3)


def test_mas_de_256_tramas_reusa_los_numeros_de_secuencia():
    mensaje = bytes(range(256)) * 40  # 10240 bytes / 32 = 320 fragmentos + FIN
    for modo in MODOS:
        recibido, _ = transmitir_simulado(mensaje, modo, "crc_prueba", timeout=0.03)
        assert recibido == mensaje


def test_ventana_invalida():
    a, _ = CanalSimulado.crear_enlace()
    with pytest.raises(ValueError):
        enviar_mensaje(a, b"x", "rechazo_selectivo", "crc_prueba", ventana=129)
    with pytest.raises(ValueError):
        enviar_mensaje(a, b"x", "no_existe", "crc_prueba")


def test_selectivo_reenvia_menos_que_retroceda_n_con_mucho_ruido():
    ruido = ConfigRuido(prob_bit=0.002)
    reenvios = {}
    for modo in ("retroceda_n", "rechazo_selectivo"):
        total = 0
        for semilla in range(5):
            _, stats = transmitir_simulado(MENSAJE, modo, "crc_prueba", ruido,
                                           semilla=semilla, ventana=8, **RAPIDO)
            total += stats.retransmisiones
        reenvios[modo] = total
    assert reenvios["rechazo_selectivo"] < reenvios["retroceda_n"]


def test_eficiencia_sin_tramas_es_cero():
    assert Estadisticas().eficiencia == 0.0
