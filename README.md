# GRIM-FPV-AI

**AI-powered FPV engineering platform для боевого дрона ГРІМ-5**

FPV AI Engineering Agent с полным стеком расчётов, multi-AI интеграцией и эмуляцией боевых миссий.

## Спецификация ГРІМ-5
- **Рама:** iFlight XL5 Pro, 5"
- **Моторы:** T-Motor U8 Pro 2000KV
- **ESC:** 40A BLheli_32 (6S)
- **Вес:** ~865г AUW
- **Батарея:** 6S 850mAh 75C (18.87Wh)
- **Тяга:** ~4.2кг (TWR 4.86)
- **Пропы:** 5045 Carbon
- **VTX:** TBS Unify Pro32 (600mW)
- **Приёмник:** ExpressLRS 2.4GHz, 500mW + Crossfire Nano RX
- **Антенна TX:** Lollipop 5.8GHz 4dBic
- **FC:** SpeedyBee F405 V4 / Pixhawk 6X (STM32H743)
- **GPS:** UBLOX M9N (dual antenna)
- **Rangefinder:** Benewake TF02 Pro (LiDAR 40m)

## Эндпоинты API

| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/health` | Статус системы |
| POST | `/calculate/flight-time` | Расчёт времени полёта |
| POST | `/calculate/hover-current` | Ток в висении |
| POST | `/calculate/rf-link` | RF link budget |
| POST | `/calculate/rf-thermal` | Тепловой расчёт TX |
| POST | `/calculate/thermal` | Полный тепловой анализ |
| POST | `/calculate/range` | Дальность связи |
| POST | `/calculate/pid` | Рекомендации PID |
| POST | `/calculate/multi-ai` | Multi-AI анализ (Gemini + GLM + Groq) |

## Установка

```bash
git clone https://github.com/Redrock453/grim-fpv-ai.git
cd grim-fpv-ai
pip install -r requirements.txt
cp .env.example .env
# Добавьте API ключи: GEMINI_API_KEY, GLM_API_KEY, GROQ_API_KEY
```

## Запуск

```bash
python -m uvicorn api.fastapi_server:app --host 0.0.0.0 --port 8000 --reload
```

## Примеры запросов

```bash
# Время полёта
curl -X POST "http://localhost:8000/calculate/flight-time" \
     -H "Content-Type: application/json" \
     -d '{"battery_wh": 18.87, "avg_power_watts": 150}'

# RF link budget
curl -X POST "http://localhost:8000/calculate/rf-link" \
     -H "Content-Type: application/json" \
     -d '{"freq_mhz": 5800, "distance_km": 2.5, "tx_power_watts": 0.6}'

# Тепловой анализ TX
curl -X POST "http://localhost:8000/calculate/rf-thermal" \
     -H "Content-Type: application/json" \
     -d '{"p_out_watts": 0.6, "efficiency": 0.35}'

# PID рекомендации
curl -X POST "http://localhost:8000/calculate/pid" \
     -H "Content-Type: application/json" \
     -d '{"kv": 2000, "prop_size": "5045", "weight_g": 865}'
```

## Структура проекта

```
grim-fpv-ai/
├── ai_engines/          # AI движки (Groq, Gemini, Claude, GLM)
├── api/                 # FastAPI сервер + модели
├── ardupilot/           # PID тюнер для SITL + кастомные режимы
├── calculators/         # Математические модули (7 калькуляторов)
├── core/                # MAVLink, state machine, world model
├── drone_specs/         # Конфигурации дронов (JSON)
├── prompts/             # System prompts для AI
├── slam/                # OpenVINS интеграция
├── ai/                  # YOLOv8 detector + ByteTrack
├── tests/               # Тесты
└── utils/               # Утилиты, config, DB
```

## ArduPilot Tweaks

### PID-тюнинг (5" FPV, ветер 8-12 м/с)

**Стартовые значения (stock):** P=0.15, I=0.02, D=0.005
**После тюнинга:** P=0.135, I=0.018, D=0.0045, roll +/-2-5° в ветер 10 м/с

### SITL Auto-Tuner
```bash
python ardupilot/grim5_tuning.py --sitrl   # generate sweep plan
python ardupilot/grim5_tuning.py --analyze logs/flight.bin  # score tune
```

## AI Engines
- **Groq** — быстрые инференсы (Llama-3, Mixtral)
- **Gemini** — глубокий анализ (Google AI)
- **GLM** — через z.ai прокси
- **Claude** — Anthropic (векторный анализ)

## Лицензия
MIT
