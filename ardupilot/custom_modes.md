## ArduPilot Custom Mode: GRIM_COMBAT

Custom flight mode for tactical FPV operations.
Based on ArduCopter mode_LOTL (Low Altitude Target Lock).

### Features:
- Auto-arm with GPS fix (3D fix, HDOP < 2.0, 8+ sats)
- Low-altitude cruise (5-15m AGL, terrain following via rangefinder)
- Wind compensation via feed-forward on rate controller
- RTL triggers: battery < 3.5V/cell, RC link loss > 2s, GPS loss > 5s
- Emergency: instant RTL on EKF failure

### RTL Behavior (foldable conditions):
- Climb to RTL_ALT (30m default)
- Direct return to HOME at max speed
- Auto-land with sonar assist
- Total RTL time target: < 60s from any point in 2km radius

### Parameter patches (apply via MAVProxy or .param file):
```
RTL_ALT        3000    # 30m return altitude (cm)
RTL_SPEED      1500    # 15 m/s return speed (cm/s)
RTL_LAND_FINAL 500     # 5m final approach (cm)
WPNAV_SPEED    1200    # 12 m/s cruise (cm/s)
FENCE_ENABLE   1       # Geofence on
FENCE_RADIUS   2000    # 2km radius (m)
FENCE_ALT_MAX  120     # 120m max altitude (m)
DISARM_DELAY   2       # 2s auto-disarm on land
ARMING_CHECK   1       # All pre-arm checks
GPS_HDOP       200     # Max HDOP for arm (cm)
```

### SITL Test Command:
```bash
sim_vehicle.py -v ArduCopter -f quad --console --map -w
# Wait for GPS fix, then:
# ARM throttle
# MODE GRIM_COMBAT (if mode defined)
# Or test with GUIDED mode + waypoints
```

### Hardware:
- Flight controller: Pixhawk 6X (STM32H743)
- GPS: HMC UBLOX M9N (dual antenna)
- Rangefinder: Benewake TF02 Pro (LiDAR, 40m)
- Telemetry: ExpressLRS 2.4GHz (low latency)
- Failsafe: FrSky R-XSR + ELRS backup
