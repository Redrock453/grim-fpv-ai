# CLAUDE.md — GRIM-FPV-AI

> **Victoria, senior FPV & RF systems engineer.**
> *Precision engineering. No hallucinations. Use physics.*

---

## Користувач
- **Ім'я:** Adam
- **Стиль:** українська розмовна, мат ок, коротко
- **Контекст:** розробка бойових FPV систем, резюме для бойового підрозділу

---

## Огляд проекту

**GRIM-FPV-AI** — AI-powered FPV інженерна платформа для 5" бойового FPV дрона **ГРІМ-5**. FastAPI бекенд + 7 математичних калькуляторів + multi-AI рушії (Groq/Gemini/GLM/Claude) + емулятор бойових місій + ArduPilot PID тюнер + SLAM/MAVLink архітектура.

### Специфікація ГРІМ-5 (`drone_specs/grim5_config.json`)

| Параметр | Значення |
|----------|----------|
| Рама | iFlight XL5 Pro 5" |
| Мотори | T-Motor U8 Pro 2000KV |
| ESC | 40A BLheli_32, 6S |
| AUW | 865g |
| Батарея | 6S 850mAh 75C (18.87Wh, 22.2V) |
| Гвинти | 5045 Carbon |
| Тяга | 4.2 кг (TWR 4.86) |
| VTX | TBS Unify Pro32 (600mW) |
| RX | ExpressLRS 2.4GHz + Crossfire Nano RX |
| FC | SpeedyBee F405 V4 / Pixhawk 6X |
| GPS | UBLOX M9N (dual antenna) |
| LiDAR | Benewake TF02 Pro (40m) |

---

## Архітектура

```
grim-fpv-ai/
├── api/
│   ├── fastapi_server.py       ← 9 ендпоінтів, Pydantic models
│   └── models.py               ← Усі request/response моделі
│
├── calculators/                ← Чисті функції. Немає I/O, немає DB.
│   ├── flight_time_calc.py     Час польоту: (Wh / W) * 60 * sag
│   ├── hover_current.py        Струм у зависанні: (weight/thrust) * max_current
│   ├── rf_link_budget.py       FSPL + link budget + watts_to_dbm
│   ├── thermal_rf.py           PA heat: P_heat = P_out/eff - P_out
│   ├── thermal_analysis.py     Повний тепловий аналіз моторів/ESC
│   ├── range_calc.py           Дальність зв'язку
│   └── pid_tuning.py           PID рекомендації для Betaflight
│
├── ai_engines/                 ← Multi-AI інтеграція
│   ├── groq_engine.py          Groq API (Llama-3, Mixtral)
│   ├── gemini_engine.py        Google Gemini 2.0 Flash
│   ├── glm_engine.py           GLM через z.ai проксі
│   ├── grok_engine.py          Grok AI
│   └── claude_engine.py        Anthropic Claude
│
├── ai/                         ← Computer Vision pipeline
│   ├── detector.py             YOLOv8 + TensorRT/NCNN
│   └── tracker.py              ByteTrack + Hungarian algorithm
│
├── core/                       ← Autonomous flight core
│   ├── data_contracts.py       DTO для всієї системи
│   ├── state_machine.py        HFSM (Hierarchical Finite State Machine)
│   ├── event_bus.py            Async event-driven архітектура
│   ├── mavlink_client.py       MAVLink транспорт
│   └── world_model.py          Модель світу + SLAM fusion
│
├── slam/                       ← SLAM інтеграція
│   ├── openvins_bridge.py      OpenVINS bridge
│   └── sensor_sync.py          Синхронізація сенсорів
│
├── ardupilot/                  ← ArduPilot SITL
│   ├── grim5_tuning.py         PID auto-tuner
│   ├── custom_modes.md         Кастомні режими (auto-launch + RTL)
│   └── pid_tuned.params        Тюнінг для вітру 10 м/с
│
├── flight_simulator.py         ← Емулятор бойових місій (5 типів)
├── drone_specs/
│   └── grim5_config.json       Single source of truth
├── prompts/
│   ├── rf_engineer_system.md   Victoria RF персона
│   ├── fpv_engineer_system.md  FPV engineer персона
│   └── calculation_templates.md Jinja-шаблони
├── utils/
│   ├── config.py               dotenv loader
│   └── db_sqlite.py            aiosqlite (calculations log)
├── tests/
│   └── test_calculations.py    unittest
├── MISSION_LOG.md              Інженерний лог
└── COMBAT_JOURNAL.md           Бойовий щоденник (ПРИВАТНИЙ)
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

| Method | Path | Calculator | Опис |
|--------|------|------------|------|
| GET | `/health` | — | Статус системи |
| POST | `/calculate/flight-time` | `flight_time_calc` | Час польоту |
| POST | `/calculate/hover-current` | `hover_current` | Струм у зависанні |
| POST | `/calculate/rf-link` | `rf_link_budget` | RF link budget |
| POST | `/calculate/rf-thermal` | `thermal_rf` | Тепловий розрахунок PA |
| POST | `/calculate/thermal` | `thermal_analysis` | Повний тепловий аналіз |
| POST | `/calculate/range` | `range_calc` | Дальність зв'язку |
| POST | `/calculate/pid` | `pid_tuning` | PID рекомендації |
| POST | `/calculate/multi-ai` | `groq+gemini+glm` | Multi-AI аналіз |

**Значення за замовчуванням:** `sag_factor=0.85`, `tx_gain_dbi=4.0`, `rx_gain_dbi=2.0`, `fade_margin_db=10.0`, `efficiency=0.4`

**RSSI:** `> -90` → Strong, `<= -90` → Weak
**Thermal:** `p_heat > 10W` → Critical

---

## Калькулятори

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

### flight_time_calc
```python
flight_minutes = (battery_wh / avg_power_watts) * 60 * sag_factor
# ГРІМ-5: 18.87Wh / 150W * 60 * 0.85 = 6.42 хв
```

### hover_current
```python
hover_current = (weight_g / thrust_kg) * max_current_a * 0.25
# ГРІМ-5: 865г / 4.2кг * 40A * 0.25 = 8.24A
```

### pid_tuning
```python
roll_P = 45 + (kv - 2000) * 0.01
pitch_P = 50 + (kv - 2000) * 0.01
yaw_P = 30 + (kv - 2000) * 0.01
# ГРІМ-5: 2000KV → roll_P=45, pitch_P=50, yaw_P=30
```

---

## Місії (Flight Simulator)

### Типи місій
| Тип | Позивний | Тривалість | Макс. висота | Макс. швидкість | Призначення |
|-----|----------|------------|--------------|-----------------|-------------|
| recon | HAWK | 180 сек | 80 м | 19 м/с | Розвідка маршруту, фотографування об'єктів |
| intercept | VIPER | 120 сек | 50 м | 32 м/с | Перехоплення та супровід цілі, високі навантаження |
| loiter | OWL | 300 сек | 100 м | 12 м/с | Баражування над зоною, тривалий моніторинг |
| strike | FALCON | 90 сек | 40 м | 33 м/с | Зближення з ціллю на максимальній швидкості, ухилення |
| delivery | PELICAN | 240 сек | 60 м | 14 м/с | Доставка вантажу (500г), повернення на базу |

### Фази польоту
1. **Takeoff** (0-5 сек) — зліт до 80% максимальної висоти
2. **Cruise** — крейсерський політ за маршрутом
3. **Mission phase** — виконання завдання (розвідка, перехоплення тощо)
4. **Return** — повернення на базу
5. **Landing** (останні 10 сек) — посадка

### Телеметрія
Кожна місія генерує повну телеметрію:
- Координати (lat, lon) з базової точки
- Висота, швидкість, курс
- Батарея (лінійне зменшення)
- RSSI (залежить від відстані)
- Roll, pitch, yaw, throttle
- Режим (takeoff, cruise, landing)

---

## Multi-AI Integration

### Движки
| Engine | Провайдер | Модель | Призначення |
|--------|-----------|--------|-------------|
| Groq | groq.com | llama-3.3-70b | Швидкий inference, прості розрахунки |
| Gemini | Google AI | gemini-2.0-flash | Глибокий аналіз, multimodal |
| GLM | z.ai проксі | glm-5.1 | Основна модель, кодинг |
| Grok | xAI | grok-2 | Альтернативний аналіз |
| Claude | Anthropic | claude-sonnet | Векторний аналіз, архітектура |

### Використання
```python
# Запит до кількох AI одночасно
response = await multi_ai_analyze(
    query="Аналіз характеристик польоту для 5\" FPV дрона",
    engines=["gemini", "glm", "groq"]
)
```

### Конфігурація
Додати API ключі до `.env`:
```
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here
GLM_API_KEY=your_glm_key_here
CLAUDE_API_KEY=your_claude_key_here
GROK_API_KEY=your_grok_key_here
```

---

## MAVLink Integration

### Підключення
```python
# FastAPI підключається до SITL
mavlink_url = os.getenv("MAVLINK_URL", "tcp:localhost:5760")
sitl_master = mavutil.mavlink_connection(mavlink_url)
```

### Команди
```python
# Takeoff
await mavlink_client.send_takeoff(altitude=1.0)

# Land
await mavlink_client.send_land()

# Return to home
await mavlink_client.send_return_to_home()

# Set position
await mavlink_client.send_position(pose, altitude)
```

### Конвертація координат
OpenVINS повертає ENU, MAVLink очікує NED:
```
x_NED = -x_ENU
y_NED = -y_ENU  
z_NED = z_ENU
```

---

## Deployment

### Docker (рекомендовано)
```bash
docker-compose up -d
```

### Локальний запуск
```bash
pip install -r requirements.txt
cp .env.example .env
# Додати API ключі
uvicorn api.fastapi_server:app --host 0.0.0.0 --port 8000 --reload
```

### Порти
| Port | Protocol | Призначення |
|------|----------|-------------|
| 5760 | TCP | MAVLink TCP (SITL ↔ FastAPI) |
| 14550 | UDP | MAVLink UDP (QGroundControl) |
| 8000 | TCP | FastAPI + Веб-панель |

---

## Розробка

### Структура коду
- **calculators/** — чисті функції, без I/O
- **api/** — HTTP layer, валідація
- **core/** — бізнес-логіка, state machine
- **ai_engines/** — інтеграція з зовнішніми AI

### Тестування
```bash
python -m pytest tests/ -v
```

### Логування
```python
logger.info(f"[MAV] Підключення до SITL на {mavlink_url}")
logger.error(f"[AI] Помилка API: {e}")
```

---

## Використання

### Приклад запиту
```bash
curl -X POST "http://localhost:8000/calculate/flight-time" \
  -H "Content-Type: application/json" \
  -d '{"battery_wh": 18.87, "avg_power_watts": 150}'
```

### Відповідь
```json
{
  "flight_time_min": 6.42,
  "params": {
    "wh": 18.87,
    "watts": 150.0,
    "sag": 0.85
  }
}
```

### Веб-панель
Відкрити `http://localhost:8000/dashboard/` для:
- Мапи з позицією дрона
- Телеметрії в реальному часі
- Графіків батареї та швидкості
- Керування місіями

---

## Troubleshooting

### SITL не підключається
1. Перевірити `MAVLINK_URL` у `.env` (має бути `tcp:sitl:5760`)
2. Переконатися, що SITL контейнер запущений
3. Перевірити логи: `docker logs grim-fpv-sitl`

### AI не працює
1. Перевірити API ключі у `.env`
2. Переконатися, що інтернет підключення є
3. Перевірити квоти API

### Веб-панель не оновлюється
1. Перевірити WebSocket підключення у консолі браузера
2. Переконатися, що FastAPI генерує телеметрію
3. Перевірити CORS налаштування

---

## Контакти

- **Lead Engineer:** Victoria (AI)
- **GitHub:** https://github.com/Redrock453/grim-fpv-ai
- **Telegram бот:** @vika_fpv_bot

---

*Документація для системи GRIM-FPV-AI*
*Оновлено: 2026-04-14*