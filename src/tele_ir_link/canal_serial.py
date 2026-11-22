import time

import serial 

from tele_ir_link.canal import Canal

INICIO = 0x7E
LARGO_CABECERA = 4
POS_LONG = 3

BYTES_CHECK = {
   "ninguno": 0,
    "vrc": 1,
    "lrc": 1,
    "checksum": 1,
    "crc": 2, 
}

class CanalSerial(Canal):
    def __init__(self, puerto: str, metodo: str, baudios: int = 115200, esperar_arranque_s: float = 2.0, silencio_max_s: float = 0.5) -> None:
        if metodo not in BYTES_CHECK:
            raise ValueError(f"Metodo de chequeo desconocido: {metodo!r}")
        self._largo_check = BYTES_CHECK[metodo]
        self._silencio_max_s = silencio_max_s
        self._buffer = bytearray()

        self._ser = serial.Serial(puerto, baudios, timeout=0.05)
        time.sleep(esperar_arranque_s)
        self._ser.reset_input_buffer()

    def enviar(self, datos: bytes) -> None:
        if len(datos) % 2:
            datos = datos + b"\x00"
        self._ser.write(datos)
        self._ser.flush()

    def recibir(self, timeout: float = 1.0) -> bytes | None:
        limite = time.monotonic() + timeout

        if not self._buscar_inicio(limite):
            return None

        if not self._llenar(LARGO_CABECERA):
            return self._descartar_inicio()

        largo = LARGO_CABECERA + self._buffer[POS_LONG] + self._largo_check
        if not self._llenar(largo):
            return self._descartar_inicio()
        trama = bytes(self._buffer[:largo])
        del self._buffer[:largo]
        return trama

    def cerrar(self) -> None:
        self._ser.close()

    def _buscar_inicio(self, limite: float) -> bool:
        while True:
            i = self._buffer.find(INICIO)
            if i >= 0:
                del self._buffer[:i]
                return True
            self._buffer.clear()
            if not self._llenar(1, limite):
                return False

    def _llenar(self, n: int, limite: float | None = None) -> bool:
        ultimo = time.monotonic()
        while len(self._buffer) < n:
            ahora = time.monotonic()
            if limite is not None and ahora >= limite:
                return False
            if limite is None and ahora - ultimo > self._silencio_max_s:    
                return False

            nuevos = self._ser.read(self._ser.in_waiting or 1)
            if nuevos:
                self._buffer += nuevos
                ultimo = time.monotonic()
        return True

    def _descartar_inicio(self) -> None:
        del self._buffer[:1]
        return None

    def __enter__(self) -> "CanalSerial":
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()
