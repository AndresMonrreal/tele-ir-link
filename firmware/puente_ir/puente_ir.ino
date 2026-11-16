/*
 * puente_ir.ino
 * Puente USB <-> infrarrojo (NEC) para el proyecto TELE U2.
 *
 * La ESP32 es solo un "módem": no entiende tramas, VRC ni CRC.
 *   USB -> IR : toma los bytes de 2 en 2 y manda cada par en una trama NEC.
 *   IR -> USB : cada trama NEC recibida se entrega como 2 bytes.
 *
 * Conexiones: receptor en D4, emisor (vía 2N2222) en D18.
 * Los bytes por USB son binarios: NO imprimir texto de depuración aquí.
 */

#define DECODE_NEC          // solo decodificar NEC (antes del include)
#include <IRremote.hpp>

const uint8_t PIN_RECEPTOR = 4;
const uint8_t PIN_EMISOR = 18;
const unsigned long BAUDIOS = 115200;   // igual en pyserial

const unsigned long PAUSA_ENTRE_PARES_MS = 30;  // silencio tras cada trama NEC
const unsigned long TIMEOUT_IMPAR_MS = 20;      // espera por el 2.º byte de un par
const uint8_t BYTE_RELLENO = 0x00;              // si llega un byte suelto

// true: el receptor propio se apaga mientras se transmite (evita el eco)
const bool SILENCIAR_RX_AL_ENVIAR = true;

// false: entrega los bytes aunque NEC detecte error (así el CRC/VRC de Python
//        es quien los detecta). true: descarta tramas con paridad NEC mala.
const bool DESCARTAR_SI_NEC_INVALIDO = false;

bool hayImpar = false;
unsigned long instanteImpar = 0;

// Una trama NEC lleva 4 bytes: dirección, ~dirección, comando, ~comando.
bool paridadNecOk(uint32_t crudo) {
  const uint8_t b0 = crudo & 0xFF;
  const uint8_t b1 = (crudo >> 8) & 0xFF;
  const uint8_t b2 = (crudo >> 16) & 0xFF;
  const uint8_t b3 = (crudo >> 24) & 0xFF;
  return (uint8_t)(b0 ^ b1) == 0xFF && (uint8_t)(b2 ^ b3) == 0xFF;
}

void enviarPar(uint8_t primero, uint8_t segundo) {
  if (SILENCIAR_RX_AL_ENVIAR) {
    IrReceiver.stop();
  }
  // Dirección <= 0xFF => NEC estándar (la librería agrega el byte invertido).
  IrSender.sendNEC(primero, segundo, 0);
  delay(PAUSA_ENTRE_PARES_MS);  // sendNEC no deja silencio al final
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

void atenderInfrarrojo() {
  if (!IrReceiver.decode()) {
    return;
  }

  const IRData &d = IrReceiver.decodedIRData;
  const bool esNec =
      (d.protocol == NEC || d.protocol == NEC2 || d.protocol == ONKYO) &&
      d.numberOfBits == 32;

  if (esNec) {
    // Usamos los 32 bits crudos y no address/command: la librería cambia
    // cómo los interpreta si la paridad falla, y aquí queremos siempre
    // los mismos 2 bytes (el 1.º y el 3.º).
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

void setup() {
  Serial.setRxBufferSize(1024);  // antes de Serial.begin
  Serial.begin(BAUDIOS);

  IrReceiver.begin(PIN_RECEPTOR, DISABLE_LED_FEEDBACK);
  IrSender.begin(PIN_EMISOR);
}

void loop() {
  atenderInfrarrojo();
  atenderUsb();
}