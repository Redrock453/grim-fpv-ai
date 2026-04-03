# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## User
- **Имя:** Adam (он же Вячеслав)
- **Стиль:** русский разговорный, мат ок, кратко

## Project Overview

GRIM-5 FPV AI Engineering Agent — расчётный и AI-инструмент для 5" боевого FPV дрона **ГРІМ-5** и 30W 433MHz RF-бустера (BEASTFPV). FastAPI бэкенд + чистые математические калькуляторы + multi-AI движки.

### ГРІМ-5 Specs (источник: `drone_specs/grim5_config.json`)
| Параметр | Значение |
|----------|----------|
| Рама | iFlight XL5 Pro 5" |
| Моторы | T-Motor U8 Pro 2000KV |
| ESC | 40A BLheli_32, 6S |
| AUW | 865g |
| Батарея | 6S 850mAh 75C (18.87Wh, 22.2V) |
| Пропы | 5045 Carbon |
| Тяга | 4.2 кг (TWR 4.86) |
| TX | ExpressLRS 2.4GHz, 500mW |

### AI Persona: Victoria
Senior RF & FPV Systems Engineer. Системные промпты в `prompts/`:
- `rf_engineer_system.md` — основная персона: 340-440MHz PAs, link budget, thermal, ELRS, anti-EW
- `fpv_engineer_system.md` — FPV инженер: расчёты, компоненты, тюнинг
- `calculation_templates.md` — Jinja-шаблоны для AI-запросов

**Victoria-стиль:** точные инженерные расчёты, никакой халлюцинации, физика. "No hallucinations. Use physics."

## Commands

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск API сервера
python -m uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8000

# Запуск всех тестов
python -m pytest tests/ -v

# Запуск одного теста
python -m pytest tests/test_calculations.py::TestCalculations::test_flight_time -v

# Запуск калькуляторов standalone (у каждого __main__ с GRIM-5 дефолтами)
python calculators/flight_time_calc.py    # → ~6.41 min
python calculators/hover_current.py       # → ~37.08 A
python calculators/rf_link_budget.py      # → 30W@433MHz, 50km
python calculators/thermal_rf.py          # → 45W heat @ 30W out
```

## Architecture

```
grim-fpv-ai/
├── api/
│   ├── fastapi_server.py     ← Точка входа. 6 эндпоинтов. Pydantic models inline.
│   └── models.py             ← Устаревшие модели (не используются сервером)
│
├── calculators/              ← Чистые функции. Нет I/O, нет DB, нет API.
│   ├── flight_time_calc.py   Flight time: (Wh / W) * 60 * sag_factor
│   ├── hover_current.py      Hover current: (weight_kg / thrust_kg) * max_current
│   ├── rf_link_budget.py     FSPL: 20log(d) + 20log(f) + 32.44
│   │                           Link budget: Tx + Gtx + Grx - path_loss - fade
│   │                           watts_to_dbm(): 10*log10(W*1000)
│   └── thermal_rf.py         PA heat: P_in = P_out/eff, P_heat = P_in - P_out
│
├── ai_engines/               ← STUB. async get_{grok,gemini,claude}_response(prompt)
│   ├── grok_engine.py          Все возвращают placeholder строки.
│   ├── gemini_engine.py        TODO: подключить реальные API.
│   └── claude_engine.py
│
├── drone_specs/
│   └── grim5_config.json     ← Single source of truth для параметров дрона
│
├── prompts/                  ← System prompts для Victoria AI
│   ├── rf_engineer_system.md   Основная персона (RF + EW + thermal)
│   ├── fpv_engineer_system.md  FPV engineer persona
│   └── calculation_templates.md Jinja-style шаблоны
│
├── utils/
│   ├── config.py             dotenv loader (DEBUG, DATABASE_URL)
│   └── db_sqlite.py          aiosqlite init — таблица calculations, НЕ подключена к API
│
├── tests/
│   └── test_calculations.py  unittest — только flight_time_calc
│
├── .env.example              GROK_API_KEY, GEMINI_API_KEY, CLAUDE_API_KEY
├── requirements.txt          fastapi, uvicorn, requests, aiohttp, pydantic, dotenv, aiosqlite
├── MISSION_LOG.md            Инженерный лог Victoria
└── COMBAT_JOURNAL.md         Боевой дневник проекта (ПРИВАТНЫЙ контент)
```

### Data Flow
```
HTTP Request → FastAPI endpoint → calculator pure function → JSON response
                                                    ↓
                                          (DB logging TODO: db_sqlite.py не подключён)
```

## API Endpoints

| Method | Path | Input | Output | Calculator |
|--------|------|-------|--------|------------|
| GET | `/health` | — | `{status, project, lead}` | — |
| POST | `/calculate/flight-time` | `battery_wh, avg_power_watts, sag_factor?` | `flight_time_min` | `flight_time_calc` |
| POST | `/calculate/hover-current` | `weight_g, thrust_kg, max_current_a` | `hover_current_a` | `hover_current` |
| POST | `/calculate/rf-link` | `freq_mhz, distance_km, tx_power_watts, tx_gain_dbi?, rx_gain_dbi?, fade_margin_db?` | `tx_power_dbm, path_loss_db, rssi_dbm, status` | `rf_link_budget` |
| POST | `/calculate/rf-thermal` | `p_out_watts, efficiency?` | `p_total_in, p_heat, efficiency_pct, status` | `thermal_rf` |
| POST | `/calculate/multi-ai` | — | `{status: "simulation"}` | STUB |

**Default values:** `sag_factor=0.85`, `tx_gain_dbi=4.0`, `rx_gain_dbi=2.0`, `fade_margin_db=10.0`, `efficiency=0.4`

**RSSI thresholds:** `rssi > -90` → "Strong", else → "Weak"

**Thermal thresholds:** `p_heat > 10W` → "Critical Heat", else → "Manageable"

## Model Router (TODO)

AI engines — заглушки. Планируемый `model_router`:
- **Groq** — llama-3.3-70b (быстрый inference)
- **DeepSeek** — кодинг и анализ
- **GLM-5.1** — основная модель через z.ai прокси

Формат: `async def get_{engine}_response(prompt: str) -> str`

## Key Patterns & Rules

1. **Calculators = pure functions.** Нет side effects, нет DB, нет API. Только math + return.
2. **Каждый calculator имеет `__main__`** с GRIM-5 дефолтами для быстрой проверки.
3. **RF расчёты в dBm/dBi/dB.** Конвертация `watts_to_dbm()` — на границе API.
4. **`api/models.py` устарел** — сервер использует inline Pydantic модели. `api/models.py` не подключён.
5. **DB logging не подключён** — `db_sqlite.py::init_db()` существует, но не вызывается из API.
6. **`.env` = секреты.** Никогда не коммитить. Токены в `.gitignore`.
7. **Victoria-стиль:** Precision engineering. No hallucinations. Surgical implementation.

## Branches

| Branch | Purpose |
|--------|---------|
| `master` | Stable, main development |
| `dev` | Development branch |
| `fast_api` | FastAPI-specific changes |
| `grok` | Grok AI engine integration |

## Test Coverage

**Что покрыто:** `flight_time_calc` (2 теста: normal + zero_power)

**TODO:** тесты для `hover_current`, `rf_link_budget` (FSPL, link_budget, watts_to_dbm), `thermal_rf`

## Known Issues

- `api/models.py` дублирует Pydantic модели из `fastapi_server.py` — рассинхрон
- AI engines — заглушки, возвращают placeholder строки
- SQLite DB инициализируется но не используется в эндпоинтах
- Нет валидации граничных условий в RF калькуляторах (negative freq, zero distance edge cases)
- `COMBAT_JOURNAL.md` содержит чувствительные данные — не пушить в публичные репо

## Dependencies

```
fastapi       — API framework
uvicorn       — ASGI server
requests      — HTTP client (для AI engines)
aiohttp       — Async HTTP (для AI engines)
pydantic      — Data validation
python-dotenv — .env loader
aiosqlite     — Async SQLite (calculations log)
```

## Harness Rules

При работе с этим репо через Claude Code:
- Не добавлять AI SDK зависимости пока model_router не спроектирован
- Не трогать `COMBAT_JOURNAL.md` — приватный файл
- Следить за секретами — GitHub push protection включён
- Calculator модули должны оставаться pure functions
- Новые калькуляторы добавлять в `calculators/` с `__main__` блоком
