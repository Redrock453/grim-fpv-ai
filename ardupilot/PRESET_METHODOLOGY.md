# ArduPilot Preset Configuration Methodology

## Overview

This document describes the step-by-step methodology for configuring ArduPilot-based drones in a production environment. Designed for operators who need to flash and configure multiple units without R&D involvement.

**Target:** Linear workers can configure a ready-to-fly board in **under 15 minutes**.

---

## Prerequisites

- Laptop with Mission Planner installed
- USB cable (Micro-B or USB-C depending on FC)
- Preset JSON file for the specific drone model
- Charged battery for the drone

---

## Step-by-Step: Board Configuration

### Phase 1: Connection & Firmware (3 min)

1. Connect FC to laptop via USB
2. Open Mission Planner → **Initial Setup → Install Firmware**
3. Select correct board type (e.g. Pixhawk 6X)
4. Flash stable ArduPilot Copter firmware
5. Wait for "Firmware uploaded successfully"

### Phase 2: Preset Loading (2 min)

**Option A — Batch Flash Tool:**
```bash
python3 ardupilot/batch_flash.py --config rarog10 --port /dev/ttyACM0 --params-only
```

**Option B — Mission Planner:**
1. Connect to FC in Mission Planner
2. **Config/Tuning → Full Parameter List**
3. **Load from file** → select `.param` file from `ardupilot/presets/`
4. **Write to FC**

### Phase 3: Calibration (5 min)

1. **Accelerometer Calibration:**
   - Initial Setup → Mandatory Hardware → Accel Calibration
   - Place FC in 6 positions as instructed
   - Wait for "Calibration successful"

2. **Compass Calibration:**
   - Initial Setup → Mandatory Hardware → Compass
   - Click "Live Calibration"
   - Rotate drone in all axes for 60 seconds
   - Keep away from metal/EMI sources

3. **Radio Calibration:**
   - Turn on RC transmitter
   - Initial Setup → Mandatory Hardware → Radio Calibration
   - Verify all channels respond correctly
   - Confirm throttle range 1000-2000μs

4. **ESC Calibration:**
   - Initial Setup → Optional Hardware → ESC Calibration
   - Follow on-screen instructions
   - Verify all motors spin at correct speeds

### Phase 4: Pre-Flight Check (3 min)

1. **Verify parameters:**
   ```bash
   python3 ardupilot/batch_flash.py --validate --config rarog10 --port /dev/ttyACM0
   ```

2. **In Mission Planner:**
   - Check GPS lock (≥ 8 satellites, HDOP < 2.0)
   - Verify battery voltage reading
   - Test flight modes switch (Stabilize → AltHold → Loiter → Auto)
   - Check RTL settings (altitude, cone slope)
   - Verify failsafe triggers: disconnect RC → observe RTL behavior

3. **Motor test:**
   - Initial Setup → Optional Hardware → Motor Test
   - Confirm correct motor order and direction

### Phase 5: First Flight Validation (2 min)

1. Arm in **Stabilize** mode
2. Hover at 2m for 10 seconds
3. Switch to **AltHold** — verify altitude hold
4. Switch to **Loiter** — verify position hold
5. Trigger **RTL** — verify return to launch point
6. Land and disarm

---

## Preset Files

| Preset | Drone Model | Board | Use Case |
|--------|------------|-------|----------|
| `rarog10` | Rarog-10 FPV Strike | Pixhawk 6X | Production strike drone |
| `grim5_combat` | GRIM-5 Combat FPV | SpeedyBee F405 V4 | Combat FPV with custom mode |

## Creating New Presets

1. Tune one drone manually (PID, failsafe, flight modes)
2. Export parameters: Mission Planner → Save to file
3. Convert to JSON format:
   ```json
   {
     "name": "Drone Model Name",
     "description": "Short description",
     "board": "BoardType",
     "firmware_url": "https://firmware.ardupilot.org/...",
     "params": { "PARAM": value, ... },
     "failsafe": { "PARAM": value, ... },
     "flight_modes": { "MODE1": 0, ... }
   }
   ```
4. Save as `ardupilot/presets/your_preset.json`
5. Test: `python3 batch_flash.py --config your_preset --params-only --port /dev/ttyACM0`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| FC not detected | Check USB cable, try different port, install CP210x/STM32 drivers |
| Compass calibration fails | Move away from metal, recalibrate outdoors |
| GPS won't lock | Ensure antenna facing up, clear sky view, wait 2 min cold start |
| ESC beep/no spin | Check motor wiring order, recalibrate ESCs |
| Parameter write fails | Check connection stability, retry, use --validate to identify |

---

## Batch Production Workflow

For configuring **N drones** in sequence:

```bash
# Loop through connected boards
for i in $(seq 1 $COUNT); do
    echo "=== Board $i/$COUNT ==="
    python3 ardupilot/batch_flash.py --config rarog10 --port /dev/ttyACM0 --params-only
    echo "Board $i done. Connect next board and press Enter..."
    read
done
```

**Expected throughput:** 15 min per board (including calibration)
**Operator skill required:** Basic Mission Planner familiarity
**R&D involvement:** Zero after initial preset creation
