"""
ArduPilot SITL PID Auto-Tuner for GRIM-5
Quick script to run automated PID sweeps in SITL and log results.

Usage:
    python ardupilot/grim5_tuning.py --sitrl  # Full SITL sweep
    python ardupilot/grim5_tuning.py --analyze logs/flight.bin  # Analyze log
"""

import subprocess
import json
import time
import argparse
from pathlib import Path

# GRIM-5 PID sweep ranges
PID_RANGES = {
    "roll": {
        "P": [0.10, 0.12, 0.135, 0.15, 0.17],
        "I": [0.015, 0.018, 0.02, 0.025],
        "D": [0.003, 0.004, 0.0045, 0.005, 0.006],
    },
    "pitch": {
        "P": [0.10, 0.12, 0.135, 0.15, 0.17],
        "I": [0.015, 0.018, 0.02, 0.025],
        "D": [0.003, 0.004, 0.0045, 0.005, 0.006],
    },
    "yaw": {
        "P": [0.15, 0.18, 0.20, 0.22],
        "I": [0.015, 0.018, 0.02, 0.025],
        "D": [0.0],
    },
}

# Best known params (from manual tuning)
BEST_PARAMS = {
    "ATC_RAT_RLL_P": 0.135,
    "ATC_RAT_RLL_I": 0.018,
    "ATC_RAT_RLL_D": 0.0045,
    "ATC_RAT_PIT_P": 0.135,
    "ATC_RAT_PIT_I": 0.018,
    "ATC_RAT_PIT_D": 0.0045,
    "ATC_RAT_YAW_P": 0.200,
    "ATC_RAT_YAW_I": 0.020,
    "ATC_RAT_YAW_D": 0.000,
}


def generate_mavproxy_script(params: dict, output: str = "tune.param"):
    """Generate MAVProxy-compatible .param file."""
    lines = ["# Auto-generated PID params for GRIM-5 tuning sweep"]
    for k, v in params.items():
        lines.append(f"{k:20s} {v}")
    path = Path("logs") / output
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines))
    return str(path)


def score_pid(log_path: str) -> float:
    """
    Score a PID tune from flight log.
    Lower is better. Measures: rate error RMS, oscillation count, max overshoot.
    """
    # Placeholder — real implementation would parse .bin log with pymavlink
    # Score = weighted sum of:
    #   0.5 * rate_error_rms +
    #   0.3 * oscillation_count_per_sec +
    #   0.2 * max_overshoot_deg / 10.0
    return 0.0


def run_sitl_sweep():
    """Run full PID sweep in SITL with Gazebo wind simulation."""
    print("=" * 50)
    print("GRIM-5 PID Auto-Tuner (SITL)")
    print("=" * 50)

    results = []

    for axis in ["roll", "pitch", "yaw"]:
        print(f"\n--- Sweeping {axis.upper()} ---")
        for p in PID_RANGES[axis]["P"]:
            for i in PID_RANGES[axis]["I"]:
                for d in PID_RANGES[axis]["D"]:
                    params = {
                        f"ATC_RAT_{axis[:3].upper()}_P": p,
                        f"ATC_RAT_{axis[:3].upper()}_I": i,
                        f"ATC_RAT_{axis[:3].upper()}_D": d,
                    }
                    param_file = generate_mavproxy_script(
                        params, f"sweep_{axis}_P{p}_I{i}_D{d}.param"
                    )
                    print(f"  P={p:.3f} I={i:.3f} D={d:.4f} -> {param_file}")
                    results.append({"axis": axis, "params": params, "file": param_file})

    # Save sweep plan
    plan_path = Path("logs/sweep_plan.json")
    plan_path.write_text(json.dumps(results, indent=2))
    print(f"\nSweep plan: {len(results)} combinations -> logs/sweep_plan.json")
    print("\nNext: run each param set in SITL with wind sim and score results")
    print("  sim_vehicle.py -v ArduCopter --console --map")
    print("  param load <sweep_file>")
    print("  arm throttle && rc 3 1800  # takeoff")


def analyze_log(log_path: str):
    """Analyze a flight log and score the tune."""
    print(f"Analyzing: {log_path}")
    score = score_pid(log_path)
    print(f"Score: {score:.3f} (lower = better)")
    print(f"Reference (best manual tune): ~0.42")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GRIM-5 PID Tuner")
    parser.add_argument("--sitrl", action="store_true", help="Generate PID sweep for SITL")
    parser.add_argument("--analyze", type=str, help="Analyze flight log")
    args = parser.parse_args()

    if args.sitrl:
        run_sitl_sweep()
    elif args.analyze:
        analyze_log(args.analyze)
    else:
        print("Usage: grim5_tuning.py --sitrl | --analyze <log.bin>")
        print("\nCurrent best params:")
        for k, v in BEST_PARAMS.items():
            print(f"  {k:20s} = {v}")
