from tele_ir_link.deteccion import redundancia_vertical, redundancia_longitudinal, redundancia_ciclica, suma_verificacion


def test_redundancia_vertical_par():
    assert redundancia_vertical(0b01100001, "par") == 1  # tiene 3 unos, falta 1 para que sea par
    assert redundancia_vertical(0b01100011, "par") == 0  # tiene 4 unos, ya es par
    assert redundancia_vertical(0) == 0


def test_redundancia_vertical_impar():
    assert redundancia_vertical(0b01100001, "impar") == 0
    assert redundancia_vertical(0b01100011, "impar") == 1


def test_redundancia_vertical_limite():
    # la paridad NO detecta cuando se dañan 2 bits
    byte_original = 0b01100001
    byte_danado = byte_original ^ 0b00000011  # volteamos 2 bits
    assert redundancia_vertical(byte_danado) == redundancia_vertical(byte_original)
    # con 1 bit dañado sí cambia
    assert redundancia_vertical(byte_original ^ 0b00000001) != redundancia_vertical(byte_original)


def test_redundancia_longitudinal():
    bloque = bytes([0b10110010, 0b01101100, 0b11100001])
    assert redundancia_longitudinal(bloque) == 0b00111111
    assert redundancia_longitudinal(b"") == 0


def test_redundancia_ciclica_diapositivas():
    # el ejemplo de las diapositivas: 1010 con polinomio 1101 da 001
    assert redundancia_ciclica(bytes([0b1010]), 0b1101) == 0b001


def test_redundancia_ciclica_cambia_si_hay_error():
    datos = b"hola"
    residuo_original = redundancia_ciclica(datos, 0x107)
    assert redundancia_ciclica(b"hola!", 0x107) != residuo_original
    assert redundancia_ciclica(b"hula", 0x107) != residuo_original


def test_redundancia_ciclica_residuo_cero():
    # si le pegamos el CRC a los datos, el residuo debe dar 0
    datos = b"hola mundo"
    valor_residuo = redundancia_ciclica(datos, 0x107)
    assert redundancia_ciclica(datos + bytes([valor_residuo]), 0x107) == 0


def test_redundancia_ciclica_si_ve_bytes_intercambiados():
    assert redundancia_ciclica(b"AB", 0x107) != redundancia_ciclica(b"BA", 0x107)


def test_suma_verificacion():
    assert suma_verificacion(b"\x01\x02\x03") == 6
    assert suma_verificacion(b"") == 0


def test_suma_verificacion_limite():
    # la suma de verificación NO ve cuando se intercambian bytes de lugar
    assert suma_verificacion(b"AB") == suma_verificacion(b"BA")


def test_suma_verificacion_cabe_en_1_byte():
    # el contrato dice que el checksum es de 1 byte (0 a 255)
    assert suma_verificacion(bytes([255] * 300)) < 256
    assert suma_verificacion(b"\xff\x02") == 1


def test_nombres_cortos():
    # tramas.py usa estos nombres
    from tele_ir_link import deteccion
    assert deteccion.vrc(0b01100001) == 1
    assert deteccion.lrc(b"\x01\x02") == 3
    assert deteccion.crc(bytes([0b1010]), 0b1101) == 0b001
    assert deteccion.checksum(b"\x01\x02") == 3
