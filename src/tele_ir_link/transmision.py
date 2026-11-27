from __future__ import annotations

from dataclasses import dataclass

BANDERA = 0x7E
ESCAPE = 0x7D
MASCARA_ESCAPE = 0x20


@dataclass(frozen=True)
class ConfigAsincrona:
    bits_datos: int = 8
    paridad: str | None = None  # None, "par" o "impar"
    bits_paro: int = 1          # 1 o 2

    def __post_init__(self) -> None:
        if not 5 <= self.bits_datos <= 8:
            raise ValueError("bits_datos debe estar entre 5 y 8")
        if self.paridad not in (None, "par", "impar"):
            raise ValueError('paridad debe ser None, "par" o "impar"')
        if self.bits_paro not in (1, 2):
            raise ValueError("bits_paro debe ser 1 o 2")

    @property
    def bits_por_caracter(self) -> int:
        bits_paridad = 1 if self.paridad else 0
        return 1 + self.bits_datos + bits_paridad + self.bits_paro

    @property
    def rendimiento(self) -> float:
        return self.bits_datos / self.bits_por_caracter


def _bit_paridad(valor: int, paridad: str) -> int:
    sobra_uno = bin(valor).count("1") % 2
    return sobra_uno if paridad == "par" else 1 - sobra_uno


def entramar_asincrono(datos: bytes,
                       config: ConfigAsincrona = ConfigAsincrona()) -> list[int]:
    """Convierte bytes en la secuencia de bits que va por la línea (LSB primero).

    Si bits_datos es menor que 8, los bits altos de cada byte se descartan.
    """
    bits: list[int] = []
    for byte in datos:
        valor = byte & ((1 << config.bits_datos) - 1)
        bits.append(0)                                  # arranque
        bits += [(valor >> i) & 1 for i in range(config.bits_datos)]
        if config.paridad:
            bits.append(_bit_paridad(valor, config.paridad))
        bits += [1] * config.bits_paro                  # paro
    return bits


@dataclass
class ResultadoAsincrono:
    datos: bytes
    errores_trama: int = 0      # bit de paro que no era 1
    errores_paridad: int = 0


def desentramar_asincrono(
        bits: list[int],
        config: ConfigAsincrona = ConfigAsincrona()) -> ResultadoAsincrono:
    """Receptor start-stop: espera un 0 (arranque) y lee un carácter desde ahí."""
    salida = bytearray()
    resultado = ResultadoAsincrono(b"")
    i = 0
    while i < len(bits):
        if bits[i] == 1:                                # línea en reposo
            i += 1
            continue
        fin = i + config.bits_por_caracter
        if fin > len(bits):                             # carácter incompleto
            break
        datos_bits = bits[i + 1 : i + 1 + config.bits_datos]
        valor = sum(bit << k for k, bit in enumerate(datos_bits))
        j = i + 1 + config.bits_datos
        if config.paridad:
            if bits[j] != _bit_paridad(valor, config.paridad):
                resultado.errores_paridad += 1
            j += 1
        if any(bit != 1 for bit in bits[j:fin]):
            resultado.errores_trama += 1
        salida.append(valor)
        i = fin
    resultado.datos = bytes(salida)
    return resultado


def rellenar(datos: bytes) -> bytes:
    """Byte stuffing: 0x7E -> 7D 5E y 0x7D -> 7D 5D."""
    salida = bytearray()
    for byte in datos:
        if byte in (BANDERA, ESCAPE):
            salida += bytes([ESCAPE, byte ^ MASCARA_ESCAPE])
        else:
            salida.append(byte)
    return bytes(salida)


def quitar_relleno(datos: bytes) -> bytes:
    """Operación inversa de rellenar."""
    salida = bytearray()
    escapado = False
    for byte in datos:
        if escapado:
            salida.append(byte ^ MASCARA_ESCAPE)
            escapado = False
        elif byte == ESCAPE:
            escapado = True
        else:
            salida.append(byte)
    return bytes(salida)


def entramar_sincrono(bloque: bytes) -> bytes:
    """Bloque síncrono: BANDERA + datos rellenados + BANDERA."""
    return bytes([BANDERA]) + rellenar(bloque) + bytes([BANDERA])


def separar_bloques(flujo: bytes) -> list[bytes]:
    """Receptor síncrono: corta el flujo en las banderas y quita el relleno."""
    bloques = []
    for pedazo in flujo.split(bytes([BANDERA])):
        if pedazo:
            bloques.append(quitar_relleno(pedazo))
    return bloques


def rendimiento_sincrono(bytes_datos: int, bytes_control: int) -> float:
    """Bytes útiles entre bytes totales.

    bytes_control agrupa cabecera, CHECK y banderas. No cuenta los bytes extra
    que agrega el relleno, porque dependen del contenido.
    """
    return bytes_datos / (bytes_datos + bytes_control)


def comparar(
        tamanos: list[int], bytes_control: int = 10,
        config: ConfigAsincrona = ConfigAsincrona(),
) -> list[tuple[int, float, float]]:
    """(tamaño de bloque, rendimiento asíncrono, rendimiento síncrono)."""
    return [(n, config.rendimiento, rendimiento_sincrono(n, bytes_control))
            for n in tamanos]