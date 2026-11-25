# Métodos para detectar errores: VRC, LRC, CRC y suma de verificación (checksum)


def redundancia_vertical(byte, paridad="par"):
    # VRC (redundancia vertical) = bit de paridad de un solo byte
    # primero contamos cuántos unos tiene el byte
    cantidad_unos = bin(byte).count("1")

    # para paridad par: el bit se pone para que el total de unos quede par
    if cantidad_unos % 2 == 0:
        bit_paridad = 0
    else:
        bit_paridad = 1

    if paridad == "par":
        return bit_paridad
    else:
        # para paridad impar es lo contrario
        return 1 - bit_paridad


def redundancia_longitudinal(bloque):
    # LRC (redundancia longitudinal) = paridad par por columna de todo el bloque
    # sacar la paridad de cada columna es lo mismo que hacer XOR
    # de todos los bytes uno por uno
    bcc = 0
    for byte in bloque:
        bcc = bcc ^ byte
    return bcc


def redundancia_ciclica(datos, polinomio):
    # División con XOR (como la de las diapositivas)
    # El polinomio se pone completo, por ejemplo 0b1101

    # el grado es cuántos bits tiene el residuo (polinomio 1101 -> grado 3)
    grado = len(bin(polinomio)) - 3

    # pasamos los datos a un texto de unos y ceros
    texto_bits = ""
    for byte in datos:
        texto_bits = texto_bits + format(byte, "08b")

    # se le agregan ceros al final (tantos como el grado)
    texto_bits = texto_bits + "0" * grado

    # vamos bajando bit por bit, igual que en la división a mano
    residuo = 0
    for caracter in texto_bits:
        residuo = residuo * 2 + int(caracter)
        # si ya se nos prendió el bit de hasta arriba, hacemos XOR con el polinomio
        if residuo >> grado == 1:
            residuo = residuo ^ polinomio

    return residuo


def suma_verificacion(datos):
    # Suma de verificación (checksum) = sumar todos los bytes
    # el % 256 es para que el resultado quepa en 1 byte (como dice el contrato)
    suma_total = 0
    for byte in datos:
        suma_total = suma_total + byte
    return suma_total % 256


# Nombres cortos que usa tramas.py (son las mismas funciones de arriba)
vrc = redundancia_vertical
lrc = redundancia_longitudinal
crc = redundancia_ciclica
checksum = suma_verificacion
