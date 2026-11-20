import sys
import time

import serial

BAUDIOS = 115200
MENSAJE = bytes([0x7E, 0x00, 0x00, 0x02, 0x48, 0x69]) * 5  # 30 bytes = 15 tramas NEC
ESPERA_S = 6  # tiempo de escucha tras mandar


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    puerto_tx, puerto_rx = sys.argv[1], sys.argv[2]

    with serial.Serial(puerto_tx, BAUDIOS, timeout=0.1) as tx, serial.Serial(
        puerto_rx, BAUDIOS, timeout=0.1
    ) as rx:
        time.sleep(2)  # abrir los puertos suele reiniciar las placas
        tx.reset_input_buffer()
        rx.reset_input_buffer()

        tx.write(MENSAJE)
        tx.flush()
        print(f"Enviado por {puerto_tx}: {len(MENSAJE)} bytes")
        print(MENSAJE.hex(" "))

        recibido = bytearray()
        inicio = time.monotonic()
        while time.monotonic() - inicio < ESPERA_S:
            recibido += rx.read(64)

        print(f"Recibido en {puerto_rx}: {len(recibido)} bytes")
        print(recibido.hex(" "))


if __name__ == "__main__":
    main()