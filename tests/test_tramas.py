import pytest

from tele_ir_link.tramas import TipoTrama, armar_trama, leer_trama


def test_ida_y_vuelta_sin_ruido():
    crudo = armar_trama(5, TipoTrama.DATOS, b"HOLA", "ninguno")
    trama = leer_trama(crudo, "ninguno")
    assert trama is not None
    assert trama.seq == 5
    assert trama.tipo == TipoTrama.DATOS
    assert trama.datos == b"HOLA"


def test_formato_de_bytes():
    crudo = armar_trama(1, TipoTrama.ACK, b"", "ninguno")
    assert crudo == bytes([0x7E, 1, 1, 0])


def test_inicio_incorrecto_se_rechaza():
    crudo = bytearray(armar_trama(0, TipoTrama.DATOS, b"A", "ninguno"))
    crudo[0] = 0x00
    assert leer_trama(bytes(crudo), "ninguno") is None


def test_largo_incorrecto_se_rechaza():
    crudo = armar_trama(0, TipoTrama.DATOS, b"ABC", "ninguno")
    assert leer_trama(crudo[:-1], "ninguno") is None


def test_metodo_desconocido():
    with pytest.raises(ValueError):
        armar_trama(0, TipoTrama.DATOS, b"A", "md5")