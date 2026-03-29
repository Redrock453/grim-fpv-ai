"""
Рекомендации PID для ГРІМ-5 (Betaflight) по KV, пропам и весу.
"""
from typing import Dict

def recommend_pid(kv: int = 2000, prop_size: str = "5045", weight_g: float = 865) -> Dict[str, dict]:
    # Эмпирические рекомендации для 5" 2000KV
    p_roll = 45 + (kv - 2000) / 50
    i_roll = 35
    d_roll = 22
    p_pitch = p_roll + 5
    i_pitch = i_roll
    d_pitch = d_roll + 2

    return {
        "roll": {"P": round(p_roll), "I": i_roll, "D": round(d_roll)},
        "pitch": {"P": round(p_pitch), "I": i_pitch, "D": round(d_pitch)},
        "yaw": {"P": 30, "I": 25, "D": 0},
        "notes": f"Рекомендации для {prop_size} на {weight_g}г. Тестируй в Betaflight!"
    }
