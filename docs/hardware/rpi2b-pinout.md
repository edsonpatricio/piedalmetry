# Raspberry Pi 2 Model B — GPIO Pinout Reference

**Board**: Raspberry Pi 2 Model B (BCM2836, ARMv7, 40-pin header)

## Pin 1 Location

Pin 1 is at the **corner closest to the SD card slot**, marked with a
small triangle or square pad on the PCB. All odd pins (1, 3, 5, …) are
on the inner row when the board is oriented with the USB ports facing
down.

```text
                    [USB ports → down]

   3V3  (1) (2)  5V
 GPIO2  (3) (4)  5V
 GPIO3  (5) (6)  GND
 GPIO4  (7) (8)  GPIO14
   GND  (9) (10) GPIO15   ◄── LED cathode (GND)
GPIO17 (11) (12) GPIO18  ◄── ENA (PWM)    ◄── LED anode (via 330 Ω)
GPIO27 (13) (14) GND
GPIO22 (15) (16) GPIO23  ◄── IN1
   3V3 (17) (18) GPIO24  ◄── IN2
GPIO10 (19) (20) GND
 GPIO9 (21) (22) GPIO25
GPIO11 (23) (24) GPIO8
   GND (25) (26) GPIO7
 GPIO0 (27) (28) GPIO1
 GPIO5 (29) (30) GND
 GPIO6 (31) (32) GPIO12
GPIO13 (33) (34) GND
GPIO19 (35) (36) GPIO16
GPIO26 (37) (38) GPIO20
   GND (39) (40) GPIO21
```

## Pins Used by Piedalmetry

| Physical Pin | BCM | Function | Connected to |
|-------------|-----|----------|--------------|
| Pin 2 | 5V | Power | L298N VCC |
| Pin 6 | GND | Ground | L298N GND |
| **Pin 9** | **GND** | **LED cathode** | **Blue LED (−)** |
| **Pin 11** | **GPIO 17** | **LED anode** | **330 Ω → Blue LED (+)** |
| **Pin 12** | **GPIO 18** | **ENA (PWM)** | **L298N ENA** |
| **Pin 16** | **GPIO 23** | **IN1** | **L298N IN1** |
| **Pin 18** | **GPIO 24** | **IN2** | **L298N IN2** |

## BCM vs Physical Pin Numbering

Piedalmetry uses **BCM (Broadcom) numbering** in the config file:

```toml
[motor]
gpio_ena = 18   # BCM 18 → Physical pin 12
gpio_in1 = 23   # BCM 23 → Physical pin 16
gpio_in2 = 24   # BCM 24 → Physical pin 18
```

Do not confuse BCM numbers with physical pin numbers. The config
file always uses BCM.

## GPIO Electrical Specifications

| Parameter | Value |
|-----------|-------|
| Logic level (HIGH) | 3.3V |
| Logic level (LOW) | 0V |
| Max current per GPIO pin | 16mA |
| Max total GPIO current | 51mA |
| Input voltage tolerance | 3.3V max (NOT 5V tolerant) |

The L298N accepts 3.3V logic on IN1/IN2/ENA. No level shifter needed.

## DietPi GPIO Access

On DietPi, the user running piedalmetry must have access to `/dev/gpiochip0`.
The `dietpi` user is typically in the `gpio` group. Verify with:

```bash
groups dietpi
# Should include: gpio
```

If not in the group:

```bash
sudo usermod -aG gpio dietpi
# Log out and back in, or reboot
```
