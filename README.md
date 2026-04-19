# GRIM-FPV-AI

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**AI-платформа для бойових FPV-дронів**

Інтелектуальний інженерний агент для дрона **ГРІМ-5**.  
Повний стек розрахунків, мульти-AI інтеграція та симуляція бойових місій.

### Призначення

- Швидкі інженерні розрахунки параметрів дрона
- Симуляція та аналіз бойових завдань
- Моніторинг телеметрії у реальному часі
- Підтримка прийняття рішень у польових умовах

---

## QUICK START

```bash
# Клон
git clone https://github.com/Redrock453/grim-fpv-ai.git
cd grim-fpv-ai

# Конфіг
cp .env.example .env

# Запуск
docker-compose up -d
```

**Запускає два контейнери:**
- **SITL** — симуляція ArduPilot ArduCopter 4.5.0
- **API** — FastAPI + MAVLink телеметрія + WebSocket + веб-дашборд

### Порти

| Порт  | Протокол | Призначення                        |
|-------|----------|----------------------------------|
| 5760  | TCP      | MAVLink TCP (SITL ↔ FastAPI)     |
| 14550 | UDP      | MAVLink UDP (QGroundControl)     |
| 8000  | TCP      | FastAPI + Web Dashboard         |

### Доступ

- **Веб-дашборд:** `http://VPS_IP:8000`
- **Документація API:** `http://VPS_IP:8000/docs`
- **QGroundControl:** `udp://VPS_IP:14550`

---

## Специфікація ГРІМ-5

| Параметр     | Значення                              |
|-------------|--------------------------------------|
| Рама        | iFlight XL5 Pro, 5"                   |
| Мотори      | T-Motor U8 Pro 2000KV                 |
| ESC         | 40A BLHeli_32 (6S)                    |
| Вага        | ~865 г AUW                            |
| Батарея     | 6S 850mAh 75C (18.87 Вт·год)          |
| Тяга        | ~4.2 кг (TWR 4.86)                    |
| Пропелери   | 5045 Carbon                           |
| VTX         | TBS Unify Pro32 600 мВт               |
| Зв'язок     | ExpressLRS 2.4GHz 500мВт + Crossfire  |
| Антена TX   | Lollipop 5.8GHz 4dBic                 |
| FC          | SpeedyBee F405 V4 / Pixhawk 6X        |
| GPS         | UBLOX M9N (dual antenna)              |
| Далекомір   | Benewake TF02 Pro LiDAR 40м           |

---

## QGroundControl на Android

1. Завантажити APK: https://github.com/mavlink/QGroundControl/releases
2. Встановити на планшет
3. QGroundControl → Settings → Comm Links → New
4. Тип: UDP, Host: `VPS_IP`, Port: `14550`
5. Connect — симульований ArduCopter з'явиться на карті

---

## Веб-дашборд

- Карта Leaflet.js з позицією дрона в реальному часі
- Телеметрія: батарея, швидкість, висота, RSSI, режим, газ
- Графіки Chart.js (батарея та швидкість)
- Кнопки місій: Розвідка, Перехват, Loiter, Удар, Доставка, Стоп

---

## Архітектура

```
┌─────────────┐     TCP 5760      ┌──────────────┐
│  ArduPilot  │ ──────────────────►│   FastAPI    │
│  SITL       │ ◄─────────────────│   Server     │
│  (Copter)   │    MAVLink        │   (Python)   │
└──────┬──────┘                   └──────┬───────┘
       │                                 │
  UDP  │ 14550                    WebSocket│
       │                                 │
┌──────▼──────┐                   ┌──────▼───────┐
│ QGroundCtrl │                   │  Browser     │
│ (Android)  │                   │  Dashboard  │
└─────────────┘                   └──────────────┘
```

---

## API Endpoints

| Method | Endpoint                     | Опис                           |
|--------|-----------------------------|--------------------------------|
| GET    | `/health`                    | Статус системи                 |
| POST   | `/calculate/flight-time`      | Розрахунок часу польоту          |
| POST   | `/calculate/hover-current`   | Струм у висінні                  |
| POST   | `/calculate/rf-link`         | RF link budget                  |
| POST   | `/calculate/rf-thermal`      | Тепловий розрахунок TX         |
| POST   | `/calculate/thermal`        | Повний тепловий аналіз          |
| POST   | `/calculate/range`          | Дальність зв'язку               |
| POST   | `/calculate/pid`            | Рекомендації PID                |
| POST   | `/calculate/multi-ai`       | Мульти-AI аналіз             |
| GET    | `/missions/portfolio`      | Портфоліо місій               |
| GET    | `/missions/{type}/simulate` | Симуляція місії                |
| GET    | `/simulate/mission`        | Симуляція місії (альт.)          |
| WS     | `/ws/telemetry`           | WebSocket телеметрії             |
| POST   | `/mission/start`          | Запуск місії                   |
| POST   | `/mission/stop`           | Зупинка місії (RTL)          |
| GET    | `/telemetry/latest`       | Остання телеметрія            |

---

## Приклади запитів

```bash
# Час польоту
curl -X POST "http://localhost:8000/calculate/flight-time" \
     -H "Content-Type: application/json" \
     -d '{"battery_wh": 18.87, "avg_power_watts": 150}'

# RF link budget
curl -X POST "http://localhost:8000/calculate/rf-link" \
     -H "Content-Type: application/json" \
     -d '{"freq_mhz": 5800, "distance_km": 2.5, "tx_power_watts": 0.6}'

# Тепловий аналіз TX
curl -X POST "http://localhost:8000/calculate/rf-thermal" \
     -H "Content-Type: application/json" \
     -d '{"p_out_watts": 0.6, "efficiency": 0.35}'

# Рекомендації PID
curl -X POST "http://localhost:8000/calculate/pid" \
     -H "Content-Type: application/json" \
     -d '{"kv": 2000, "prop_size": "5045", "weight_g": 865}'
```

---

## ArduPilot / PID-тюнінг

**5" FPV, вітер 8–12 м/с**

| Параметр     | Stock  | Tuned   |
|-------------|-------|--------|
| Rate P      | 0.15  | 0.135  |
| Rate I      | 0.02  | 0.018  |
| Rate D      | 0.005 | 0.0045 |
| FLTT/FLTD   | —     | 15Hz   |
| Roll у вітер| ±8–15°| ±2–5°  |

```bash
python ardupilot/grim5_tuning.py --sitl            # генерація sweep-плану
python ardupilot/grim5_tuning.py --analyze logs/flight.bin  # аналіз тюну
```

---

## AI-двигуни

| Двигун  | Провайдер  | Модель            | Призначення                    |
|----------|------------|------------------|------------------------------|
| Groq     | groq.com   | llama-3.3-70b    | Швидкі розрахунки              |
| Gemini   | Google AI  | gemini-2.0-flash | Глибокий аналіз, multimodal |
| GLM      | z.ai      | glm-5.1          | Основна логіка, кодинг      |
| Grok     | xAI       | grok-2           | Альтернативний аналіз       |
| Claude   | Anthropic | claude-sonnet     | Векторний аналіз, архітектура |

---

## Структура проєкту

```
grim-fpv-ai/
├── ai_engines/          # Інтеграція LLM (Groq, Gemini, GLM, Claude)
├── api/                # FastAPI сервер + Pydantic моделі
│   └── static/         # Веб-дашборд (Leaflet + Chart.js + WebSocket)
├── ardupilot/          # SITL, PID-тюнер, кастомні режими
├── calculators/         # 7 математичних модулів
├── core/               # MAVLink, state machine, world model
├── drone_specs/        # Конфігурації дронів (JSON)
├── prompts/            # Системні промпти для AI
├── slam/              # OpenVINS інтеграція
├── ai/                # YOLOv8 детектор + ByteTrack
├── tests/              # Тести
├── utils/             # Утиліти, config, DB
├── docker-compose.yml
├── Dockerfile.sitl
├── Dockerfile.api
└── flight_simulator.py  # Емулятор бойових місій
```

---

## Локальна установка

```bash
pip install -r requirements.txt
cp .env.example .env
# Додати ключі: GEMINI_API_KEY, GLM_API_KEY, GROQ_API_KEY
python -m uvicorn api.fastapi_server:app --host 0.0.0.0 --port 8000 --reload
```

---

## CONTRIBUTING

1. Fork репозиторію
2. Створити branch: `git checkout -b feature/NAME`
3. Commit зміни: `git commit -m 'DESCRIPTION'`
4. Push до branch: `git push origin feature/NAME`
5. Створити Pull Request

**Вимоги:**
- PEP 8 compliant код
- Тести для нових калькуляторів
- Документація для нових ендпоінтів

---

## License

MIT