from __future__ import annotations

import math 
import random
import threading
import time
from abc import ABC,abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum

VELOCIDAD_LUZ = 299_792_458.0  # m/s

class Canal(ABC):
    @abstractmethod
    def enviar(self, datos:bytes) -> None:
        """Manda una secuencia de bytes al otro extremo"""

    @abstractmethod
    def recibir(self, timeout: float = 1.0) -> bytes | None:
        """Devuelve lo siguiente que llego, o None si no llego nada a tiempo"""

@dataclass
class ConfigRuido:
    """Perturbaciones extra, ademas de las que ya trea el medio"""

    # Ruido aleatorio (blanco): probabilidad de que cada bit se voltee
    prob_bit: float = 0.0
    # Ruido de impulso: probabilidad de que una transmisión sufra una ráfaga
    prob_rafaga: float = 0.0
    # Cuántos bits seguidos daña una ráfaga
    largo_rafaga: int = 8
    # Probabilidad de que una transmisión no llegue (señal perdida)
    prob_perdida: float = 0.0

@dataclass(frozen=True)
class Medio:
    nombre: str
    guiado: bool
    snr_ref_db: float             # S/N a distancia_ref_m
    distancia_ref_m: float        # guiado: 0 (salida del transmisor)
    atenuacion_db_por_m: float    # solo guiados
    velocidad_bps: float          # bits por segundo
    factor_velocidad: float       # velocidad de propagación / velocidad de la luz
    prob_rafaga: float            # qué tanto le afecta el ruido de impulso
    distancia_tipica_m: float     # distancia "normal" de uso

    def perdida_db(self, distancia_m: float) -> float:
        if self.guiado:
            return self.atenuacion_db_por_m * distancia_m
        if distancia_m <= self.distancia_ref_m:
            return 0.0
        return 20 * math.log10(distancia_m / self.distancia_ref_m)

    def snr_db(self, distancia_m: float) -> float:
        return self.snr_ref_db - self.perdida_db(distancia_m)

    def prob_error_bit(self, distancia_m: float) -> float:
        snr_linea = 10 ** (self.snr_db(distancia_m) / 10)
        return 0.5 * math.erfc(math.sqrt(snr_linea))

    def retardo_propagacion_s(self, distancia_m: float) -> float:
        return distancia_m / (self.factor_velocidad * VELOCIDAD_LUZ)

    def tiempo_transmision_s(self, n_bytes: int) -> float:
        return n_bytes* 8 / self.velocidad_bps


MEDIOS: dict[str, Medio] = {
    "par_trenzado_utp": Medio(
        "Par trenzado UTP", guiado=True, snr_ref_db=30, distancia_ref_m=0,
        atenuacion_db_por_m=0.2, velocidad_bps=100e6, factor_velocidad=0.65,
        prob_rafaga=0.02, distancia_tipica_m=100,
    ),
    "par_trenzado_stp": Medio(
        "Par trenzado STP", guiado=True, snr_ref_db=33, distancia_ref_m=0,
        atenuacion_db_por_m=0.2, velocidad_bps=100e6, factor_velocidad=0.65,
        prob_rafaga=0.005, distancia_tipica_m=100,
    ),
    "coaxial": Medio(
        "Coaxial (banda base, 50 Ω)", guiado=True, snr_ref_db=20, distancia_ref_m=0,
        atenuacion_db_por_m=0.05, velocidad_bps=10e6, factor_velocidad=0.66,
        prob_rafaga=0.002, distancia_tipica_m=185,
    ),
    "fibra_multimodo": Medio(
        "Fibra óptica multimodo", guiado=True, snr_ref_db=25, distancia_ref_m=0,
        atenuacion_db_por_m=0.003, velocidad_bps=1e9, factor_velocidad=0.68,
        prob_rafaga=0.0, distancia_tipica_m=2_000,
    ),
    "fibra_monomodo": Medio(
        "Fibra óptica monomodo", guiado=True, snr_ref_db=25, distancia_ref_m=0,
        atenuacion_db_por_m=0.00035, velocidad_bps=10e9, factor_velocidad=0.68,
        prob_rafaga=0.0, distancia_tipica_m=40_000,
    ),
    "infrarrojo": Medio(
        "Infrarrojo (punto a punto)", guiado=False, snr_ref_db=30, distancia_ref_m=0.1,
        atenuacion_db_por_m=0.0, velocidad_bps=115_200, factor_velocidad=1.0,
        prob_rafaga=0.01, distancia_tipica_m=1,
    ),
    "satelite_geo": Medio(
        "Satélite geoestacionario", guiado=False, snr_ref_db=12,
        distancia_ref_m=2 * 35_786_000, atenuacion_db_por_m=0.0,
        velocidad_bps=10e6, factor_velocidad=1.0, prob_rafaga=0.005,
        distancia_tipica_m=2 * 35_786_000,  # subida + bajada
    ),
}


class Sentido(Enum):
    SIMPLEX = "simplex"        # solo A -> B
    SEMIDUPLEX = "semiduplex"  # ambos, pero uno a la vez (comparten el medio)
    DUPLEX = "duplex"  # ambos, simultáneamente

class _Enlace:
    def __init__(self, config: ConfigRuido, rng: random.Random, medio: Medio | None,
                 distancia_m: float, sentido: Sentido, escala_tiempo: float) -> None:
        self.config = config
        self.rng = rng
        self.medio = medio
        self.distancia_m = distancia_m
        self.sentido = sentido
        self.escala_tiempo = escala_tiempo
        self.candado = threading.Lock()
        # instante (reloj real) en que el medio queda libre, por dirección
        self.libre_en: dict[str, float] = {"a": 0.0, "b": 0.0}

    def prob_error_bit(self) -> float:
        p_medio = self.medio.prob_error_bit(self.distancia_m) if self.medio else 0.0
        return min(self.config.prob_bit + p_medio, 1.0)

    def prob_rafaga(self) -> float:
        p_medio = self.medio.prob_rafaga if self.medio else 0.0
        return min(self.config.prob_rafaga + p_medio, 1.0)

    def reservar(self, lado: str, n_bytes: int) -> float:
        if self.medio is None:
            return 0.0
        clave = "a" if self.sentido is Sentido.SEMIDUPLEX else lado
        ahora = time.monotonic()
        inicio = max(ahora, self.libre_en[clave])
        fin = inicio + self.medio.tiempo_transmision_s(n_bytes) * self.escala_tiempo
        self.libre_en[clave] = fin
        return fin + self.medio.retardo_propagacion_s(self.distancia_m) * self.escala_tiempo

class CanalSimulado(Canal):
    def __init__(self, enlace: _Enlace, lado: str) -> None:
        self._enlace = enlace
        self._lado = lado
        self._entrada: deque[tuple[float, bytes]] = deque()
        self._otro: CanalSimulado | None = None
        self.bits_enviados = 0
        self.bits_volteados = 0

    @classmethod
    def crear_enlace(cls, config: ConfigRuido | None = None, semilla:int | None = None, * ,
                    medio: Medio | str | None = None,
                    distancia_m: float | None = None, sentido: Sentido = Sentido.DUPLEX,
                    escala_tiempo: float = 1.0) -> tuple[CanalSimulado, CanalSimulado]:
        if isinstance(medio, str):
            medio = MEDIOS[medio]
        if distancia_m is None:
            distancia_m = medio.distancia_tipica_m if medio else 0.0
        enlace = _Enlace(config or ConfigRuido(), random.Random(semilla), medio, distancia_m, sentido,
                         escala_tiempo)
        a = cls(enlace, "a")
        b = cls(enlace, "b")
        a._otro = b
        b._otro = a
        return a, b

    @property
    def prob_error_bit(self) -> float:
        return self._enlace.prob_error_bit()

    @property
    def snr_db(self) -> float | None:
        e = self._enlace
        return e.medio.snr_db(e.distancia_m) if e.medio else None

    @property
    def retardo_propagacion_s(self) -> float:
        e = self._enlace
        return e.medio.retardo_propagacion_s(e.distancia_m) if e.medio else 0.0

    def enviar(self, datos: bytes) -> None:
        if self._otro is None:
            raise RuntimeError("El otro extremo del canal no está conectado")
        e = self._enlace
        if e.sentido is Sentido.SIMPLEX and self._lado == "b":
            raise PermissionError("Enlace simplex: solo el extremo A puede transmitir")

        with e.candado:
            self.bits_enviados += len(datos) * 8
            llegada = e.reservar(self._lado, len(datos))
            if e.rng.random() < e.config.prob_perdida:
                return
            senal = bytearray(datos)
            self._aplicar_ruido_aleatorio(senal)
            self._aplicar_ruido_impulsivo(senal)
            self._otro._entrada.append((llegada, bytes(senal)))

    def recibir(self, timeout: float = 1.0) -> bytes | None:
        if not self._entrada:
            return None
        llegada, datos = self._entrada[0]
        espera = llegada - time.monotonic()
        if espera > timeout:
            time.sleep(max(timeout, 0.0))
            return None
        if espera > 0:
            time.sleep(espera)
        self._entrada.popleft()
        return datos

    def _voltear_bit(self, senal: bytearray, posicion: int) -> None:
        indice_byte, indice_bit = divmod(posicion, 8)
        senal[indice_byte] ^= 1 << (7 - indice_bit)
        self.bits_volteados += 1

    def _aplicar_ruido_aleatorio(self, senal: bytearray) -> None:
        p = self._enlace.prob_error_bit()
        if p == 0:
            return
        rng = self._enlace.rng
        for posicion in range(len(senal) * 8):
            if rng.random() < p:
                self._voltear_bit(senal, posicion)

    def _aplicar_ruido_impulsivo(self, senal: bytearray) -> None:
        rng = self._enlace.rng
        if not senal or rng.random() >= self._enlace.prob_rafaga():
            return
        total_bit = len(senal) * 8
        inicio = rng.randrange(total_bit)
        fin = min(inicio + self._enlace.config.largo_rafaga, total_bit)
        for posicion in range(inicio, fin):
            self._voltear_bit(senal, posicion)

        