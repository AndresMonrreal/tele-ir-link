/*
 * puente_ir.ino  (v2: emisor NEC propio con LEDC)
 * Puente USB <-> infrarrojo para el proyecto TELE U2.
 *
 *   USB -> IR : toma los bytes de 2 en 2 y manda cada par en una trama NEC
 *               generada a mano (portadora de 38 kHz con LEDC).
 *   IR -> USB : IRremote decodifica la trama NEC y salen 2 bytes por USB.
 *
 * Conexiones: receptor en D4, emisor (vía 2N2222) en D18.
 * Los bytes por USB son binarios: NO imprimir texto de depuración aquí.
 */

#define DECODE_NEC          // solo decodificar NEC (antes del include)
#include <IRremote.hpp>

// ---------- Configuración ----------
const uint8_t PIN_RECEPTOR = 4;
const uint8_t PIN_EMISOR = 18;
const unsigned long BAUDIOS = 115200;   // igual en pyserial

const uint32_t FRECUENCIA_PORTADORA_HZ = 38000;  // a lo que responde el receptor
const uint8_t RESOLUCION_BITS = 8;               // duty de 0 a 255
const uint32_t DUTY_PORTADORA = 128;             // ~50 % mientras hay "marca"

const unsigned long PAUSA_ENTRE_PARES_MS = 30;  // silencio tras cada trama NEC
const unsigned long TIMEOUT_IMPAR_MS = 20;      // espera por el 2.º byte de un par
const uint8_t BYTE_RELLENO = 0x00;              // si llega un byte suelto

// true: el receptor propio se apaga mientras se transmite (evita el eco)
const bool SILENCIAR_RX_AL_ENVIAR = true;

// false: entrega los bytes aunque NEC detecte error (los detecta el CRC/VRC
//        de Python). true: descarta tramas con paridad NEC mala.
const bool DESCARTAR_SI_NEC_INVALIDO = false;

// ---------- Estado ----------
bool hayImpar = false;
unsigned long instanteImpar = 0;

// ---------- Utilidades ----------
// Una trama NEC lleva 4 bytes: dirección, ~dirección, comando, ~comando.
bool paridadNecOk(uint32_t crudo) {
  const uint8_t b0 = crudo & 0xFF;
  const uint8_t b1 = (crudo >> 8) & 0xFF;
  const uint8_t b2 = (crudo >> 16) & 0xFF;
  const uint8_t b3 = (crudo >> 24) & 0xFF;
  return (uint8_t)(b0 ^ b1) == 0xFF && (uint8_t)(b2 ^ b3) == 0xFF;
}

// ---------- Emisor NEC propio ----------
// "Marca" = LED parpadeando a 38 kHz. "Espacio" = LED apagado.
void marca(unsigned int microsegundos) {
  ledcWrite(PIN_EMISOR, DUTY_PORTADORA);
  delayMicroseconds(microsegundos);
}

void espacio(unsigned int microsegundos) {
  ledcWrite(PIN_EMISOR, 0);
  delayMicroseconds(microsegundos);
}

// NEC: encabezado 9 ms + 4.5 ms, luego 32 bits LSB primero
// (bit 0 = 560 us marca + 560 us espacio; bit 1 = 560 us + 1690 us),
// y una marca final de 560 us.
void enviarNec(uint8_t direccion, uint8_t comando) {
  const uint32_t trama =
      (uint32_t)direccion |
      ((uint32_t)(uint8_t)~direccion << 8) |
      ((uint32_t)comando << 16) |
      ((uint32_t)(uint8_t)~comando << 24);

  marca(9000);
  espacio(4500);

  for (uint8_t i = 0; i < 32; i++) {
    marca(560);
    espacio(((trama >> i) & 1) ? 1690 : 560);
  }

  marca(560);
  ledcWrite(PIN_EMISOR, 0);
}

// ---------- USB -> IR ----------
void enviarPar(uint8_t primero, uint8_t segundo) {
  if (SILENCIAR_RX_AL_ENVIAR) {
    IrReceiver.stop();
  }
  enviarNec(primero, segundo);
  delay(PAUSA_ENTRE_PARES_MS);
  if (SILENCIAR_RX_AL_ENVIAR) {
    IrReceiver.start();
  }
}

void atenderUsb() {
  const int disponibles = Serial.available();

  if (disponibles >= 2) {
    const uint8_t primero = Serial.read();
    const uint8_t segundo = Serial.read();
    hayImpar = false;
    enviarPar(primero, segundo);
    return;
  }

  if (disponibles == 1) {
    if (!hayImpar) {
      hayImpar = true;
      instanteImpar = millis();
    } else if (millis() - instanteImpar >= TIMEOUT_IMPAR_MS) {
      const uint8_t solo = Serial.read();
      hayImpar = false;
      enviarPar(solo, BYTE_RELLENO);
    }
    return;
  }

  hayImpar = false;
}

// ---------- IR -> USB ----------
void atenderInfrarrojo() {
  if (!IrReceiver.decode()) {
    return;
  }

  const IRData &d = IrReceiver.decodedIRData;
  const bool esNec =
      (d.protocol == NEC || d.protocol == NEC2 || d.protocol == ONKYO) &&
      d.numberOfBits == 32;

  if (esNec) {
    const uint32_t crudo = (uint32_t)d.decodedRawData;
    if (!DESCARTAR_SI_NEC_INVALIDO || paridadNecOk(crudo)) {
      const uint8_t par[2] = {
        (uint8_t)(crudo & 0xFF),
        (uint8_t)((crudo >> 16) & 0xFF)
      };
      Serial.write(par, 2);
    }
  }

  IrReceiver.resume();  // sin esto no recibe la siguiente trama
}

// ---------- Arduino ----------
void setup() {
  Serial.setRxBufferSize(1024);  // antes de Serial.begin
  Serial.begin(BAUDIOS);

  ledcAttach(PIN_EMISOR, FRECUENCIA_PORTADORA_HZ, RESOLUCION_BITS);
  ledcWrite(PIN_EMISOR, 0);  // LED apagado al arrancar

  IrReceiver.begin(PIN_RECEPTOR, DISABLE_LED_FEEDBACK);
}

void loop() {
  atenderInfrarrojo();
  atenderUsb();
}