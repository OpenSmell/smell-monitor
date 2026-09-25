# Smell Monitor: Open-Source Digital Olfaction Hardware

**Status:** V0.1 Reference Design (Schematic complete, PCB layout in progress).

## Overview
Smell Monitor is an open-source, modular hardware reference design for digital olfaction and environmental sensing. It provides a standardized, multi-channel data acquisition platform capable of interfacing with a wide variety of analog (MOX/electrochemical) and digital (MEMS) gas sensors.

## Hardware Architecture
The board is designed around a central microcontroller that manages data acquisition from two distinct sensor interfaces:

*   **Microcontroller:** ESP32-WROOM-32E (Wi-Fi/Bluetooth, dual-core).
*   **Digital Multiplexer:** TCA9548A (8-channel I2C switch). Prevents address collisions, allowing multiple digital sensors with identical I2C addresses to operate on the same bus.
*   **Analog-to-Digital Converters:** 2x ADS1115 (16-bit, 4-channel I2C ADCs). Provides high-resolution reading of analog sensor outputs.
*   **Environmental Compensation:** SHT31-DIS. Placed on the main I2C bus to provide real-time temperature and humidity data for sensor drift compensation.
*   **Power Regulation:** LM1117DT-3.3 (Converts 5V USB input to a regulated 3.3V rail).
*   **I/O:** USB-C (Power/Data), 0.91" I2C OLED Display, Passive Buzzer.

### Sensor Interfaces
The board features 16 universal vertical headers:
1. **Analog Bank (8x 4-Pin):** `3.3V`, `GND`, `AOUT`, `DOUT`. Designed for MOX and electrochemical sensors.
2. **Digital Bank (8x 6-Pin):** `3.3V`, `GND`, `SDA`, `SCL`, `INT`, `CTRL`. Designed for advanced digital MEMS sensors.

## Project Status
*   [x] Core component selection and schematic architecture.
*   [x] I2C multiplexing and environmental compensation routing.
*   [ ] Final schematic Design Rule Check (DRC) and Electrical Rule Check (ERC).
*   [ ] PCB layout and routing.
*   [ ] Bill of Materials (BOM) optimization for manufacturing.

## Contributing
This is an active hardware development project. If you identify issues in the schematic or have recommendations for component selection, please open an Issue or submit a Pull Request. 

*Hardware files are intended to be released under the CERN Open Hardware License.*
