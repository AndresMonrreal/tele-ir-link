"""Menú para probar el enlace: escoger mensaje, método de detección, ARQ y ruido."""

from __future__ import annotations

from tele_ir_link.arq import MODOS, Estadisticas, transmitir_simulado
from tele_ir_link.canal import ConfigRuido
from tele_ir_link.tramas import METODOS

MENSAJE_DEFECTO = "Hola desde la ESP32, este es un mensaje de prueba del enlace infrarrojo."

NIVELES_RUIDO: dict[str, ConfigRuido] = {
    "sin ruido": ConfigRuido(),
    "bajo": ConfigRuido(prob_bit=0.0005),
    "medio": ConfigRuido(prob_bit=0.001, prob_rafaga=0.05),
    "alto": ConfigRuido(prob_bit=0.002, prob_rafaga=0.10, prob_perdida=0.05),
}

NOMBRES_ARQ = {
    "pare_espera": "Pare y espere",
    "retroceda_n": "Retroceda N",
    "rechazo_selectivo": "Rechazo selectivo",
}


def elegir(titulo: str, opciones: list[str], defecto: int = 0) -> str:
    print(f"\n{titulo}")
    for i, nombre in enumerate(opciones, start=1):
        marca = " (por defecto)" if i - 1 == defecto else ""
        print(f"  {i}. {nombre}{marca}")
    while True:
        texto = input("> ").strip()
        if not texto:
            return opciones[defecto]
        if texto.isdigit() and 1 <= int(texto) <= len(opciones):
            return opciones[int(texto) - 1]
        print("Opción no válida, escribe el número.")


def mostrar(modo: str, recibido: bytes, esperado: bytes, stats: Estadisticas) -> None:
    estado = "OK, el mensaje llegó igual" if recibido == esperado else "ERROR: el mensaje llegó distinto"
    print(f"\n--- {NOMBRES_ARQ[modo]} ---")
    print(f"Resultado:           {estado}")
    print(f"Tramas enviadas:     {stats.tramas_enviadas} (necesarias: {stats.tramas_utiles})")
    print(f"Retransmisiones:     {stats.retransmisiones}")
    print(f"Errores detectados:  {stats.errores_detectados}")
    print(f"Errores corregidos:  {stats.errores_corregidos}")
    print(f"Temporizadores:      {stats.timeouts}")
    print(f"Eficiencia:          {stats.eficiencia:.0%}")


def correr(modo: str, mensaje: bytes, metodo: str, ruido: ConfigRuido) -> None:
    try:
        recibido, stats = transmitir_simulado(mensaje, modo, metodo, ruido, timeout=0.05)
    except ConnectionError as error:
        print(f"\n--- {NOMBRES_ARQ[modo]} ---\nEl enlace falló: {error}")
        return
    mostrar(modo, recibido, mensaje, stats)


def main() -> None:
    texto = input(f"Mensaje a enviar (Enter = \"{MENSAJE_DEFECTO}\"):\n> ").strip()
    mensaje = (texto or MENSAJE_DEFECTO).encode("utf-8")

    metodo = elegir("Método de detección de errores:", list(METODOS), defecto=0)
    nivel = elegir("Nivel de ruido:", list(NIVELES_RUIDO), defecto=2)
    opciones_arq = [*MODOS, "comparar los tres"]
    arq = elegir("Tipo de ARQ:", opciones_arq, defecto=0)

    ruido = NIVELES_RUIDO[nivel]
    modos = list(MODOS) if arq == "comparar los tres" else [arq]
    try:
        for modo in modos:
            correr(modo, mensaje, metodo, ruido)
    except AttributeError as error:
        print(f"\nFalta código de otro integrante ({error}). "
              "Prueba con el método 'ninguno' mientras llega deteccion.py.")


if __name__ == "__main__":
    main()
