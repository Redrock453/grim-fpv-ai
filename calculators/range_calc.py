"""
Расчёт дальности FPV для ExpressLRS и других RF систем.
Использует уравнение Фрииса для радиосвязи.

FSPL (dB) = 20·log10(d_km) + 20·log10(f_MHz) + 32.44
Link Budget: received = tx_power_dbm + tx_gain + rx_gain - FSPL
Max range когда received = rx_sensitivity
"""
import math
from typing import Dict, Optional


def mw_to_dbm(mw: float) -> float:
    """Convert milliwatts to dBm."""
    if mw <= 0:
        return -999.0
    return 10 * math.log10(mw)


def fspl_db(distance_km: float, freq_mhz: float) -> float:
    """Free Space Path Loss in dB."""
    if distance_km <= 0 or freq_mhz <= 0:
        return 0.0
    return 20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44


def calculate_range(
    tx_power_mw: float = 500,
    tx_antenna_gain_db: float = 3.0,
    rx_antenna_gain_db: float = 3.0,
    rx_sensitivity_dbm: float = -110.0,
    frequency_mhz: float = 2400.0,
    fade_margin_db: float = 10.0,
) -> Dict[str, float]:
    """
    Calculate maximum range using Friis transmission equation.

    Args:
        tx_power_mw: Transmitter power in milliwatts (e.g. 500 for ExpressLRS)
        tx_antenna_gain_db: TX antenna gain in dBi
        rx_antenna_gain_db: RX antenna gain in dBi
        rx_sensitivity_dbm: Receiver sensitivity in dBm (lower = better)
        frequency_mhz: Operating frequency in MHz (2400 for 2.4GHz, 900 for 900MHz)
        fade_margin_db: Safety margin for fading/interference in dB

    Returns:
        Dictionary with theoretical and realistic range estimates.
    """
    tx_power_dbm = mw_to_dbm(tx_power_mw)

    # Total link budget available for path loss
    # max_path_loss = tx_power + gains - sensitivity - fade_margin
    max_path_loss_db = tx_power_dbm + tx_antenna_gain_db + rx_antenna_gain_db - rx_sensitivity_dbm - fade_margin_db

    if max_path_loss_db <= 0:
        return {
            "range_km": 0.0,
            "realistic_range_km": 0.0,
            "tx_power_dbm": round(tx_power_dbm, 1),
            "max_path_loss_db": round(max_path_loss_db, 1),
            "notes": "Недостаточно мощности для связи"
        }

    # Invert FSPL formula to solve for distance:
    # FSPL = 20·log10(d) + 20·log10(f) + 32.44
    # d = 10^((FSPL - 20·log10(f) - 32.44) / 20)
    freq_term = 20 * math.log10(frequency_mhz) + 32.44
    distance_km = 10 ** ((max_path_loss_db - freq_term) / 20)

    # Realistic range accounts for terrain, obstacles, multipath
    # ~65% of theoretical for open field, less in urban/forest
    realistic_range_km = distance_km * 0.65

    return {
        "range_km": round(distance_km, 2),
        "realistic_range_km": round(realistic_range_km, 2),
        "tx_power_dbm": round(tx_power_dbm, 1),
        "max_path_loss_db": round(max_path_loss_db, 1),
        "frequency_mhz": frequency_mhz,
        "notes": f"Теоретическая дальность в открытом поле ({frequency_mhz/1000:.1f}GHz)"
    }


def calculate_range_table(
    tx_power_mw: float = 500,
    tx_antenna_gain_db: float = 3.0,
    rx_antenna_gain_db: float = 3.0,
    rx_sensitivity_dbm: float = -110.0,
    frequency_mhz: float = 2400.0,
) -> list:
    """
    Generate a range table showing RSSI at various distances.

    Returns list of dicts with distance, FSPL, and estimated RSSI.
    """
    tx_power_dbm = mw_to_dbm(tx_power_mw)
    total_gain = tx_antenna_gain_db + rx_antenna_gain_db
    distances = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0]

    table = []
    for d in distances:
        loss = fspl_db(d, frequency_mhz)
        rssi = tx_power_dbm + total_gain - loss
        table.append({
            "distance_km": d,
            "fspl_db": round(loss, 1),
            "rssi_dbm": round(rssi, 1),
            "signal": "good" if rssi > -90 else ("weak" if rssi > rx_sensitivity_dbm else "lost")
        })

    return table
