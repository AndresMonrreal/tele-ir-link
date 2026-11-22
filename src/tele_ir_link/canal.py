from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass 


class Canal(ABC):
    @abstractmethod
    def enviar(self, datos: bytes) -> None:
        """Manda una secuencia de bytes al otro extremo"""

    @abstractmethod
    def recibir(self, timeout: float = 1.0) -> bytes | None:
        """Devuelve lo siguiente que llegó, o None si no llegó nada a tiempo"""

@dataclass 
class ConfigRuido:

    # Ruido aleatorio (blanco): probabilidad de que cada bit se voltee
    prob_bit: float = 0.0
    # Ruido de impulso: probabilidad de que una transmisión sufra una ráfaga
    prob_rafaga: float = 0.0
    # Cuántos bits seguidos daña una ráfaga
    largo_rafaga: int = 8
    # Atenuación: distancia simulada entre emisor y receptor
    distancia_cm: float = 0.0
    # Distancia a la que la atenuación llega a su máximo
    alcance_cm: float = 100.0
    # Probabilidad extra de error por bit cuando distancia >= alcance
    prob_bit_max_atenuacion: float = 0.05
    # Probabilidad de que una transmisión no llegue (señal perdida)
    prob_perdida: float = 0.0

class CanalSimulado:

    def __init__(self, config: ConfigRuido, rng: random.Random) -> None:
        self.config = config
        self._rng = rng
        self._entrada: deque[bytes] = deque()
        self._otro: CanalSimulado | None = None
        self.bits_enviados = 0
        self.bits_volteados = 0

    @classmethod
    def crear_enlace(cls, config: ConfigRuido | None = None, semilla: int | None = None) -> tuple[CanalSimulado, CanalSimulado]:
        config = config or ConfigRuido()
        rng = random.Random(semilla)
        a = cls(config,rng)
        b = cls(config,rng)
        a. _otro = b
        b. _otro = a
        return a,b

    def enviar(self, datos: bytes) -> None:
        if self._otro is None:
            raise RuntimeError("Canal sin conectar: créalo con CanalSimulado.crear_enlace()")

        self.bits_enviados += len(datos) * 8

        if self._rng.random() < self.config.prob_perdida:
            return

        senal = bytearray(datos)
        self._aplicar_ruido_aleatorio(senal)
        self._aplicar_ruido_impulsivo(senal)
        self._otro._entrada.append(bytes(senal))

    def recibir(self, timeout: float = 1.0) -> bytes | None:
        if self._entrada:
            return self._entrada.popleft()
        return None

    def _prob_error_por_bit(self) -> float:
        c = self.config
        factor_distancia = min(c.distancia_cm / c.alcance_cm, 1.0)
        return min(c.prob_bit + factor_distancia * c.prob_bit_max_atenuacion, 1.0)

    def _voltear_bit(self, senal: bytearray, posicion: int) -> None:
        indice_byte, indice_bit = divmod(posicion, 8)
        senal[indice_byte] ^= 1 << (7 - indice_bit)
        self.bits_volteados += 1

    def _aplicar_ruido_aleatorio(self, senal: bytearray) -> None:
        p = self._prob_error_por_bit()
        if p == 0:
            return
        for posicion in range(len(senal) * 8):
            if self._rng.random() < p:
                self._voltear_bit(senal, posicion)

    def _aplicar_ruido_impulsivo(self, senal: bytearray) -> None:
        if not senal or self._rng.random() >= self.config.prob_rafaga:
            return
        total_bits = len(senal) * 8
        inicio = self._rng.randrange(total_bits)
        fin = min(inicio + self.config.largo_rafaga, total_bits)
        for posicion in range(inicio, fin):
            self._voltear_bit(senal, posicion)


