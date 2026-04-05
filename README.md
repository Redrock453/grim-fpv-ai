# GRIM-FPV-AI

**AI-powered FPV engineering platform для боевого дрона ГРІМ-5**

FPV AI Engineering Agent с полным стеком расчётов, multi-AI интеграцией и эмуляцией боевых миссий.

## Спецификация ГРІМ-5

| Параметр | Значение |
|----------|----------|
| Рама | iFlight XL5 Pro, 5" |
| Моторы | T-Motor U8 Pro 2000KV |
| ESC | 40A BLheli_32 (6S) |
| Вес | ~865г AUW |
| Батарея | 6S 850mAh 75C (18.87Wh) |
| Тяга | ~4.2кг (TWR 4.86) |
| Пропы | 5045 Carbon |
| VTX | TBS Unify Pro32 (600mW) |
| Приёмник | ExpressLRS 2.4GHz, 500mW + Crossfire Nano RX |
| Антенна TX | Lollipop 5.8GHz 4dBic |
| FC | SpeedyBee F405 V4 / Pixhawk 6X (STM32H743) |
| GPS | UBLOX M9N (dual antenna) |
| Rangefinder | Benewake TF02 Pro (LiDAR 40m) |

---

## Docker Deployment (VPS Ubuntu 2 CPU 8GB RAM)

```bash
# Clone and deploy
git clone https://github.com/Redrock453/grim-fpv-ai.git
cd grim-fpv-ai
cp .env.example .env
docker-compose up -d
```

This starts two containers:
- **SITL** — ArduPilot ArduCopter simulation (ArduCopter-4.5.0)
- **API** — FastAPI server with MAVLink telemetry, WebSocket, web dashboard

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 5760 | TCP | MAVLink TCP (SITL ↔ FastAPI) |
| 14550 | UDP | MAVLink UDP (QGroundControl) |
| 8000 | TCP | FastAPI + Web Dashboard |

### Services

- **Web Dashboard:** `http://VPS_IP:8000/dashboard/`
- **API Docs:** `http://VPS_IP:8000/docs`
- **QGroundControl:** `udp://VPS_IP:14550`

---

## QGroundControl on Android

1. Download QGroundControl APK: https://github.com/mavlink/QGroundControl/releases
2. Install on your Android tablet
3. Open QGroundControl → Settings → Comm Links
4. Add new UDP connection:
   - Type: UDP
   - Host: VPS_IP_ADDRESS
   - Port: 14550
5. Connect — you should see the simulated ArduCopter on the map

The SITL instance streams MAVLink data to UDP 14550, which QGC reads as if it were a real drone.

---

## Web Dashboard

Open `http://VPS_IP:8000` in any browser (tablet recommended):

- Live Leaflet.js map with drone position
- Telemetry panel: battery, speed, altitude, RSSI, mode, throttle
- Real-time Chart.js graphs (battery & speed)
- Mission control buttons: Recon, Intercept, Loiter, Strike, Delivery, Stop

---

## Architecture

```
┌─────────────┐     TCP 5760      ┌──────────────┐
│  ArduPilot  │ ──────────────────►│   FastAPI    │
│  SITL       │ ◄─────────────────│   Server     │
│  (Copter)   │    MAVLink        │   (Python)   │
└──────┬──────┘                   └──────┬───────┘
       │                                 │
  UDP  │ 14550                     WebSocket│
       │                                 │
┌──────▼──────┐                   ┌──────▼───────┐
│ QGroundCtrl │                   │  Browser     │
│ (Android)   │                   │  Dashboard   │
└─────────────┘                   └──────────────┘
```

---

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
| GET | `/missions/portfolio` | Портфолио миссий |
| GET | `/missions/{type}/simulate` | Симуляция миссии |
| GET | `/simulate/mission?type=recon` | Симуляция миссии (новый) |
| WS | `/ws/telemetry` | WebSocket стрим телеметрии |
| POST | `/mission/start` | Запуск миссии (SITL или симуляция) |
| POST | `/mission/stop` | Остановка миссии (RTL) |
| GET | `/telemetry/latest` | Последняя телеметрия |
| GET | `/mission/status` | Статус текущей миссии |

---

## Установка (локальная)

```bash
git clone https://github.com/Redrock453/grim-fpv-ai.git
cd grim-fpv-ai
pip install -r requirements.txt
cp .env.example .env
# Добавьте API ключи: GEMINI_API_KEY, GLM_API_KEY, GROQ_API_KEY
```

## Запуск (локальный)

```bash
python -m uvicorn api.fastapi_server:app --host 0.0.0.0 --port 8000 --reload
```

---

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

---

## Структура проекта

```
grim-fpv-ai/
├── ai_engines/          # AI движки (Groq, Gemini, Claude, GLM)
├── api/                 # FastAPI сервер + модели
│   ├── fastapi_server.py    # Основной сервер (обновлён)
│   ├── models.py            # Pydantic модели
│   └── static/              # Веб-дашборд (новый)
│       └── index.html       # Leaflet + Chart.js + WebSocket
├── ardupilot/           # PID тюнер для SITL + кастомные режимы
├── calculators/         # Математические модули (7 калькуляторов)
├── core/                # MAVLink, state machine, world model
├── drone_specs/         # Конфигурации дронов (JSON)
├── prompts/             # System prompts для AI
├── slam/                # OpenVINS интеграция
├── ai/                  # YOLOv8 detector + ByteTrack
├── tests/               # Тесты
├── utils/               # Утилиты, config, DB
├── docker-compose.yml   # Docker: SITL + FastAPI (новый)
├── Dockerfile.sitl      # ArduPilot SITL образ (новый)
├── Dockerfile.api       # FastAPI образ (новый)
└── flight_simulator.py  # Эмулятор боевых миссий
```

---

## ArduPilot Tweaks

### PID-тюнинг (5" FPV, ветер 8-12 м/с)

| Параметр | Stock | Tuned |
|----------|-------|-------|
| Rate P | 0.15 | 0.135 |
| Rate I | 0.02 | 0.018 |
| Rate D | 0.005 | 0.0045 |
| FLTT/FLTD | — | 15Hz |
| Roll в ветер | ±8-15° | ±2-5° |

### SITL Auto-Tuner

```bash
python ardupilot/grim5_tuning.py --sitrl   # generate sweep plan
python ardupilot/grim5_tuning.py --analyze logs/flight.bin  # score tune
```

---

## AI Engines

| Engine | Провайдер | Модель | Назначение |
|--------|-----------|--------|------------|
| Groq | groq.com | llama-3.3-70b | Быстрый inference, простые расчёты |
| Gemini | Google AI | gemini-2.0-flash | Глубокий анализ, multimodal |
| GLM | z.ai прокси | glm-5.1 | Основная модель, кодинг |
| Grok | xAI | grok-2 | Альтернативный анализ |
| Claude | Anthropic | claude-sonnet | Векторный анализ, архитектура |

- **Groq** — быстрые инференсы (Llama-3, Mixtral)
- **Gemini** — глубокий анализ (Google AI)
- **GLM** — через z.ai прокси
- **Claude** — Anthropic (векторный анализ)

---

## Лицензия

MIT
