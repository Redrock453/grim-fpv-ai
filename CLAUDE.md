# CLAUDE.md — GRIM-FPV-AI

> **Victoria, senior FPV & RF systems engineer.**
> *Precision engineering. No hallucinations. Use physics.*

---

## User
- **Имя:** Adam
- **Стиль:** русский разговорный, мат ок, кратко
- **Контекст:** разработка боевых FPV систем, резюме для боевого подразделения

---

## Project Overview

**GRIM-FPV-AI** — AI-powered FPV engineering platform для 5" боевого FPV дрона **ГРІМ-5**. FastAPI бэкенд + 7 математических калькуляторов + multi-AI движки (Groq/Gemini/GLM/Claude) + эмулятор боевых миссий + ArduPilot PID тюнер + SLAM/MAVLink архитектура.

### ГРІМ-5 Specs (`drone_specs/grim5_config.json`)

| Параметр | Значение |
|----------|----------|
| Рама | iFlight XL5 Pro 5" |
| Моторы | T-Motor U8 Pro 2000KV |
| ESC | 40A BLheli_32, 6S |
| AUW | 865g |
| Батарея | 6S 850mAh 75C (18.87Wh, 22.2V) |
| Пропы | 5045 Carbon |
| Тяга | 4.2 кг (TWR 4.86) |
| VTX | TBS Unify Pro32 (600mW) |
| RX | ExpressLRS 2.4GHz + Crossfire Nano RX |
| FC | SpeedyBee F405 V4 / Pixhawk 6X |
| GPS | UBLOX M9N (dual antenna) |
| LiDAR | Benewake TF02 Pro (40m) |

---

## Architecture

```
grim-fpv-ai/
├── api/
│   ├── fastapi_server.py       ← 9 эндпоинтов, Pydantic models
│   └── models.py               ← Все request/response модели
│
├── calculators/                ← Чистые функции. Нет I/O, нет DB.
│   ├── flight_time_calc.py     Время полёта: (Wh / W) * 60 * sag
│   ├── hover_current.py        Ток висения: (weight/thrust) * max_current
│   ├── rf_link_budget.py       FSPL + link budget + watts_to_dbm
│   ├── thermal_rf.py           PA heat: P_heat = P_out/eff - P_out
│   ├── thermal_analysis.py     Полный тепловой анализ моторов/ESC
│   ├── range_calc.py           Дальность связи
│   └── pid_tuning.py           PID рекомендации для Betaflight
│
├── ai_engines/                 ← Multi-AI интеграция
│   ├── groq_engine.py          Groq API (Llama-3, Mixtral)
│   ├── gemini_engine.py        Google Gemini 2.0 Flash
│   ├── glm_engine.py           GLM через z.ai прокси
│   ├── grok_engine.py          Grok AI
│   └── claude_engine.py        Anthropic Claude
│
├── ai/                         ← Computer Vision pipeline
│   ├── detector.py             YOLOv8 + TensorRT/NCNN
│   └── tracker.py              ByteTrack + Hungarian algorithm
│
├── core/                       ← Autonomous flight core
│   ├── data_contracts.py       DTO для всей системы
│   ├── state_machine.py        HFSM (Hierarchical Finite State Machine)
│   ├── event_bus.py            Async event-driven архитектура
│   ├── mavlink_client.py       MAVLink транспорт
│   └── world_model.py          Модель мира + SLAM fusion
│
├── slam/                       ← SLAM интеграция
│   ├── openvins_bridge.py      OpenVINS bridge
│   └── sensor_sync.py          Синхронизация сенсоров
│
├── ardupilot/                  ← ArduPilot SITL
│   ├── grim5_tuning.py         PID auto-tuner
│   ├── custom_modes.md         Кастомные режимы (auto-launch + RTL)
│   └── pid_tuned.params        Тюнинг для ветра 10 м/с
│
├── flight_simulator.py         ← Эмулятор боевых миссий (5 типов)
├── drone_specs/
│   └── grim5_config.json       Single source of truth
├── prompts/
│   ├── rf_engineer_system.md   Victoria RF персона
│   ├── fpv_engineer_system.md  FPV engineer персона
│   └── calculation_templates.md Jinja-шаблоны
├── utils/
│   ├── config.py               dotenv loader
│   └── db_sqlite.py            aiosqlite (calculations log)
├── tests/
│   └── test_calculations.py    unittest
├── MISSION_LOG.md              Инженерный лог
└── COMBAT_JOURNAL.md           Боевой дневник (ПРИВАТНЫЙ)
```

### Data Flow
```
HTTP Request → FastAPI → calculator pure function → JSON
                                        ↓
                              Multi-AI: Groq/Gemini/GLM → enrichment
                                        ↓
                              Flight Simulator → telemetry → mission report
                                        ↓
                              Core: MAVLink → State Machine → World Model
                                        ↓
                              AI: Camera → YOLOv8 → ByteTrack → SLAM
```

---

## API Endpoints

| Method | Path | Calculator | Описание |
|--------|------|------------|----------|
| GET | `/health` | — | Статус системы |
| POST | `/calculate/flight-time` | `flight_time_calc` | Время полёта |
| POST | `/calculate/hover-current` | `hover_current` | Ток висения |
| POST | `/calculate/rf-link` | `rf_link_budget` | RF link budget |
| POST | `/calculate/rf-thermal` | `thermal_rf` | Тепловой расчёт PA |
| POST | `/calculate/thermal` | `thermal_analysis` | Полный тепловой анализ |
| POST | `/calculate/range` | `range_calc` | Дальность связи |
| POST | `/calculate/pid` | `pid_tuning` | PID рекомендации |
| POST | `/calculate/multi-ai` | `groq+gemini+glm` | Multi-AI анализ |

**Default values:** `sag_factor=0.85`, `tx_gain_dbi=4.0`, `rx_gain_dbi=2.0`, `fade_margin_db=10.0`, `efficiency=0.4`

**RSSI:** `> -90` → Strong, `<= -90` → Weak
**Thermal:** `p_heat > 10W` → Critical

---

## Calculators

### rf_link_budget
```python
FSPL(dB) = 20*log10(d_km) + 20*log10(f_MHz) + 32.44
RSSI = Tx_dbm + Gtx + Grx - FSPL - fade_margin
watts_to_dbm(W) = 10*log10(W * 1000)
```

### thermal_rf
```python
P_in = P_out / efficiency
P_heat = P_in - P_out
# ГРІМ-5 default: 30W out, eff=0.4 → 45W heat
```

### thermal_analysis
Полный тепловой анализ моторов и ESC с учётом ambient temperature.

### pid_tuning
Рекомендации PID для Betaflight на основе KV мотора, размера пропов и веса.

### range_calc
Расчёт максимальной дальности связи на основе TX мощности и antenna gain.

### flight_time_calc
```python
flight_time = (battery_wh / power_watts) * 60 * sag_factor
# ГРІМ-5: 18.87Wh / 150W * 60 * 0.85 ≈ 6.41 мин
```

### hover_current
```python
hover_current = (weight_kg / thrust_kg) * max_current
```

---

## AI Engines & Model Router

### Конфигурация Multi-AI
| Engine | Провайдер | Модель | Назначение |
|--------|-----------|--------|------------|
| Groq | groq.com | llama-3.3-70b | Быстрый inference, простые расчёты |
| Gemini | Google AI | gemini-2.0-flash | Глубокий анализ, multimodal |
| GLM | z.ai прокси | glm-5.1 | Основная модель, кодинг |
| Grok | xAI | grok-2 | Альтернативный анализ |
| Claude | Anthropic | claude-sonnet | Векторный анализ, архитектура |

### Роутинг логика (проектируемая)
```
Простой расчёт → Groq (быстро, дёшево)
Анализ данных → Gemini (multimodal)
Код/архитектура → GLM-5.1 (умная, дорогая)
FPV эксперт → Victoria persona через любой engine
```

### Victoria-стиль
- Точные инженерные расчёты, **никакой халлюцинации**
- Физика и формулы вместо общих фраз
- "No hallucinations. Use physics."
- Surgical implementation, minimal diffs

---

## Flight Simulator

Эмулятор боевых FPV миссий (`flight_simulator.py`):

| Тип миссии | Позывной | Описание |
|------------|----------|----------|
| `recon` | HAWK | Разведка маршрута |
| `intercept` | VIPER | Перехват и сопровождение |
| `loiter` | OWL | Барражирование |
| `strike` | FALCON | Сближение с целью |
| `delivery` | PELICAN | Доставка груза |

Генерирует реалистичную телеметрию:
- GPS координаты с дрифтом
- Батарея: 6S voltage model + расход по throttle
- RF: RSSI через FSPL от distance
- Ветер: переменный, влияет на drift
- Аэродинамика: roll/pitch/yaw с turbulence

```bash
# Запуск эмулятора
python flight_simulator.py
# → Генерирует mission_data.json с 8 миссиями
```

---

## ArduPilot Integration

### PID Auto-Tuner (`ardupilot/grim5_tuning.py`)
```bash
python ardupilot/grim5_tuning.py --sitrl   # Generate sweep plan
python ardupilot/grim5_tuning.py --analyze logs/flight.bin  # Score tune
```

### Результаты тюнинга (5" FPV, ветер 10 м/с)
| Параметр | Stock | Tuned |
|----------|-------|-------|
| Rate P | 0.15 | 0.135 |
| Rate I | 0.02 | 0.018 |
| Rate D | 0.005 | 0.0045 |
| FLTT/FLTD | — | 15Hz |
| Roll в ветер | ±8-15° | ±2-5° |

### Кастомный режим: auto-launch + RTL
`CUSTOM_AUTO_LAUNCH = 20` — auto-arm → hover 5m → RTL

---

## Commands

```bash
# Установка
pip install -r requirements.txt
cp .env.example .env

# API сервер
python -m uvicorn api.fastapi_server:app --host 0.0.0.0 --port 8000 --reload

# Калькуляторы standalone
python calculators/flight_time_calc.py    # → ~6.41 min
python calculators/hover_current.py       # → ~37.08 A
python calculators/rf_link_budget.py      # → 30W@433MHz, 50km
python calculators/thermal_rf.py          # → 45W heat @ 30W out

# Эмулятор миссий
python flight_simulator.py               # → mission_data.json

# Тесты
python -m pytest tests/ -v
```

---

## Key Patterns & Rules

1. **Calculators = pure functions.** Нет side effects, нет DB, нет API.
2. **Каждый calculator имеет `__main__`** с GRIM-5 дефолтами.
3. **RF расчёты в dBm/dBi/dB.** Конвертация watts_to_dbm — на границе API.
4. **`api/models.py`** — единое место для всех Pydantic моделей.
5. **AI engines** — async, возвращают `{"ai": name, "status": ok/error, "response": text}`.
6. **`.env` = секреты.** Никогда не коммитить.
7. **Victoria-стиль:** Precision engineering. No hallucinations. Surgical implementation.
8. **Flight simulator** — генерирует реалистичные данные для портфолио.

---

## Dependencies

```
fastapi        — API framework
uvicorn        — ASGI server
pydantic       — Data validation
python-dotenv  — .env loader
aiohttp        — Async HTTP client
httpx          — Async HTTP (AI engines)
requests       — Sync HTTP
aiosqlite      — Async SQLite (calculations log)
```

---

## Branches

Все ветки смерджены в **master**:
- `fast_api` — enhanced API + multi-AI + extended calculators
- `ardupilot-tweaks` — PID auto-tuner + SITL
- `dev` — core modules + MAVLink + SLAM
- `grok` — YOLOv8 + ByteTrack + AI pipeline

---

## Harness Rules

- Calculator модули = pure functions, без side effects
- Новые калькуляторы — в `calculators/` с `__main__` блоком
- AI engines — async, error-tolerant (return_exceptions=True)
- Не трогать `COMBAT_JOURNAL.md` — приватный
- Секреты — только в `.env`, GitHub push protection включён
- Flight simulator данные — для демонстрации, не для production
