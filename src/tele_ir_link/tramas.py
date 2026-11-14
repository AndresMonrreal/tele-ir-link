from __future__ import annotations

from dataclasses import dataclass 
from enum import IntEnum
from functools import reduce
from operator import xor
from typing import Callable

from tele_ir_link import deteccion

INICIO = 0x7E
TAM_ENCABEZADO = 4
MAX_DATOS = 255
POLINOMIO_CRC16 = 0x11021

class TipoTrama(IntEnum):
    DATOS = 0
    ACK = 1
    NACK = 2

@dataclass(frozen = True)
class Trama:
    seq: int
    tipo: TipoTrama
    datos: bytes

@dataclass(frozen = True)
class Metodo:
    tamano: int
    calcular: Callable[[bytes], int]

def _paridad_bloque(contenido: bytes) -> int:
    return reduce(xor, (deteccion.vrc(b) for b in contenido), 0)

METODOS: dict[str,Metodo] = {
    "ninguno": Metodo(0, lambda contenido: 0),
    "vrc": Metodo(1, _paridad_bloque),
    "lrc": Metodo(1, lambda contenido: deteccion.lrc(contenido)),
    "checksum": Metodo(1, lambda contenido: deteccion.checksum(contenido)),
    "crc": Metodo(2, lambda contenido: deteccion.crc(contenido, POLINOMIO_CRC16)),
}

def _obtener_metodo(metodo: str) -> Metodo:
    try:
        return METODOS[metodo]
    except KeyError:
        raise ValueError(f"Metodo desconocido: {metodo!r}. Opciones: {list(METODOS)}") from None

def armar_trama(seq: int, tipo: TipoTrama, datos: bytes, metodos: str) -> bytes:
    if not 0 <= seq <= 255:
        raise ValueError(f"SEQ debe estar entre 0 y 255, llegó {seq}")
    if len(datos) > MAX_DATOS:
          raise ValueError(f"Máximo {MAX_DATOS} bytes de datos por trama, llegaron {len(datos)}")
    m = _obtener_metodo(metodos)
    contenido = bytes([seq, tipo, len(datos)]) + datos
    check = m.calcular(contenido).to_bytes(m.tamano, "big")
    return bytes([INICIO]) + contenido + check

def leer_trama(crudo: bytes, metodo:str) -> Trama | None:
    m = _obtener_metodo(metodo)

    if len(crudo) < TAM_ENCABEZADO + m.tamano or crudo[0] != INICIO:
        return None

    largo = crudo[3]

    if len(crudo) != TAM_ENCABEZADO + largo + m.tamano:
        return None

    contenido = crudo[1 : TAM_ENCABEZADO + largo]
    check_recibido = int.from_bytes(crudo[TAM_ENCABEZADO + largo :], "big")
    if m.calcular(contenido) != check_recibido:
        return None

    try:
        tipo = TipoTrama(crudo[2])
    except ValueError:
        return None

    return Trama(
        seq=crudo[1],
        tipo=tipo,
        datos=crudo[TAM_ENCABEZADO : TAM_ENCABEZADO + largo],
    )