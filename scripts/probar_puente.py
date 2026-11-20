import sys 
import time

import serial

BAUDIOS = 115200
MENSAJE_PRUEBA = bytes([0x7E, 0x00, 0x00, 0x02, 0x48, 0x69]) * 20

def abrir(puerto: str) -> serial.Serial:
    ser = serial.Serial(puerto, BAUDIOS, timeout=0.2)
    time.sleep(2)
    ser.reset_input_buffer()
    return ser

def escuchar(ser: serial.Serial, segundos: float | None = None) -> None:
    print("Escuchando...")
    inicio = time.monotonic()
    while segundos is None or time.monotonic() - inicio < segundos:
        datos = ser.read(64)
        if datos:
            print("Recibido:", datos.hex(" "))

def enviar(ser: serial.Serial) -> None:
    ser.write(MENSAJE_PRUEBA)
    ser.flush()
    print("Enviado: ", MENSAJE_PRUEBA.hex(" "))
    print("Esperando 4 s por si el receptor propio lo escucha...")
    escuchar(ser, segundos=4)

def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in ("escuchar", "enviar"):
        print(__doc__)
        sys.exit(1)

    puerto, modo = sys.argv[1], sys.argv[2]
    with abrir(puerto) as ser:
        try:
            if modo == "escuchar":
                escuchar(ser)
            else:
                enviar(ser)
        except KeyboardInterrupt:
            print("\nFin")

if __name__ == "__main__":
    main()