# firmware/

ESP32 firmware for the Smell Monitor v1.

## Status

Not yet implemented — structure agreed in `docs/architecture.md §7`.

## Top-level behaviour

1. **Cycle state machine:** `IDLE → INTAKE(10s) → HOLD(10s) → PURGE(20s) → report`. Triggered by measure button (GPIO0) or UART host command.
2. **Analog acquisition (HOLD):** interleave 8 ADS1115 channels @ ~8 SPS/ch, average per channel.
3. **Digital scan (HOLD):** iterate TCA9548A channels 0–7; detect & read whatever sensor is present (driver registry keyed by chip ID).
4. **Environmental logging:** SHT31 @ 1 Hz at all phases.
5. **Comms protocol (USB-UART, 115200 baud):** JSON records `{ts, phase, ao[8], digital[8], t, rh, cycle_id}` → Osmograph.
6. **UI:** OLED phase/values; LED state machine; buzzer events.
7. **Boot self-test:** fan, I2C enumeration, divider sanity, SHT31.

## Proposed layout

```
firmware/esp32/
├── src/
│   ├── main.cpp          # init + loop
│   ├── cycle.h/.cpp      # three-phase state machine
│   ├── sensors/          # ADS1115, TCA9548A drivers, digital sensor registry
│   ├── ui/               # OLED, LED, buzzer
│   └── serial_proto.cpp  # JSON records out
├── platformio.ini        # ESP32-WROOM-32E target
└── test/                 # unit tests for cycle state transitions
```

Reference: Arduino-ESP32 core.