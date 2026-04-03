"""
Тепловой анализ ГРІМ-5: температура ESC и моторов по току.
"""
from typing import Dict

def calculate_thermal(current_a_per_motor: float = 15.0, ambient_temp_c: float = 25.0) -> Dict[str, float]:
    # Простая эмпирическая формула (на основе типичных данных BLHeli + T-Motor)
    esc_temp_rise = current_a_per_motor * 2.8          # °C на ампер
    motor_temp_rise = current_a_per_motor * 4.2
    esc_temp = ambient_temp_c + esc_temp_rise
    motor_temp = ambient_temp_c + motor_temp_rise

    warning = "OK"
    if esc_temp > 85:
        warning = "⚠️ ESC перегрев!"
    if motor_temp > 95:
        warning = "⚠️ Моторы перегреваются!"

    return {
        "esc_temp_c": round(esc_temp, 1),
        "motor_temp_c": round(motor_temp, 1),
        "warning": warning,
        "notes": "Расчёт при непрерывном полёте, без обдува"
    }
