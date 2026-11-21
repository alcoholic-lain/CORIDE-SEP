# Mieruka demo: Arduino LED + LCD (small scale)

Low-voltage bench demo only. It uses 5 V from USB and no mains voltage. Nothing here connects to 230/240 V.

## What it shows

A simulated air conditioner (`NABD-0004`) draws about 900 W. Press **SPIKE** to simulate an anomaly (about 1.6x load). The Mieruka rule raises an alert after 3 consecutive readings more than 35% above the sliding median. The red LED blinks and the LCD shows `ANOMALIE +xx%`. Press **FIX** to apply the recommendation: the load returns to normal and the green LED comes back on.

Each second is one simulated minute. Measurements are printed on serial in the shared contract format:
`{"adaptateur_id":"NABD-0004","horodatage":...,"watts":...,"source":"simulee"}`

## Parts

- Arduino Uno or Nano (or compatible)
- 16x2 LCD with I2C backpack (PCF8574, usually address 0x27). **Confirm this is the display you have.** If you have an SSD1306 OLED instead, the code must change.
- 2 LEDs (green, red)
- 2 resistors, 220 Ω
- 2 push buttons
- USB cable, breadboard, jumper wires

Library: **LiquidCrystal_I2C** (Frank de Brabander), installed through the Arduino Library Manager.

## Wiring

| Part | Connection | Arduino pin |
|---|---|---|
| Green LED anode | through 220 Ω | D8 |
| Green LED cathode | | GND |
| Red LED anode | through 220 Ω | D9 |
| Red LED cathode | | GND |
| SPIKE button | one leg | D2 |
| SPIKE button | other leg | GND |
| FIX button | one leg | D3 |
| FIX button | other leg | GND |
| LCD I2C SDA | | A4 (Uno) |
| LCD I2C SCL | | A5 (Uno) |
| LCD VCC | | 5V |
| LCD GND | | GND |

Buttons use `INPUT_PULLUP`, so no external pull-up resistor is needed.

## Bench test

1. Wire the LEDs and buttons first, without the LCD. Power the board over USB.
2. Upload `nabd_demo/nabd_demo.ino`. The green LED should be solid.
3. Open the serial monitor at 9600 baud. Expect one JSON line per second with watts around 800 to 1000.
4. Press **SPIKE**. Within about 3 seconds the red LED should start blinking and the serial watts should jump to about 1400 to 1600.
5. Press **FIX**. The red LED stops and the green LED returns.
6. Add the LCD. Check the top line reads `SIMULE NABD-0004` and the bottom line shows `W:xxxx Wh:xxxx`, or `ANOMALIE +xx%` during an alert. If the LCD is blank, adjust the contrast potentiometer on the backpack, then try address 0x3F.

## Demo script (about 2 minutes)

1. "This is one household appliance, an air conditioner, at normal use." (green, about 900 W)
2. Press SPIKE. "Its consumption jumps, which could be a fault or wasted energy." Wait for the red alert.
3. "Mieruka compares each reading to this device's own recent median. Three readings above 35% trigger the alert."
4. Press FIX. "The household applies the recommendation. Points are awarded for the kWh avoided against this device's own history."
5. Point to the serial output to show the measurement format that the real adapter will send.

## Known limits

- The sketch was compiled and run against a PC stub of the Arduino API. The logic passes: the alert is raised and the fix works. **It has not been run on the real board or LCD yet.** Expect small wiring or address issues on the first bench run.
- Watts are simulated. No current sensor is attached. A real build would use a DC-side sensor such as an INA219 (low voltage), and mains metering needs a certified product.
