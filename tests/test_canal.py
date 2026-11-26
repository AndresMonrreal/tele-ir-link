"""Pruebas del canal simulado (canal.py)."""

import time

import pytest

from tele_ir_link.canal import MEDIOS, Canal, CanalSimulado, ConfigRuido, Medio, Sentido

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
        cambiados = bits_distintos(MENSAJE, b.recibir())
        assert 1 <= cambiados <= 8
        assert cambiados == a.bits_volteados


def test_guiado_atenuacion_lineal_en_db():
    utp = MEDIOS["par_trenzado_utp"]
    assert utp.perdida_db(0) == 0
    assert utp.perdida_db(100) == pytest.approx(2 * utp.perdida_db(50))


def test_no_guiado_pierde_6_db_al_doblar_la_distancia():
    ir = MEDIOS["infrarrojo"]
    # 20 * log10(2) = 6.02 dB: la potencia cae con 1/d²
    assert ir.perdida_db(2.0) - ir.perdida_db(1.0) == pytest.approx(6.02, abs=0.01)


@pytest.mark.parametrize("clave", list(MEDIOS))
def test_mas_distancia_mas_errores(clave):
    m = MEDIOS[clave]
    d = m.distancia_tipica_m
    assert m.snr_db(d * 2) < m.snr_db(d)
    assert m.prob_error_bit(d * 2) >= m.prob_error_bit(d)


def test_ber_conocida():
    # S/N lineal = 1 (0 dB) -> 0.5 * erfc(1) = 0.0786...
    medio = Medio("prueba", True, snr_ref_db=0, distancia_ref_m=0, atenuacion_db_por_m=0,
                  velocidad_bps=1e6, factor_velocidad=1, prob_rafaga=0, distancia_tipica_m=1)
    assert medio.prob_error_bit(0) == pytest.approx(0.0786, abs=1e-4)


def test_fibra_aguanta_mas_distancia_que_el_par_trenzado():
    d = 500
    assert MEDIOS["fibra_multimodo"].prob_error_bit(d) < MEDIOS["par_trenzado_utp"].prob_error_bit(d)


def test_el_canal_usa_el_ruido_del_medio():
    cerca, _ = CanalSimulado.crear_enlace(medio="infrarrojo", distancia_m=0.5)
    lejos, _ = CanalSimulado.crear_enlace(medio="infrarrojo", distancia_m=5)
    assert lejos.prob_error_bit > cerca.prob_error_bit
    assert lejos.snr_db < cerca.snr_db


def test_retardo_satelite_geo():
    a, _ = CanalSimulado.crear_enlace(medio="satelite_geo")
    # ~71 572 km a la velocidad de la luz: ~0.239 s de ida
    assert a.retardo_propagacion_s == pytest.approx(0.239, abs=0.001)


def test_la_trama_llega_hasta_que_pasa_el_retardo():
    a, b = CanalSimulado.crear_enlace(medio="satelite_geo", escala_tiempo=0.5)
    a.enviar(MENSAJE)
    assert b.recibir(timeout=0.01) is None   # todavía viaja (~0.12 s)
    inicio = time.monotonic()
    assert b.recibir(timeout=1.0) == MENSAJE
    assert time.monotonic() - inicio > 0.05


def test_escala_cero_es_instantaneo():
    a, b = CanalSimulado.crear_enlace(medio="satelite_geo", escala_tiempo=0)
    a.enviar(MENSAJE)
    assert b.recibir(timeout=0) == MENSAJE



def test_simplex_solo_transmite_a():
    a, b = CanalSimulado.crear_enlace(sentido=Sentido.SIMPLEX)
    a.enviar(MENSAJE)
    assert b.recibir() == MENSAJE
    with pytest.raises(PermissionError):
        b.enviar(b"ACK")


def _llegada_de_b_tras_a(sentido: Sentido) -> float:
    # medio lento (1000 bps): 100 bytes tardan 0.8 s en salir; escala 0.1 -> 0.08 s
    lento = Medio("lento", True, snr_ref_db=60, distancia_ref_m=0, atenuacion_db_por_m=0,
                  velocidad_bps=1000, factor_velocidad=1, prob_rafaga=0, distancia_tipica_m=0)
    a, b = CanalSimulado.crear_enlace(medio=lento, sentido=sentido, escala_tiempo=0.1)
    inicio = time.monotonic()
    a.enviar(bytes(100))
    b.enviar(bytes(100))
    a.recibir(timeout=1.0)
    return time.monotonic() - inicio


def test_semiduplex_espera_a_que_se_libere_el_medio():
    # dúplex: B sale al mismo tiempo que A (~0.08 s)
    # semidúplex: B espera a que A termine (~0.16 s)
    assert _llegada_de_b_tras_a(Sentido.SEMIDUPLEX) > _llegada_de_b_tras_a(Sentido.DUPLEX) + 0.04



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