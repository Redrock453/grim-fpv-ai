"""
Flight Simulator & Mission Emulator для ГРІМ-5
Генерирует реалистичные телеметрические данные FPV миссий.
Используется для демонстрации capabilities и как портфолио.
"""

import json
import math
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class TelemetryPoint:
    timestamp: str
    lat: float
    lon: float
    alt_m: float
    speed_ms: float
    heading_deg: float
    battery_pct: float
    voltage: float
    current_a: float
    rssi_dbm: float
    roll: float
    pitch: float
    yaw: float
    throttle_pct: float
    mode: str


@dataclass
class Mission:
    mission_id: str
    mission_type: str
    callsign: str
    start_time: str
    duration_sec: int
    max_alt_m: float
    max_speed_ms: float
    distance_m: float
    battery_start_pct: float
    battery_end_pct: float
    status: str
    notes: str
    telemetry: List[dict]


# Базовые координаты (пример — тренировочная зона)
BASE_LAT = 48.4567
BASE_LON = 35.0422

# Характеристики ГРІМ-5
GRIM5 = {
    "max_speed_ms": 35,
    "cruise_speed_ms": 18,
    "max_alt_m": 120,
    "battery_cells": 6,
    "battery_capacity_mah": 850,
    "battery_full_voltage": 25.2,
    "battery_empty_voltage": 21.0,
    "hover_current_a": 12,
    "max_current_a": 80,
    "weight_g": 865,
    "frame": "iFlight XL5 Pro 5\"",
    "motors": "T-Motor U8 Pro 2000KV",
}


def _voltage_from_pct(pct: float) -> float:
    """Линейная модель напряжения батареи 6S"""
    return GRIM5["battery_empty_voltage"] + \
        (GRIM5["battery_full_voltage"] - GRIM5["battery_empty_voltage"]) * (pct / 100)


def _simulate_battery_drain(speed_ms: float, throttle_pct: float) -> float:
    """Расход батареи в %/сек в зависимости от throttle"""
    base_drain = 0.05  # %/сек hover
    load_factor = (throttle_pct / 50) ** 1.5
    return base_drain * load_factor


def _wind_effect(t: float) -> tuple:
    """Симуляция ветра — меняется со временем"""
    wind_speed = 3 + 5 * math.sin(t / 30) + 2 * math.sin(t / 7)
    wind_dir = 180 + 30 * math.sin(t / 45)
    return wind_speed, wind_dir


def generate_mission(
    mission_type: str = "recon",
    duration_sec: int = 180,
    wind_magnitude: float = 5.0,
    pilot_skill: str = "experienced"
) -> Mission:
    """Генерация полной миссии с телеметрией"""

    mission_id = f"GRIM5-{datetime.now().strftime('%Y%m%d')}-{random.randint(100,999)}"

    configs = {
        "recon": {
            "callsign": "HAWK",
            "max_alt": 80,
            "cruise_speed": 15,
            "notes": "Разведка маршрута, фотографирование объектов"
        },
        "intercept": {
            "callsign": "VIPER",
            "max_alt": 50,
            "cruise_speed": 25,
            "notes": "Перехват и сопровождение цели, высокие нагрузки"
        },
        "loiter": {
            "callsign": "OWL",
            "max_alt": 100,
            "cruise_speed": 10,
            "notes": "Барражирование над зоной, длительный мониторинг"
        },
        "strike": {
            "callsign": "FALCON",
            "max_alt": 40,
            "cruise_speed": 28,
            "notes": "Сближение с целью на максимальной скорости, уклонение"
        },
        "delivery": {
            "callsign": "PELICAN",
            "max_alt": 60,
            "cruise_speed": 12,
            "notes": "Доставка груза (500г), возврат на базу"
        },
    }

    cfg = configs.get(mission_type, configs["recon"])
    start_time = datetime.now() - timedelta(seconds=duration_sec)

    telemetry = []
    lat, lon = BASE_LAT, BASE_LON
    battery_pct = 100.0
    total_distance = 0.0
    max_alt = 0.0
    max_speed = 0.0
    heading = random.uniform(0, 360)

    for i in range(duration_sec):
        t = i
        phase = "loiter"

        # Фазы полёта
        if t < 5:
            phase = "takeoff"
            alt = min(t * 6, cfg["max_alt"] * 0.8)
            speed = t * 3
            throttle = 70 + random.uniform(-5, 5)
        elif t > duration_sec - 10:
            phase = "landing"
            progress = (duration_sec - t) / 10
            alt = cfg["max_alt"] * progress * 0.5
            speed = max(3, cfg["cruise_speed"] * progress)
            throttle = 30 + random.uniform(-5, 5)
        elif mission_type == "intercept" and 30 < t < duration_sec - 40:
            phase = "intercept"
            alt = cfg["max_alt"] * (0.4 + 0.3 * math.sin(t / 10))
            speed = cfg["cruise_speed"] + 10 * math.sin(t / 5)
            throttle = 65 + 20 * math.sin(t / 8) + random.uniform(-8, 8)
        elif mission_type == "strike" and 20 < t < duration_sec - 30:
            phase = "attack_run"
            alt = cfg["max_alt"] * 0.3 + 5 * math.sin(t / 3)
            speed = GRIM5["max_speed_ms"] * 0.8 + 5 * math.sin(t / 4)
            throttle = 85 + random.uniform(-5, 10)
        elif mission_type == "loiter":
            phase = "orbit"
            orbit_radius = 50
            angle = t * 0.15
            lat = BASE_LAT + orbit_radius * math.cos(angle) / 111000
            lon = BASE_LON + orbit_radius * math.sin(angle) / (111000 * math.cos(math.radians(BASE_LAT)))
            alt = cfg["max_alt"] + 5 * math.sin(t / 20)
            speed = cfg["cruise_speed"] * 0.6
            throttle = 40 + random.uniform(-3, 3)
        elif mission_type == "delivery":
            if t < duration_sec * 0.4:
                phase = "outbound"
                alt = cfg["max_alt"]
                speed = cfg["cruise_speed"]
                throttle = 55 + random.uniform(-3, 3)
            elif t < duration_sec * 0.5:
                phase = "drop"
                alt = cfg["max_alt"] * 0.5
                speed = 3
                throttle = 35
            else:
                phase = "return"
                alt = cfg["max_alt"] * 0.8
                speed = cfg["cruise_speed"] * 1.1
                throttle = 50 + random.uniform(-3, 3)
        else:
            phase = "cruise"
            alt = cfg["max_alt"] * (0.6 + 0.3 * math.sin(t / 25))
            speed = cfg["cruise_speed"] + 3 * math.sin(t / 10)
            throttle = 45 + 10 * math.sin(t / 15) + random.uniform(-5, 5)

        # Влияние ветра
        wind_speed, wind_dir = _wind_effect(t)
        wind_drift = wind_speed * 0.1 * math.sin(math.radians(heading - wind_dir))

        # Обновление позиции
        if phase not in ["orbit"]:
            lat += (speed * math.cos(math.radians(heading)) + wind_drift * 0.5) / 111000
            lon += (speed * math.sin(math.radians(heading)) + wind_drift * 0.3) / \
                (111000 * math.cos(math.radians(BASE_LAT)))
            heading = (heading + 3 * math.sin(t / 12) + random.uniform(-2, 2)) % 360

        # Телеметрия
        alt += random.uniform(-1.5, 1.5)
        speed = max(0, speed + random.uniform(-1, 1))
        current = GRIM5["hover_current_a"] * (throttle / 45)
        rssi = -55 - 20 * math.log10(max(0.1, total_distance / 100 + 0.5)) + random.uniform(-3, 3)

        roll = 15 * math.sin(t / 8) + random.uniform(-3, 3)
        pitch = 8 * math.sin(t / 12) + random.uniform(-2, 2)
        yaw = heading + random.uniform(-5, 5)

        battery_pct -= _simulate_battery_drain(speed, throttle)
        battery_pct = max(0, battery_pct)

        point = TelemetryPoint(
            timestamp=(start_time + timedelta(seconds=t)).isoformat(),
            lat=round(lat, 6),
            lon=round(lon, 6),
            alt_m=round(alt, 1),
            speed_ms=round(speed, 1),
            heading_deg=round(heading, 1),
            battery_pct=round(battery_pct, 1),
            voltage=round(_voltage_from_pct(battery_pct), 2),
            current_a=round(current, 1),
            rssi_dbm=round(rssi, 1),
            roll=round(roll, 1),
            pitch=round(pitch, 1),
            yaw=round(yaw, 1),
            throttle_pct=round(throttle, 1),
            mode=phase
        )

        telemetry.append(asdict(point))

        if i > 0:
            d_lat = telemetry[-1]["lat"] - telemetry[-2]["lat"]
            d_lon = telemetry[-1]["lon"] - telemetry[-2]["lon"]
            total_distance += math.sqrt((d_lat * 111000) ** 2 + (d_lon * 111000) ** 2)

        max_alt = max(max_alt, alt)
        max_speed = max(max_speed, speed)

        if battery_pct <= 5:
            break

    return Mission(
        mission_id=mission_id,
        mission_type=mission_type,
        callsign=cfg["callsign"],
        start_time=start_time.isoformat(),
        duration_sec=len(telemetry),
        max_alt_m=round(max_alt, 1),
        max_speed_ms=round(max_speed, 1),
        distance_m=round(total_distance, 1),
        battery_start_pct=100.0,
        battery_end_pct=round(battery_pct, 1),
        status="completed" if battery_pct > 10 else "rtl",
        notes=cfg["notes"],
        telemetry=telemetry
    )


def generate_mission_report(mission: Mission) -> str:
    """Генерация текстового отчёта миссии"""
    m = mission
    avg_speed = sum(t["speed_ms"] for t in m.telemetry) / len(m.telemetry)
    avg_alt = sum(t["alt_m"] for t in m.telemetry) / len(m.telemetry)
    min_rssi = min(t["rssi_dbm"] for t in m.telemetry)
    max_current = max(t["current_a"] for t in m.telemetry)
    avg_throttle = sum(t["throttle_pct"] for t in m.telemetry) / len(m.telemetry)

    report = f"""
{'='*60}
  ОТЧЁТ МИССИИ: {m.mission_id}
  Тип: {m.mission_type.upper()} | Позывной: {m.callsign}
{'='*60}

  ВРЕМЯ:          {m.start_time}
  ДЛИТЕЛЬНОСТЬ:   {m.duration_sec} сек ({m.duration_sec/60:.1f} мин)
  ДИСТАНЦИЯ:      {m.distance_m:.0f} м ({m.distance_m/1000:.2f} км)
  МАКС. ВЫСОТА:   {m.max_alt_m:.1f} м
  МАКС. СКОРОСТЬ:  {m.max_speed_ms:.1} м/с ({m.max_speed_ms*3.6:.0f} км/ч)
  СРЕДН. СКОРОСТЬ: {avg_speed:.1f} м/с ({avg_speed*3.6:.0f} км/ч)
  СРЕДН. ВЫСОТА:  {avg_alt:.1f} м
  МАКС. ТОК:      {max_current:.1f} A

  БАТАРЕЯ:        {m.battery_start_pct:.0f}% → {m.battery_end_pct:.1f}%
  РАСХОД:         {m.battery_start_pct - m.battery_end_pct:.1f}%
  СРЕДН. THROTTLE: {avg_throttle:.1f}%

  RF:
  МИН. RSSI:      {min_rssi:.1f} dBm
  СТАТУС СВЯЗИ:   {'STABLE' if min_rssi > -85 else 'MARGINAL'}

  СТАТУС МИССИИ:  {m.status.upper()}
  ЗАМЕТКИ:        {m.notes}

{'='*60}
  ДРОН: ГРІМ-5 | {GRIM5['frame']} | {GRIM5['motors']}
  ВЕС: {GRIM5['weight_g']}г | БАТАРЕЯ: {GRIM5['battery_cells']}S {GRIM5['battery_capacity_mah']}mAh
{'='*60}
"""
    return report


def generate_portfolio_missions() -> List[Mission]:
    """Генерация набора миссий для портфолио/резюме"""
    missions = []
    scenarios = [
        ("recon", 180, 3.0),
        ("intercept", 120, 6.0),
        ("loiter", 300, 4.0),
        ("strike", 90, 7.0),
        ("delivery", 240, 2.0),
        ("recon", 150, 8.0),  # ветер сильный
        ("intercept", 100, 5.0),
        ("loiter", 360, 1.0),
    ]

    for mtype, dur, wind in scenarios:
        missions.append(generate_mission(mtype, dur, wind))

    return missions


if __name__ == "__main__":
    # Демо: генерация миссий и отчётов
    print("ГРІМ-5 Flight Simulator — Portfolio Mode\n")

    missions = generate_portfolio_missions()
    for m in missions:
        print(generate_mission_report(m))

    # Сохранить JSON для API
    with open("mission_data.json", "w") as f:
        json.dump([asdict(m) for m in missions], f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(missions)} missions to mission_data.json")
