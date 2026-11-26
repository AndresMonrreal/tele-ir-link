from tele_ir_link.hamming import codificar, decodificar


def test_codificar():
    # datos 1011 -> 0110011
    assert codificar(0b1011) == 0b0110011


def test_sin_error():
    for numero in range(16):
        assert decodificar(codificar(numero)) == (numero, 0)


def test_corrige_un_error():
    # probamos con todos los datos y volteando cada una de las 7 posiciones
    for numero in range(16):
        codigo = codificar(numero)
        for posicion in range(1, 8):
            codigo_danado = codigo ^ (1 << (7 - posicion))
            assert decodificar(codigo_danado) == (numero, posicion)


def test_limite_dos_errores():
    # Hamming solo corrige 1 error, con 2 se equivoca
    codigo = codificar(0b1011)
    codigo_danado = codigo ^ (1 << 4) ^ (1 << 1)  # volteamos las posiciones 3 y 6
    datos, posicion_error = decodificar(codigo_danado)
    assert datos != 0b1011
