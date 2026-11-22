import sys 

from tele_ir_link.canal_serial import CanalSerial
from tele_ir_link.tramas import TipoTrama, armar_trama, leer_trama

METODO = "ninguno"
CANTIDAD = 20
DATOS = b"Hola TELE"
TIMEOUT_S = 3.0

def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    puerto_tx, puerto_rx = sys.argv[1], sys.argv[2]
    buenas = danadas = perdidas = 0

    with CanalSerial(puerto_tx, METODO) as tx, CanalSerial(puerto_rx, METODO) as rx:
        for seq in range(CANTIDAD):
            tx.enviar(armar_trama(seq, TipoTrama.DATOS, DATOS, METODO))
            crudo = rx.recibir(TIMEOUT_S)

            if crudo is None:
                perdidas += 1
                estado = "Perdida"
            elif (trama := leer_trama(crudo, METODO)) is None:
                danadas += 1
                estado = f"DAÑADA  {crudo.hex(' ')}"
            else: 
                buenas += 1
                estado = f"Buena  seq={trama.seq} datos={trama.datos!r}"

            print(f"[{seq:2}] {estado}")

    print(f"\nBuenas: {buenas}  Dañadas: {danadas}  Perdidas: {perdidas}  (de {CANTIDAD})")


if __name__ == "__main__":
    main()