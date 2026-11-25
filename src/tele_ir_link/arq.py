"""Protocolo ARQ (corrección hacia atrás) sobre un Canal.

Tres variantes, todas con la misma interfaz del contrato:

- ``pare_espera``: una trama a la vez; se espera su ACK antes de mandar la siguiente.
- ``retroceda_n``: ventana fija de N tramas; si una falla, se regresa a la primera
  sin confirmar y se reenvía todo desde ahí. El receptor solo acepta en orden.
- ``rechazo_selectivo``: ventana deslizante; solo se reenvían las tramas perdidas o
  dañadas. El receptor guarda las que llegan fuera de orden.

El mensaje se parte en fragmentos y al final se manda una trama de DATOS con 0 bytes
(FIN) para que el receptor sepa que el mensaje terminó.

El ACK lleva el SEQ de la trama confirmada (en retroceda N es acumulativo: confirma
todas hasta esa). El NACK lleva el SEQ de la trama que se pide de nuevo.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from tele_ir_link.canal import Canal, CanalSimulado, ConfigRuido
from tele_ir_link.tramas import MAX_DATOS, TipoTrama, Trama, armar_trama, leer_trama

PARE_ESPERA = "pare_espera"
RETROCEDA_N = "retroceda_n"
RECHAZO_SELECTIVO = "rechazo_selectivo"
MODOS = (PARE_ESPERA, RETROCEDA_N, RECHAZO_SELECTIVO)

TAM_FRAGMENTO = 32
VENTANA = 4
TIMEOUT = 0.2
MAX_REINTENTOS = 30
_PAUSA_SONDEO = 0.0005


@dataclass
class Estadisticas:
    tramas_enviadas: int = 0       # todas las tramas de DATOS que salieron (con repeticiones)
    retransmisiones: int = 0       # cuántas de esas fueron repeticiones
    errores_detectados: int = 0    # tramas dañadas (CHECK falla) vistas por el receptor y por el emisor
    errores_corregidos: int = 0    # tramas distintas que necesitaron reenvío y al final se entregaron
    timeouts: int = 0              # veces que se agotó el temporizador
    tramas_utiles: int = 0         # tramas necesarias sin errores (fragmentos + FIN)

    @property
    def eficiencia(self) -> float:
        """Tramas útiles entre tramas enviadas (1.0 = nada repetido)."""
        if self.tramas_enviadas == 0:
            return 0.0
        return self.tramas_utiles / self.tramas_enviadas


# ---------------------------------------------------------------- utilidades

def _fragmentar(mensaje: bytes, tam: int) -> list[bytes]:
    if not 1 <= tam <= MAX_DATOS:
        raise ValueError(f"tam_fragmento debe estar entre 1 y {MAX_DATOS}")
    partes = [mensaje[i : i + tam] for i in range(0, len(mensaje), tam)]
    partes.append(b"")  # FIN
    return partes


def _validar(modo: str, ventana: int) -> None:
    if modo not in MODOS:
        raise ValueError(f"Modo ARQ desconocido: {modo!r}. Opciones: {list(MODOS)}")
    limite = 128 if modo == RECHAZO_SELECTIVO else 255
    if not 1 <= ventana <= limite:
        raise ValueError(f"ventana debe estar entre 1 y {limite} para {modo}")


def _leer(canal: Canal, metodo: str, timeout: float) -> tuple[str, Trama | None]:
    """Espera una trama hasta ``timeout`` segundos.

    Devuelve ("ok", trama), ("danada", None) o ("nada", None).
    """
    limite = time.monotonic() + timeout
    while True:
        restante = limite - time.monotonic()
        crudo = canal.recibir(max(0.0, min(restante, 0.05)))
        if crudo is not None:
            trama = leer_trama(crudo, metodo)
            return ("ok", trama) if trama is not None else ("danada", None)
        if restante <= 0:
            return "nada", None
        time.sleep(_PAUSA_SONDEO)


def _resolver(seq: int, base: int, siguiente: int) -> int | None:
    """Pasa un SEQ (0-255) al índice absoluto dentro de [base, siguiente)."""
    for k in range(base, siguiente):
        if k % 256 == seq:
            return k
    return None


# ------------------------------------------------------------------- emisor

class _Emisor:
    def __init__(self, canal: Canal, mensaje: bytes, metodo: str, *,
                 ventana: int, timeout: float, max_reintentos: int, tam_fragmento: int) -> None:
        self.canal = canal
        self.metodo = metodo
        self.ventana = ventana
        self.timeout = timeout
        self.max_reintentos = max_reintentos
        self.fragmentos = _fragmentar(mensaje, tam_fragmento)
        self.total = len(self.fragmentos)
        self.stats = Estadisticas(tramas_utiles=self.total)
        self._ya_enviadas: set[int] = set()
        self._reenviadas: set[int] = set()

    def _enviar(self, idx: int) -> None:
        trama = armar_trama(idx % 256, TipoTrama.DATOS, self.fragmentos[idx], self.metodo)
        self.canal.enviar(trama)
        self.stats.tramas_enviadas += 1
        if idx in self._ya_enviadas:
            self.stats.retransmisiones += 1
            self._reenviadas.add(idx)
        self._ya_enviadas.add(idx)

    def _fallo(self, intentos: int) -> None:
        if intentos > self.max_reintentos:
            raise ConnectionError(
                f"Se superó el máximo de {self.max_reintentos} reintentos sin respuesta"
            )

    def correr(self, modo: str) -> Estadisticas:
        if modo == PARE_ESPERA:
            self._pare_espera()
        elif modo == RETROCEDA_N:
            self._retroceda_n()
        else:
            self._rechazo_selectivo()
        self.stats.errores_corregidos = len(self._reenviadas)
        return self.stats

    # -- pare y espere
    def _pare_espera(self) -> None:
        for idx in range(self.total):
            intentos = 0
            while True:
                self._enviar(idx)
                resultado = self._esperar_confirmacion(idx)
                if resultado == "ack":
                    break
                if resultado == "timeout":
                    self.stats.timeouts += 1
                intentos += 1
                self._fallo(intentos)

    def _esperar_confirmacion(self, idx: int) -> str:
        limite = time.monotonic() + self.timeout
        while True:
            estado, t = _leer(self.canal, self.metodo, max(0.0, limite - time.monotonic()))
            if estado == "nada":
                return "timeout"
            if estado == "danada":
                self.stats.errores_detectados += 1
                continue
            if t.seq != idx % 256:
                continue  # confirmación vieja o repetida
            if t.tipo == TipoTrama.ACK:
                return "ack"
            if t.tipo == TipoTrama.NACK:
                return "nack"

    # -- retroceda N
    def _retroceda_n(self) -> None:
        base = siguiente = 0
        intentos = 0
        limite = time.monotonic() + self.timeout
        while base < self.total:
            while siguiente < min(base + self.ventana, self.total):
                self._enviar(siguiente)
                siguiente += 1
            estado, t = _leer(self.canal, self.metodo, max(0.0, limite - time.monotonic()))
            if estado == "danada":
                self.stats.errores_detectados += 1
                continue
            if estado == "ok":
                k = _resolver(t.seq, base, siguiente)
                if k is None:
                    continue
                if t.tipo == TipoTrama.ACK:
                    base = k + 1
                    intentos = 0
                    limite = time.monotonic() + self.timeout
                elif t.tipo == TipoTrama.NACK and k == base:
                    # no cuenta como reintento: varias tramas dañadas de una misma
                    # ventana generan varios NACK seguidos
                    siguiente = base  # regresar y reenviar desde la fallida
                    limite = time.monotonic() + self.timeout
                continue
            # temporizador vencido
            self.stats.timeouts += 1
            intentos += 1
            self._fallo(intentos)
            siguiente = base
            limite = time.monotonic() + self.timeout

    # -- rechazo selectivo
    def _rechazo_selectivo(self) -> None:
        base = siguiente = 0
        confirmadas: set[int] = set()
        limites: dict[int, float] = {}
        intentos: dict[int, int] = {}

        def reenviar(k: int) -> None:
            intentos[k] += 1
            self._fallo(intentos[k])
            self._enviar(k)
            limites[k] = time.monotonic() + self.timeout

        while base < self.total:
            while siguiente < min(base + self.ventana, self.total):
                self._enviar(siguiente)
                limites[siguiente] = time.monotonic() + self.timeout
                intentos[siguiente] = 0
                siguiente += 1

            proximo = min(limites[k] for k in range(base, siguiente) if k not in confirmadas)
            estado, t = _leer(self.canal, self.metodo, max(0.0, proximo - time.monotonic()))
            if estado == "danada":
                self.stats.errores_detectados += 1
            elif estado == "ok":
                k = _resolver(t.seq, base, siguiente)
                if k is not None and k not in confirmadas:
                    if t.tipo == TipoTrama.ACK:
                        confirmadas.add(k)
                        while base in confirmadas:
                            base += 1
                    elif t.tipo == TipoTrama.NACK:
                        reenviar(k)

            ahora = time.monotonic()
            for k in range(base, siguiente):
                if k not in confirmadas and limites[k] <= ahora:
                    self.stats.timeouts += 1
                    reenviar(k)


def enviar_mensaje(canal: Canal, mensaje: bytes, modo: str, metodo: str, *,
                   ventana: int = VENTANA, timeout: float = TIMEOUT,
                   max_reintentos: int = MAX_REINTENTOS,
                   tam_fragmento: int = TAM_FRAGMENTO) -> Estadisticas:
    """Manda ``mensaje`` por ``canal`` con el ARQ ``modo`` y devuelve las estadísticas.

    Lanza ConnectionError si una trama supera ``max_reintentos`` sin confirmarse.
    """
    _validar(modo, ventana)
    emisor = _Emisor(canal, mensaje, metodo, ventana=ventana, timeout=timeout,
                     max_reintentos=max_reintentos, tam_fragmento=tam_fragmento)
    return emisor.correr(modo)


# ----------------------------------------------------------------- receptor

def _responder(canal: Canal, metodo: str, tipo: TipoTrama, seq: int) -> None:
    canal.enviar(armar_trama(seq % 256, tipo, b"", metodo))


def _despedida(canal: Canal, metodo: str, espera: float,
               terminado: threading.Event | None) -> None:
    """Tras el FIN sigue confirmando repeticiones por si el emisor no recibió el último ACK.

    Dura ``espera`` segundos, o menos si ``terminado`` se activa (el emisor ya acabó).
    """
    limite = time.monotonic() + espera
    while time.monotonic() < limite and not (terminado is not None and terminado.is_set()):
        estado, t = _leer(canal, metodo, min(0.05, max(0.0, limite - time.monotonic())))
        if estado == "ok" and t.tipo == TipoTrama.DATOS:
            _responder(canal, metodo, TipoTrama.ACK, t.seq)


def _recibir_en_orden(canal: Canal, metodo: str, inactividad: float, espera_final: float,
                      terminado: threading.Event | None, stats: Estadisticas) -> bytes:
    """Receptor de pare y espere y de retroceda N (solo acepta la trama esperada)."""
    esperada = 0
    partes: list[bytes] = []
    while True:
        estado, t = _leer(canal, metodo, inactividad)
        if estado == "nada":
            raise TimeoutError("El emisor dejó de mandar tramas")
        if estado == "danada":
            stats.errores_detectados += 1
            _responder(canal, metodo, TipoTrama.NACK, esperada)
            continue
        if t.tipo != TipoTrama.DATOS:
            continue
        if t.seq == esperada % 256:
            _responder(canal, metodo, TipoTrama.ACK, t.seq)
            esperada += 1
            if not t.datos:
                break
            partes.append(t.datos)
        elif esperada > 0:
            # repetida o fuera de orden: se vuelve a confirmar la última en orden
            _responder(canal, metodo, TipoTrama.ACK, esperada - 1)
    _despedida(canal, metodo, espera_final, terminado)
    return b"".join(partes)


def _recibir_selectivo(canal: Canal, metodo: str, inactividad: float, espera_final: float,
                       terminado: threading.Event | None, ventana: int,
                       stats: Estadisticas) -> bytes:
    """Receptor de rechazo selectivo: guarda las tramas fuera de orden dentro de la ventana."""
    base = 0
    guardadas: dict[int, bytes] = {}
    partes: list[bytes] = []
    fin = False
    while not fin:
        estado, t = _leer(canal, metodo, inactividad)
        if estado == "nada":
            raise TimeoutError("El emisor dejó de mandar tramas")
        if estado == "danada":
            stats.errores_detectados += 1
            continue  # sin SEQ confiable; el temporizador del emisor la repone
        if t.tipo != TipoTrama.DATOS:
            continue
        desfase = (t.seq - base) % 256
        if desfase < ventana:
            guardadas.setdefault(base + desfase, t.datos)
            _responder(canal, metodo, TipoTrama.ACK, t.seq)
            while base in guardadas:
                datos = guardadas.pop(base)
                base += 1
                if not datos:
                    fin = True
                    break
                partes.append(datos)
        elif desfase >= 256 - ventana:
            _responder(canal, metodo, TipoTrama.ACK, t.seq)  # ya entregada: reconfirmar
    _despedida(canal, metodo, espera_final, terminado)
    return b"".join(partes)


def recibir_mensaje(canal: Canal, modo: str, metodo: str, *,
                    ventana: int = VENTANA, timeout: float = TIMEOUT,
                    max_reintentos: int = MAX_REINTENTOS,
                    stats: Estadisticas | None = None,
                    terminado: threading.Event | None = None) -> bytes:
    """Recibe un mensaje completo mandado con ``enviar_mensaje`` y devuelve sus bytes.

    ``ventana`` y ``timeout`` deben coincidir con los del emisor. Si se pasa ``stats``,
    se le suman las tramas dañadas que detectó el receptor. Lanza TimeoutError si el
    emisor deja de mandar tramas.

    Al recibir el FIN, el receptor sigue confirmando repeticiones hasta
    ``timeout * max_reintentos`` segundos (el máximo que el emisor puede seguir
    reintentando), salvo que se active ``terminado``.
    """
    _validar(modo, ventana)
    stats = stats if stats is not None else Estadisticas()
    inactividad = timeout * max_reintentos
    if modo == RECHAZO_SELECTIVO:
        return _recibir_selectivo(canal, metodo, inactividad, inactividad, terminado, ventana, stats)
    return _recibir_en_orden(canal, metodo, inactividad, inactividad, terminado, stats)


# ------------------------------------------------------- simulación completa

def transmitir_simulado(mensaje: bytes, modo: str, metodo: str,
                        config: ConfigRuido | None = None, semilla: int | None = None,
                        **opciones) -> tuple[bytes, Estadisticas]:
    """Corre emisor y receptor en dos hilos sobre un CanalSimulado.

    Devuelve (mensaje recibido, estadísticas). ``opciones`` se pasa a ambos lados
    (ventana, timeout, max_reintentos); ``tam_fragmento`` solo al emisor.
    Con hilos, el orden del ruido no es del todo repetible aunque se fije la semilla.
    """
    emisor_canal, receptor_canal = CanalSimulado.crear_enlace(config, semilla)
    opciones_rx = {k: v for k, v in opciones.items() if k != "tam_fragmento"}
    stats_rx = Estadisticas()
    terminado = threading.Event()
    resultado: dict[str, object] = {}

    def lado_receptor() -> None:
        try:
            resultado["datos"] = recibir_mensaje(receptor_canal, modo, metodo,
                                                 stats=stats_rx, terminado=terminado,
                                                 **opciones_rx)
        except Exception as error:  # se reporta en el hilo principal
            resultado["error"] = error

    hilo = threading.Thread(target=lado_receptor, daemon=True)
    hilo.start()
    try:
        stats = enviar_mensaje(emisor_canal, mensaje, modo, metodo, **opciones)
    finally:
        terminado.set()  # el receptor ya no tiene a quién reconfirmar
    hilo.join()
    if "error" in resultado:
        raise resultado["error"]  # type: ignore[misc]
    stats.errores_detectados += stats_rx.errores_detectados
    return resultado["datos"], stats  # type: ignore[return-value]
