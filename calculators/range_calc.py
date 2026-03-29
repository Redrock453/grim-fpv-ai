"""
Расчёт дальности FPV для ExpressLRS 500mW + антенны.
"""
from typing import Dict

def calculate_range(tx_power_mw: int = 500, antenna_gain_db: float = 3.0, rx_sensitivity_dbm: float = -110.0) -> Dict[str, float]:
    # Упрощённая формула Friis + эмпирика для 2.4GHz в открытом поле
    free_space_loss_db = 20 * 3.0 + 20 * 2.4 + 32.44  # базовое
    max_loss_db = tx_power_mw / 1000 * 30 + antenna_gain_db * 2 - rx_sensitivity_dbm
    range_km = 10 ** ((max_loss_db - free_space_loss_db) / 20) / 1000
    return {
        "range_km": round(range_km, 1),
        "realistic_range_km": round(range_km * 0.65, 1),  # с учётом помех/земли
        "notes": "Теоретическая дальность в открытом поле"
    }
