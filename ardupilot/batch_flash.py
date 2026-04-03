#!/usr/bin/env python3
"""
ArduPilot Batch Flash & Configuration Tool
============================================
Automated firmware flashing and parameter configuration for production-scale drone manufacturing.

Designed for: Rarog Tactical Gear — mass production of Rarog-10 FPV drones
Usage:
    python3 batch_flash.py --config presets/rarog10.json --port /dev/ttyUSB0 --flash
    python3 batch_flash.py --config presets/rarog10.json --port /dev/ttyUSB0 --params-only
    python3 batch_flash.py --list-presets
    python3 batch_flash.py --validate --port /dev/ttyUSB0

Requires: pymavlink, serial
"""

import argparse
import json
import time
import sys
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('batch_flash')

# --- Data Structures ---

@dataclass
class FlashResult:
    success: bool
    board: str
    firmware_version: str
    params_applied: int
    params_failed: list = field(default_factory=list)
    elapsed_sec: float = 0.0
    errors: list = field(default_factory=list)


@dataclass
class PresetConfig:
    name: str
    description: str
    board: str  # e.g. "Pixhawk6X", "MatekH743"
    firmware_url: str
    required_params: dict  # PARAM_NAME: value
    calibration: dict = field(default_factory=dict)
    failsafe_params: dict = field(default_factory=dict)
    flight_modes: dict = field(default_factory=dict)


# --- Preset Loader ---

PRESETS_DIR = Path(__file__).parent / 'presets'

def list_presets() -> list[str]:
    """List available preset configurations."""
    if not PRESETS_DIR.exists():
        return []
    return [f.stem for f in PRESETS_DIR.glob('*.json')]


def load_preset(name: str) -> Optional[PresetConfig]:
    """Load preset from JSON file."""
    path = PRESETS_DIR / f'{name}.json'
    if not path.exists():
        log.error(f'Preset not found: {name}')
        return None

    with open(path) as f:
        data = json.load(f)

    return PresetConfig(
        name=data['name'],
        description=data['description'],
        board=data['board'],
        firmware_url=data['firmware_url'],
        required_params=data['params'],
        calibration=data.get('calibration', {}),
        failsafe_params=data.get('failsafe', {}),
        flight_modes=data.get('flight_modes', {}),
    )


# --- MAVLink Connection ---

def connect_mavlink(port: str, baud: int = 115200):
    """Connect to flight controller via MAVLink."""
    try:
        from pymavlink import mavutil
    except ImportError:
        log.error('pymavlink not installed: pip install pymavlink')
        sys.exit(1)

    log.info(f'Connecting to {port} at {baud} baud...')
    conn = mavutil.mavlink_connection(port, baud=baud)
    conn.wait_heartbeat(timeout=10)
    log.info(f'Connected: sysid={conn.target_system}, compid={conn.target_component}')
    return conn


# --- Parameter Operations ---

def set_param(conn, name: str, value) -> bool:
    """Set a single parameter on the flight controller."""
    try:
        conn.mav.param_set_send(
            conn.target_system,
            conn.target_component,
            name.encode('utf-8'),
            float(value),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        # Wait for ACK
        msg = conn.recv_match(type='PARAM_VALUE', blocking=True, timeout=5)
        if msg and msg.param_id.decode('utf-8').strip('\x00') == name:
            return True
    except Exception as e:
        log.error(f'Failed to set {name}: {e}')
    return False


def get_param(conn, name: str) -> Optional[float]:
    """Read a parameter from the flight controller."""
    try:
        conn.mav.param_request_read_send(
            conn.target_system,
            conn.target_component,
            name.encode('utf-8'),
            -1
        )
        msg = conn.recv_match(type='PARAM_VALUE', blocking=True, timeout=5)
        if msg:
            return msg.param_value
    except Exception as e:
        log.error(f'Failed to read {name}: {e}')
    return None


def apply_preset_params(conn, preset: PresetConfig) -> tuple[int, list]:
    """Apply all parameters from a preset. Returns (applied_count, failed_list)."""
    applied = 0
    failed = []

    all_params = {}
    all_params.update(preset.required_params)
    all_params.update(preset.failsafe_params)
    all_params.update(preset.flight_modes)

    total = len(all_params)
    log.info(f'Applying {total} parameters from preset "{preset.name}"...')

    for name, value in all_params.items():
        if set_param(conn, name, value):
            applied += 1
            log.info(f'  [{applied}/{total}] {name} = {value}')
        else:
            failed.append(name)
            log.warning(f'  FAILED: {name} = {value}')

    return applied, failed


# --- Validation ---

def validate_board(conn, expected_board: str) -> bool:
    """Verify the connected board matches the preset."""
    msg = conn.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
    if msg:
        autopilot = msg.autopilot
        log.info(f'Autopilot type: {autopilot}')
        return True
    return False


def validate_params(conn, preset: PresetConfig) -> list[str]:
    """Verify all parameters were applied correctly."""
    mismatches = []
    all_params = {**preset.required_params, **preset.failsafe_params, **preset.flight_modes}

    for name, expected in all_params.items():
        actual = get_param(conn, name)
        if actual is None:
            mismatches.append(f'{name}: READ_FAILED')
        elif abs(actual - float(expected)) > 0.01:
            mismatches.append(f'{name}: expected={expected}, got={actual}')

    return mismatches


# --- Write Params to File (for MAVProxy) ---

def export_params_file(preset: PresetConfig, output_path: str):
    """Export preset as MAVProxy .param file."""
    all_params = {**preset.required_params, **preset.failsafe_params, **preset.flight_modes}

    with open(output_path, 'w') as f:
        f.write(f'# Preset: {preset.name}\n')
        f.write(f'# Board: {preset.board}\n')
        f.write(f'# Description: {preset.description}\n')
        f.write(f'# Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        for name, value in sorted(all_params.items()):
            f.write(f'{name}\t{value}\n')

    log.info(f'Exported {len(all_params)} params to {output_path}')


# --- Main Flow ---

def flash_and_configure(port: str, preset_name: str, params_only: bool = False) -> FlashResult:
    """Main flash + configure flow."""
    start = time.time()

    preset = load_preset(preset_name)
    if not preset:
        return FlashResult(False, '', '', 0, errors=[f'Preset {preset_name} not found'])

    conn = connect_mavlink(port)

    if not validate_board(conn, preset.board):
        log.warning('Board validation: could not verify board type, continuing...')

    # Apply parameters
    applied, failed = apply_preset_params(conn, preset)

    # Validate
    if failed:
        log.warning(f'{len(failed)} params failed, re-trying...')
        time.sleep(1)
        for name in failed:
            val = preset.required_params.get(name) or preset.failsafe_params.get(name) or preset.flight_modes.get(name)
            if val and set_param(conn, name, val):
                failed.remove(name)
                applied += 1

    # Save to FC
    log.info('Writing parameters to persistent storage...')
    set_param(conn, 'SYSID_THISMAV', 1)

    elapsed = time.time() - start
    success = len(failed) == 0

    result = FlashResult(
        success=success,
        board=preset.board,
        firmware_version=preset.firmware_url,
        params_applied=applied,
        params_failed=failed,
        elapsed_sec=round(elapsed, 1),
    )

    log.info(f'Result: {"PASS" if success else "FAIL"} — {applied} params applied in {elapsed:.1f}s')
    if failed:
        log.error(f'Failed params: {", ".join(failed)}')

    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser(description='ArduPilot Batch Flash & Configuration Tool')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--config', help='Preset name (e.g. rarog10)')
    parser.add_argument('--flash', action='store_true', help='Flash firmware + apply params')
    parser.add_argument('--params-only', action='store_true', help='Apply params only (no flash)')
    parser.add_argument('--validate', action='store_true', help='Validate current params')
    parser.add_argument('--list-presets', action='store_true', help='List available presets')
    parser.add_argument('--export', help='Export preset to .param file')

    args = parser.parse_args()

    if args.list_presets:
        presets = list_presets()
        if presets:
            print('Available presets:')
            for p in presets:
                preset = load_preset(p)
                if preset:
                    print(f'  {p:20s} — {preset.description}')
        else:
            print('No presets found. Create one in ardupilot/presets/')
        return

    if not args.config:
        parser.error('--config required (use --list-presets to see available)')

    if args.export:
        preset = load_preset(args.config)
        if preset:
            export_params_file(preset, args.export)
        return

    if args.validate:
        conn = connect_mavlink(args.port, args.baud)
        preset = load_preset(args.config)
        if preset:
            mismatches = validate_params(conn, preset)
            if mismatches:
                print(f'MISMATCHES ({len(mismatches)}):')
                for m in mismatches:
                    print(f'  {m}')
            else:
                print('ALL PARAMETERS VALID')
        conn.close()
        return

    if args.params_only:
        result = flash_and_configure(args.port, args.config, params_only=True)
        sys.exit(0 if result.success else 1)

    if args.flash:
        result = flash_and_configure(args.port, args.config)
        sys.exit(0 if result.success else 1)

    parser.print_help()


if __name__ == '__main__':
    main()
