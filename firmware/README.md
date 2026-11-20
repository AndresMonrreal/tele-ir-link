# Firmware de las estaciones IR

## Conexiones (igual en las dos ESP32)
- Receptor: S → D4, + → 3V3, − → GND
- Emisor: VIN → 100 Ω → pata larga del LED; pata corta → C del 2N2222;
  D18 → 1 kΩ → B; E → GND

## Pruebas, en este orden
1. prueba_receptor: con el control del kit deben salir líneas Protocol=NEC.
2. prueba_emisor: el LED IR se ve prendido con la cámara FRONTAL (la trasera filtra el IR).
3. prueba_enlace: con el LED apuntando al receptor debe dar ~330 con LED y 0 sin LED.

## Problemas que ya nos pasaron
- Resistencias intercambiadas: la de 100 Ω (4.ª franja negra) va al LED,
  la de 1 kΩ (4.ª franja café) a la base. Al revés, el LED casi no emite.
- El LED IR emite en un cono angosto: tiene que apuntar al domo del receptor.
- El control del kit usa pila CR2025.
- Unos 68 cambios = una trama NEC del control (sirve para saber que el receptor funciona).
- `IrSender` de IRremote no emitía nada con nuestro core de ESP32 (las pruebas A→B daban 0 bytes).
  Solución: generar la trama NEC a mano con `ledcAttach`/`ledcWrite` a 38 kHz
  (encabezado 9 ms + 4.5 ms, bits por distancia de pulsos: 560/560 µs = 0, 560/1690 µs = 1).
  IRremote se usa solo para recibir.
- Windows cambia el número de COM al reconectar: verificar con
  `[System.IO.Ports.SerialPort]::GetPortNames()` antes de cada prueba.
- "Access is denied" = otro programa (Monitor Serie, otro script) tiene el puerto abierto.
- Prueba de enlace: `uv run python scripts\probar_enlace.py COMtx COMrx` → 30/30 bytes en ambos sentidos.