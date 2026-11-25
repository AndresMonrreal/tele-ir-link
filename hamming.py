# Corrección de errores: código Hamming de 7 bits (4 de datos + 3 de paridad)
#
# Las posiciones van de 1 a 7, de izquierda a derecha:
#
#   posición:  1      2      3      4      5      6      7
#   bit:       par1   par2   dato1  par4   dato2  dato3  dato4
#
# par1 revisa las posiciones 1, 3, 5, 7
# par2 revisa las posiciones 2, 3, 6, 7
# par4 revisa las posiciones 4, 5, 6, 7


def codificar(nibble):
    # nibble = número de 4 bits (de 0 a 15)
    # sacamos cada bit de los datos
    dato1 = (nibble >> 3) & 1
    dato2 = (nibble >> 2) & 1
    dato3 = (nibble >> 1) & 1
    dato4 = nibble & 1

    # bits de paridad (paridad par, se calculan con XOR)
    par1 = dato1 ^ dato2 ^ dato4
    par2 = dato1 ^ dato3 ^ dato4
    par4 = dato2 ^ dato3 ^ dato4

    # los acomodamos en su posición y armamos el número de 7 bits
    lista_bits = [par1, par2, dato1, par4, dato2, dato3, dato4]
    codigo = 0
    for bit in lista_bits:
        codigo = codigo * 2 + bit
    return codigo


def decodificar(codigo):
    # codigo = número de 7 bits
    # lo pasamos a una lista de bits
    # (agregamos un 0 al inicio para que lista_bits[1] sea la posición 1)
    texto_bits = format(codigo, "07b")
    lista_bits = [0]
    for caracter in texto_bits:
        lista_bits.append(int(caracter))

    # revisamos cada grupo de paridad
    revision1 = lista_bits[1] ^ lista_bits[3] ^ lista_bits[5] ^ lista_bits[7]
    revision2 = lista_bits[2] ^ lista_bits[3] ^ lista_bits[6] ^ lista_bits[7]
    revision4 = lista_bits[4] ^ lista_bits[5] ^ lista_bits[6] ^ lista_bits[7]

    # juntando las 3 revisiones nos da la posición del error (0 = no hubo error)
    posicion_error = revision4 * 4 + revision2 * 2 + revision1

    # si hubo error, volteamos ese bit para corregirlo
    if posicion_error != 0:
        lista_bits[posicion_error] = 1 - lista_bits[posicion_error]

    # los datos están en las posiciones 3, 5, 6 y 7
    datos = lista_bits[3] * 8 + lista_bits[5] * 4 + lista_bits[6] * 2 + lista_bits[7]

    return datos, posicion_error
