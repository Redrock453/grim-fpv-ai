# GRIM-FPV-AI

**AI-powered FPV engineering platform для боевого дрона ГРІМ-5**

FPV AI Engineering Agent с полным стеком расчётов, multi-AI интеграцией и эмуляцией боевых миссий.

## Спецификация ГРІМ-5
- **Рама:** iFlight XL5 Pro, 5"
- **Моторы:** T-Motor U8 Pro 2000KV
- **Вес:** ~865г
- **Батарея:** 6S 850mAh 75C (18.87Wh)
- **Тяга:** ~4.2кг (TWR 4.86)
- **VTX:** TBS Unify Pro32 (600mW)
- **Приёмник:** Crossfire Nano RX
- **Антенна TX:** Lollipop 5.8GHz 4dBic
- **FC:** SpeedyBee F405 V4

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
```

## Структура проекта

```
grim-fpv-ai/
├── ai_engines/          # AI движки (Groq, Gemini, Claude, GLM)
├── api/                 # FastAPI сервер + модели
├── ardupilot/           # PID тюнер для SITL
├── calculators/         # Математические модули (7 калькуляторов)
├── core/                # MAVLink, state machine, world model
├── drone_specs/         # Конфигурации дронов
├── prompts/             # System prompts для AI
├── slam/                # OpenVINS интеграция
├── ai/                  # YOLOv8 detector + ByteTrack
├── tests/               # Тесты
└── utils/               # Утилиты, config, DB
```

## AI Engines
- **Groq** — быстрые инференсы (Llama-3, Mixtral)
- **Gemini** — глубокий анализ (Google AI)
- **GLM** — через z.ai прокси
- **Claude** — Anthropic (векторный анализ)

## Лицензия
MIT
