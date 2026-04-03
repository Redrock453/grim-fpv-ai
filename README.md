# GRIM-FPV-AI

FPV AI Engineering Agent для проекта **ГРІМ-5** (5-дюймовый боевой дрон).

## Спецификация ГРІМ-5
- **Рама:** iFlight XL5 Pro, 5"
- **Моторы:** T-Motor U8 Pro 2000KV
- **ESC:** 40A BLheli_32 (6S)
- **Вес:** ~865г AUW
- **Батарея:** 6S 850mAh 75C (18.87Wh)
- **Тяга:** ~4.2кг (TWR 4.86)
- **Пропы:** 5045 Carbon
- **TX:** ExpressLRS 2.4GHz, 500mW

## Установка

```bash
git clone https://github.com/redrock453/grim-fpv-ai.git
cd grim-fpv-ai
pip install -r requirements.txt
cp .env.example .env  # добавьте API ключи
```

## Запуск API

```bash
python -m uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8000
```

### Примеры запросов

**Расчёт времени полёта:**
```bash
curl -X POST "http://localhost:8000/calculate/flight-time" \
     -H "Content-Type: application/json" \
     -d '{"battery_wh": 18.87, "avg_power_watts": 150}'
```

**RF link budget (30W booster, 50km):**
```bash
curl -X POST "http://localhost:8000/calculate/rf-link" \
     -H "Content-Type: application/json" \
     -d '{"freq_mhz": 433, "distance_km": 50, "tx_power_watts": 30}'
```

**Тепловой расчёт PA:**
```bash
curl -X POST "http://localhost:8000/calculate/rf-thermal" \
     -H "Content-Type: application/json" \
     -d '{"p_out_watts": 30, "efficiency": 0.4}'
```

## Структура проекта
- `calculators/` — чистые математические модули (flight time, hover current, RF link budget, thermal)
- `ai_engines/` — интеграция с Grok, Gemini и Claude
- `api/` — FastAPI сервер
- `drone_specs/` — конфигурации дронов (JSON)
- `prompts/` — system prompts для Victoria AI persona
- `ardupilot/` — PID params, custom modes, tuning tools

---

## ArduPilot Tweaks (03.04.2026)

Работаю с ArduPilot на уровне прошивки для FPV-боевых дронов:

### PID-тюнинг (5" FPV, ветер 8-12 м/с)

Тюнинговал rate controller для стабильного полёта в порывистом ветре без осцилляций.

**Стартовые значения (stock):**
- Rate Roll/Pitch: P=0.15, I=0.02, D=0.005
- Проблема: осцилляции roll +/-8-15° в ветре 10 м/с, integral windup на порывах

**После тюнинга** (см. `ardupilot/pid_tuned.params`):
- Rate Roll/Pitch: P=0.135, I=0.018, D=0.0045
- Фильтры: FLTT/FLTD=15Hz, FLTE=2Hz
- Gyro/accel filter: 20Hz
- Результат: roll +/-2-5° в ветре 10 м/с, rate error <12 deg/s

**Лог тюнинга:** `ardupilot/grim5_mission.txt` — 3 тестовых полёта (stock → tuned → stress test 14 м/с)

### Кастомный режим: auto-launch + RTL

Минимальный патч (на основе форка ArduCopter 4.5.x):

В `ArduCopter/mode.h`:
```cpp
enum modes {
    ...
    CUSTOM_AUTO_LAUNCH = 20,  // auto-arm → hover → RTL
    ...
};
```

В `mode.cpp`:
```cpp
case CUSTOM_AUTO_LAUNCH:
    // 2 сек задержка после арма, затем взлёт на 5м + RTL
    if (millis() - last_arm_time > 2000) {
        set_mode(MODE_LOITER);
    }
    break;
```

Полный форк с патчами — приватно, готов показать на собеседовании.

**Параметры RTL:** см. `ardupilot/custom_modes.md` — геофенс 2км, RTL 30м, скорость возврата 15 м/с.

### SITL Auto-Tuner

Скрипт `ardupilot/grim5_tuning.py` — генерация PID sweep для SITL:
```bash
python ardupilot/grim5_tuning.py --sitrl   # generate sweep plan
python ardupilot/grim5_tuning.py --analyze logs/flight.bin  # score tune
```

### Оборудование
- Pixhawk 6X (STM32H743)
- GPS: UBLOX M9N (dual antenna)
- Rangefinder: Benewake TF02 Pro (LiDAR 40m)
- Telemetry: ExpressLRS 2.4GHz

Готов к Rarog: PID, миссии, кастом под боевые сценарии. Без фейков.
