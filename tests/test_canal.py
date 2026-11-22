"""Pruebas del canal simulado (canal.py)."""

import random

import pytest

from tele_ir_link.canal import Canal, CanalSimulado, ConfigRuido

MENSAJE = b"Hola TELE"


def bits_distintos(a: bytes, b: bytes) -> int:
    """Cuenta cuántos bits cambian entre dos mensajes del mismo largo."""
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def test_crear_enlace_entrega_dos_canales():
    a, b = CanalSimulado.crear_enlace()
    assert isinstance(a, CanalSimulado)
    assert isinstance(b, CanalSimulado)
    assert a is not b


def test_canal_simulado_cumple_la_interfaz_canal():
    a, _ = CanalSimulado.crear_enlace()
    assert isinstance(a, Canal)


def test_canal_abstracto_no_se_puede_instanciar():
    with pytest.raises(TypeError):
        Canal()


def test_subclase_incompleta_no_se_puede_instanciar():
    class CanalIncompleto(Canal):
        def enviar(self, datos: bytes) -> None:
            pass
        # falta recibir (como cuando se llamaba "resibir")

    with pytest.raises(TypeError):
        CanalIncompleto()


def test_sin_ruido_llega_igual_de_a_hacia_b():
    a, b = CanalSimulado.crear_enlace(semilla=1)
    a.enviar(MENSAJE)
    assert b.recibir() == MENSAJE


def test_sin_ruido_llega_igual_de_b_hacia_a():
    a, b = CanalSimulado.crear_enlace(semilla=1)
    b.enviar(MENSAJE)
    assert a.recibir() == MENSAJE


def test_el_emisor_no_recibe_su_propio_mensaje():
    a, b = CanalSimulado.crear_enlace(semilla=1)
    a.enviar(MENSAJE)
    assert a.recibir() is None


def test_recibir_sin_nada_pendiente_regresa_none():
    a, _ = CanalSimulado.crear_enlace()
    assert a.recibir(timeout=0.1) is None


def test_los_mensajes_llegan_en_orden():
    a, b = CanalSimulado.crear_enlace(semilla=1)
    for mensaje in (b"uno", b"dos", b"tres"):
        a.enviar(mensaje)
    assert [b.recibir(), b.recibir(), b.recibir()] == [b"uno", b"dos", b"tres"]
    assert b.recibir() is None


def test_enviar_sin_enlace_lanza_error():
    suelto = CanalSimulado(ConfigRuido(), random.Random(0))
    with pytest.raises(RuntimeError):
        suelto.enviar(MENSAJE)


def test_perdida_total_no_entrega_nada_pero_cuenta_bits():
    a, b = CanalSimulado.crear_enlace(ConfigRuido(prob_perdida=1.0), semilla=1)
    a.enviar(MENSAJE)
    assert b.recibir() is None
    assert a.bits_enviados == len(MENSAJE) * 8


def test_ruido_blanco_total_invierte_todos_los_bits():
    a, b = CanalSimulado.crear_enlace(ConfigRuido(prob_bit=1.0), semilla=1)
    a.enviar(MENSAJE)
    assert b.recibir() == bytes(x ^ 0xFF for x in MENSAJE)
    assert a.bits_volteados == len(MENSAJE) * 8


def test_rafaga_dana_a_lo_mas_largo_rafaga_bits():
    config = ConfigRuido(prob_rafaga=1.0, largo_rafaga=8)
    for semilla in range(50):
        a, b = CanalSimulado.crear_enlace(config, semilla=semilla)
        a.enviar(MENSAJE)
        recibido = b.recibir()
        cambiados = bits_distintos(MENSAJE, recibido)
        assert 1 <= cambiados <= 8
        assert cambiados == a.bits_volteados


def test_atenuacion_en_el_alcance_maximo():
    config = ConfigRuido(distancia_cm=100, alcance_cm=100, prob_bit_max_atenuacion=1.0)
    a, b = CanalSimulado.crear_enlace(config, semilla=1)
    a.enviar(MENSAJE)
    assert b.recibir() == bytes(x ^ 0xFF for x in MENSAJE)


@pytest.mark.parametrize(
    ("distancia", "esperada"),
    [(0, 0.0), (50, 0.05), (100, 0.10), (300, 0.10)],
)
def test_prob_error_crece_con_la_distancia(distancia, esperada):
    config = ConfigRuido(distancia_cm=distancia, alcance_cm=100, prob_bit_max_atenuacion=0.10)
    a, _ = CanalSimulado.crear_enlace(config)
    assert a._prob_error_por_bit() == pytest.approx(esperada)



def correr(semilla: int) -> list[bytes | None]:
    config = ConfigRuido(prob_bit=0.05, prob_rafaga=0.3, prob_perdida=0.2)
    a, b = CanalSimulado.crear_enlace(config, semilla=semilla)
    resultados = []
    for _ in range(20):
        a.enviar(MENSAJE)
        resultados.append(b.recibir())
    return resultados


def test_misma_semilla_mismos_errores():
    assert correr(42) == correr(42)


def test_distinta_semilla_distintos_errores():
    assert correr(42) != correr(7)