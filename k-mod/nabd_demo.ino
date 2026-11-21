/*
  Nabd demo, small scale: simulated air conditioner on an Arduino.
  Low voltage only. Nothing here touches mains.

  Hardware
    - Arduino Uno (or Nano)
    - 16x2 LCD with I2C backpack (address 0x27; check yours)
    - LED green on D8, LED red on D9 (each with a 220 ohm resistor to GND)
    - Button SPIKE on D2 (to GND), Button FIX on D3 (to GND). Internal pull-ups.

  Libraries
    - LiquidCrystal_I2C (Frank de Brabander)

  Behaviour (same rule as the workspace AI module)
    - Simulated power for NABD-0004 (Climatisation), one sample per second = one simulated minute.
    - Keeps the last 15 normal samples. Median per device.
    - Alert when the value is more than 35% above the median for 3 samples in a row.
    - SPIKE button toggles "Clim anormale" (load x1.6).
    - FIX button applies the recommendation: load back to normal, alert cleared.
    - Every reading is also printed as JSON on serial, in the Nabd measurement format.
*/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const uint8_t LCD_ADDR = 0x27;
const uint8_t PIN_GREEN = 8;
const uint8_t PIN_RED = 9;
const uint8_t PIN_SPIKE = 2;
const uint8_t PIN_FIX = 3;

const char DEVICE_ID[] = "NABD-0004";
const unsigned int BASE_W = 900;          // air conditioner base power
const unsigned long TICK_MS = 1000;       // 1 s = 1 simulated minute
const uint8_t HISTORY = 15;
const uint8_t CONSECUTIVE = 3;
const unsigned int THRESHOLD_PCT = 135;   // 35% above median
const unsigned int ANOMALY_PCT = 160;     // "Clim anormale" load factor (x1.6)

LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

unsigned int history[HISTORY];
uint8_t historyCount = 0;
uint8_t historyNext = 0;
uint8_t aboveCount = 0;
bool spikeOn = false;      // "Clim anormale" injected
bool alert = false;
unsigned int lastW = 0;
unsigned long lastTick = 0;
unsigned long lastBlink = 0;
bool blinkOn = false;
unsigned long whTotal = 0; // energy since start, in Wh (approximate)
unsigned int lastPct = 0;

unsigned int medianOfHistory() {
  unsigned int copy[HISTORY];
  for (uint8_t i = 0; i < historyCount; i++) copy[i] = history[i];
  // insertion sort (15 values, fine on an Uno)
  for (uint8_t i = 1; i < historyCount; i++) {
    unsigned int key = copy[i];
    int8_t j = i - 1;
    while (j >= 0 && copy[j] > key) { copy[j + 1] = copy[j]; j--; }
    copy[j + 1] = key;
  }
  return copy[historyCount / 2];
}

unsigned int simulateWatts() {
  unsigned long factor = spikeOn ? ANOMALY_PCT : 100;
  long noise = (long)random(-8, 9);           // +/- 8 %
  unsigned long w = (BASE_W * factor / 100UL) * (100L + noise) / 100UL;
  return (unsigned int)w;
}

void setLeds() {
  if (alert) {
    digitalWrite(PIN_GREEN, LOW);
    if (millis() - lastBlink >= 500) { blinkOn = !blinkOn; lastBlink = millis(); }
    digitalWrite(PIN_RED, blinkOn ? HIGH : LOW);
  } else {
    digitalWrite(PIN_RED, LOW);
    digitalWrite(PIN_GREEN, HIGH);
  }
}

void printLcd() {
  char line0[17];
  char line1[24];
  snprintf(line0, sizeof(line0), "SIMULE %s", DEVICE_ID);   // "SIMULE NABD-0004"
  if (alert) {
    snprintf(line1, sizeof(line1), "ANOMALIE +%3u%%", lastPct > 100 ? lastPct - 100 : 0);
  } else {
    snprintf(line1, sizeof(line1), "W:%4u Wh:%4lu", lastW, whTotal);
  }
  lcd.setCursor(0, 0); lcd.print(line0);
  lcd.setCursor(0, 1); lcd.print(line1);
}

void printJson(unsigned long ms) {
  Serial.print(F("{\"adaptateur_id\":\""));
  Serial.print(DEVICE_ID);
  Serial.print(F("\",\"horodatage\":"));
  Serial.print(ms);
  Serial.print(F(",\"watts\":"));
  Serial.print(lastW);
  Serial.println(F(",\"source\":\"simulee\"}"));
}

void setup() {
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_SPIKE, INPUT_PULLUP);
  pinMode(PIN_FIX, INPUT_PULLUP);
  randomSeed(analogRead(A0));
  Serial.begin(115200);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lastW = BASE_W;
}

void loop() {
  // Buttons (pressed = LOW), with a simple debounce delay
  if (digitalRead(PIN_SPIKE) == LOW) {
    spikeOn = !spikeOn;
    delay(250);
  }
  if (digitalRead(PIN_FIX) == LOW) {
    // applying the recommendation: back to normal, clear the alert and the history
    spikeOn = false;
    alert = false;
    aboveCount = 0;
    historyCount = 0;
    historyNext = 0;
    delay(250);
  }

  setLeds();

  if (millis() - lastTick >= TICK_MS) {
    lastTick = millis();
    unsigned int w = simulateWatts();
    lastW = w;
    whTotal += w / 60;                       // one simulated minute per tick

    if (historyCount >= HISTORY) {
      unsigned int med = medianOfHistory();
      unsigned long pct = (unsigned long)w * 100UL / (med ? med : 1);
      lastPct = (unsigned int)pct;
      if (pct > THRESHOLD_PCT) {
        aboveCount++;
      } else {
        aboveCount = 0;
      }
      if (aboveCount >= CONSECUTIVE) alert = true;
    }

    if (!alert) {                            // only normal values go into the history
      history[historyNext] = w;
      historyNext = (historyNext + 1) % HISTORY;
      if (historyCount < HISTORY) historyCount++;
    }

    printLcd();
    printJson(millis());
  }
}
