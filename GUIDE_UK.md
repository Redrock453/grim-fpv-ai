# 📚 Єдиний посібник по GRIM-FPV-AI

*Об'єднання всієї документації з репозиторію*
*Версія: 1.0 | Дата: 2026-04-14*

---

## 📋 Зміст

1. [Огляд системи](#огляд-системи)
2. [Швидкий старт](#швидкий-старт)
3. [Архітектура](#архітектура)
4. [API Endpoints](#api-endpoints)
5. [Калькулятори](#калькулятори)
6. [Місії](#місії)
7. [Налаштування SITL](#налаштування-sitl)
8. [Веб-панель](#веб-панель)
9. [Операційна інформація](#операційна-інформація)
10. [Вирішення проблем](#вирішення-проблем)

---

## 🎯 Огляд системи

**GRIM-FPV-AI** — AI-powered FPV інженерна платформа для 5" бойового FPV дрона **ГРІМ-5**.

### Основні можливості:
- **7 математичних калькуляторів** для інженерних розрахунків
- **5 типів бойових місій** з емуляцією
- **Multi-AI аналіз** (Groq/Gemini/GLM/Claude/Grok)
- **Веб-панель** з картою та телеметрією в реальному часі
- **ArduPilot SITL** інтеграція
- **MAVLink** транспорт для керування дроном

### Специфікація ГРІМ-5:
| Параметр | Значення |
|----------|----------|
| Рама | iFlight XL5 Pro, 5" |
| Мотори | T-Motor U8 Pro 2000KV |
| ESC | 40A BLheli_32 (6S) |
| Вага | ~865г AUW |
| Батарея | 6S 850mAh 75C (18.87Wh) |
| Тяга | ~4.2кг (TWR 4.86) |
| Гвинти | 5045 Carbon |
| VTX | TBS Unify Pro32 (600mW) |
| Приймач | ExpressLRS 2.4GHz, 500mW + Crossfire Nano RX |
| FC | SpeedyBee F405 V4 / Pixhawk 6X (STM32H743) |
| GPS | UBLOX M9N (dual antenna) |
| Дальномір | Benewake TF02 Pro (LiDAR 40m) |

---

## 🚀 Швидкий старт

### Docker розгортання (VPS Ubuntu 2 CPU 8GB RAM):
```bash
git clone https://github.com/Redrock453/grim-fpv-ai.git
cd grim-fpv-ai
cp .env.example .env
docker-compose up -d
```

### Порти:
| Port | Protocol | Призначення |
|------|----------|-------------|
| 5760 | TCP | MAVLink TCP (SITL ↔ FastAPI) |
| 14550 | UDP | MAVLink UDP (QGroundControl) |
| 8000 | TCP | FastAPI + Веб-панель |

### Сервіси:
- **Веб-панель:** `http://VPS_IP:8000/dashboard/`
- **API Docs:** `http://VPS_IP:8000/docs`
- **QGroundControl:** `udp://VPS_IP:14550`

---

## 🏗️ Архітектура

### Структура проекту:
```
grim-fpv-ai/
├── api/                 # FastAPI сервер + моделі
├── calculators/         # 7 математичних калькуляторів
├── ai_engines/         # Multi-AI інтеграція
├── ai/                 # Computer Vision pipeline
├── core/               # Autonomous flight core
├── slam/               # SLAM інтеграція
├── ardupilot/          # ArduPilot SITL
├── flight_simulator.py # Емулятор бойових місій
├── drone_specs/        # Конфігурації дронів
├── prompts/            # System prompts для AI
└── utils/              # Утиліти, config, DB
```

### Data Flow:
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

## 📡 API Endpoints

### Калькулятори (POST):
| Endpoint | Опис |
|----------|------|
| `/calculate/flight-time` | Розрахунок часу польоту |
| `/calculate/hover-current` | Струм у зависанні |
| `/calculate/rf-link` | RF link budget |
| `/calculate/rf-thermal` | Тепловий розрахунок TX |
| `/calculate/thermal` | Повний тепловий аналіз |
| `/calculate/range` | Дальність зв'язку |
| `/calculate/pid` | Рекомендації PID |
| `/calculate/multi-ai` | Multi-AI аналіз |

### Місії:
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/mission/start` | POST | Запуск місії (потребує SITL) |
| `/mission/status` | GET | Статус поточної місії |
| `/mission/stop` | POST | Зупинка місії (RTL) |
| `/missions/portfolio` | GET | Портфоліо завершених місій |
| `/missions/{type}/simulate` | GET | Симуляція місії за типом |
| `/simulate/mission` | GET | Симуляція місії (параметр ?type=) |

### Телеметрія та моніторинг:
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/telemetry/latest` | GET | Остання телеметрія |
| `/health` | GET | Статус системи |
| `/ws/telemetry` | WebSocket | Стрім телеметрії в реальному часі |

---

## 🧮 Калькулятори

### 1. Час польоту (`/calculate/flight-time`)
```bash
curl -X POST "http://localhost:8000/calculate/flight-time" \
  -H "Content-Type: application/json" \
  -d '{"battery_wh": 18.87, "avg_power_watts": 150}'
```
**Відповідь:** `{"flight_time_min":6.42,"params":{"wh":18.87,"watts":150.0,"sag":0.85}}`

### 2. RF link budget (`/calculate/rf-link`)
```bash
curl -X POST "http://localhost:8000/calculate/rf-link" \
  -H "Content-Type: application/json" \
  -d '{"freq_mhz": 5800, "distance_km": 2.5, "tx_power_watts": 0.6}'
```
**Відповідь:** `{"tx_power_dbm":27.78,"path_loss_db":115.67,"rssi_dbm":-91.89,"status":"Weak"}`

### 3. Тепловий аналіз TX (`/calculate/rf-thermal`)
```bash
curl -X POST "http://localhost:8000/calculate/rf-thermal" \
  -H "Content-Type: application/json" \
  -d '{"p_out_watts": 0.6, "efficiency": 0.35}'
```
**Відповідь:** `{"p_out_watts":0.6,"p_total_in_watts":1.71,"p_heat_watts":1.11,"efficiency_pct":35.0,"status":"Manageable"}`

### 4. PID рекомендації (`/calculate/pid`)
```bash
curl -X POST "http://localhost:8000/calculate/pid" \
  -H "Content-Type: application/json" \
  -d '{"kv": 2000, "prop_size": "5045", "weight_g": 865}'
```
**Відповідь:** `{"roll":{"P":45,"I":35,"D":22},"pitch":{"P":50,"I":35,"D":24},"yaw":{"P":30,"I":25,"D":0}}`

### 5. Струм у зависанні (`/calculate/hover-current`)
```bash
curl -X POST "http://localhost:8000/calculate/hover-current" \
  -H "Content-Type: application/json" \
  -d '{"kv": 2000, "battery_cells": 6, "prop_size": "5045", "weight_g": 865, "thrust_kg": 4.2, "max_current_a": 40}'
```
**Відповідь:** `{"hover_current_a":8.24,"params":{"weight":865.0,"thrust":4.2,"max_current":40.0}}`

### 6. Дальність зв'язку (`/calculate/range`)
```bash
curl -X POST "http://localhost:8000/calculate/range" \
  -H "Content-Type: application/json" \
  -d '{"freq_mhz": 5800, "tx_power_watts": 0.6, "rx_sensitivity_dbm": -95, "antenna_gain_tx_dbi": 4, "antenna_gain_rx_dbi": 3}'
```
**Відповідь:** `{"range_km":44.39,"realistic_range_km":28.85,"tx_power_dbm":27.0,"max_path_loss_db":133.0}`

### 7. Тепловий аналіз (`/calculate/thermal`)
```bash
curl -X POST "http://localhost:8000/calculate/thermal" \
  -H "Content-Type: application/json" \
  -d '{"motor_count": 4, "motor_current_a": 15, "esc_efficiency": 0.95, "ambient_temp_c": 25}'
```
**Відповідь:** `{"esc_temp_c":67.0,"motor_temp_c":88.0,"warning":"OK","notes":"Розрахунок при безперервному польоті, без обдуву"}`

### 8. Multi-AI аналіз (`/calculate/multi-ai`)
```bash
curl -X POST "http://localhost:8000/calculate/multi-ai" \
  -H "Content-Type: application/json" \
  -d '{"calculation_type": "flight_analysis", "params": {"kv": 2000, "battery_cells": 6, "prop_size": "5045"}, "engines": ["gemini"]}'
```
*Потребує налаштування API ключів у .env файлі*

---

## 🎯 Місії

### Типи місій:
1. **recon** (розвідка) - позивний HAWK
2. **intercept** (перехоплення) - позивний VIPER
3. **loiter** (баражування) - позивний OWL
4. **strike** (удар) - позивний FALCON
5. **delivery** (доставка) - позивний PELICAN

### Запуск симульованої місії:
```bash
# Розвідка
curl "http://localhost:8000/simulate/mission?type=recon"

# Перехоплення
curl "http://localhost:8000/simulate/mission?type=intercept"

# Баражування
curl "http://localhost:8000/simulate/mission?type=loiter"

# Удар
curl "http://localhost:8000/simulate/mission?type=strike"

# Доставка
curl "http://localhost:8000/simulate/mission?type=delivery"
```

### Запуск "реальної" місії (потребує SITL):
```bash
curl -X POST "http://localhost:8000/mission/start" \
  -H "Content-Type: application/json" \
  -d '{"mission_type": "recon", "callsign": "HAWK", "duration_sec": 120}'
```

### Приклади завершених місій:
```
Місія #1: HAWK — Розвідка маршруту
Тип: recon | Тривалість: 3 хв | Дистанція: 2.7 км
Макс. висота: 78 м | Макс. швидкість: 19 м/с (68 км/год)
Батарея: 100% → 72% | Витрата: 28%

Місія #2: VIPER — Перехоплення цілі
Тип: intercept | Тривалість: 2 хв | Дистанція: 3.1 км
Макс. висота: 48 м | Макс. швидкість: 32 м/с (115 км/год)
Батарея: 100% → 41% | Витрата: 59%

Місія #3: OWL — Баражування
Тип: loiter | Тривалість: 5 хв | Дистанція: 1.8 км
Макс. висота: 104 м | Макс. швидкість: 12 м/с (43 км/год)
Батарея: 100% → 55% | Витрата: 45%
```

---

## 🛠️ Налаштування SITL

### Проблема:
SITL Docker образ не запускається (падає з помилкою 127).

### Рішення:
1. **Перевірити Docker образ:**
```bash
docker build -t grim-fpv-ai-sitl-fixed -f Dockerfile.sitl .
```

2. **Запустити вручну:**
```bash
docker run -d --name grim-fpv-sitl \
  -p 5760:5760 -p 14550:14550/udp \
  grim-fpv-ai-sitl-fixed
```

3. **Налаштувати підключення FastAPI:**
У `docker-compose.yml` встановити:
```yaml
environment:
  - MAVLINK_URL=tcp:sitl:5760  # Без "//"
```

### Альтернатива: Використовувати зовнішній SITL
1. Встановити ArduPilot на хост-машині
2. Запустити: `sim_vehicle.py -v ArduCopter -f quad --out tcp:0.0.0.0:5760`
3. Налаштувати FastAPI на підключення до `localhost:5760`

---

## 🖥️ Веб-панель

### Доступ:
- `http://[IP_машини]:8000/dashboard/`
- Через Tailscale: `http://100.123.130.38:8000/dashboard/`
- Публічно: `http://68.183.101.60:8000/dashboard/` (якщо порт відкритий)

### Функції:
1. **Карта** з позицією дрона (Leaflet.js)
2. **Панель телеметрії**: батарея, швидкість, висота, RSSI, режим, throttle
3. **Графіки в реальному часі** (Chart.js)
4. **Кнопки керування місіями**: Recon, Intercept, Loiter, Strike, Delivery, Stop
5. **WebSocket підключення** для live даних

### WebSocket:
```javascript
// Підключення до WebSocket
const ws = new WebSocket('ws://' + window.location.host + '/ws/telemetry');
```

---

## 📊 Операційна інформація

### Поточний статус (з COMBAT_JOURNAL.md):
- ✅ **grim-fpv-ai** (GitHub PUBLIC) — FPV інженерія
- ✅ **secrets-vault** (GitHub PRIVATE) — усі ключі
- ✅ **vika_ok v15.6** (DO Droplet) — Telegram агент
- ✅ **vika_fpv_bot** (Telegram) — FPV AI бот
- ⏳ **Telegram-bot міграція** — FastAPI → aiogram

### Організація:
```
В'ЯЧЕСЛАВ (ти):
  ✅ CEO + Decision maker

CLAUDE (браузер):
  ✅ FPV інженер (розрахунки, рекомендації)
  ✅ RF інженер (link budget, дальність)
  ✅ AI аналітик (multi-AI аналіз)

VIKA (Telegram бот):
  ✅ FPV AI асистент
  ✅ Сповіщення про місії
  ✅ Статус системи
```

### AI Models:
- ✅ Gemini 3-flash-preview (основний)
- ✅ Groq llama-3.3-70b
- ✅ DO Agent

---

## 🔧 Вирішення проблем

### Проблема 1: SITL не запускається
**Симптом:** Docker контейнер падає з кодом 127
**Рішення:**
1. Перевірити Dockerfile.sitl на помилки
2. Спробувати зібрати образ заново
3. Використовувати емулятор замість SITL

### Проблема 2: "SITL недоступний" на панелі
**Симптом:** На панелі відображається "SITL недоступний"
**Причина:** FastAPI не може підключитися до SITL
**Рішення:**
1. Перевірити формат MAVLINK_URL (має бути `tcp:sitl:5760` без `//`)
2. Переконатися, що контейнери в одній мережі Docker
3. Перевірити розв'язання імені `sitl` з контейнера API

### Проблема 3: Місії не запускаються
**Симптом:** `/mission/start` повертає помилку або місія не "злітає"
**Причина:** Проблема з підключенням до SITL або емулятором
**Рішення:**
1. Використовувати `/simulate/mission` замість `/mission/start`
2. Перевірити логи FastAPI на помилки підключення
3. Переконатися, що SITL запущений і приймає підключення

### Проблема 4: Multi-AI не працює
**Симптом:** `/calculate/multi-ai` повертає помилки API
**Причина:** Не налаштовані API ключі
**Рішення:**
1. Додати API ключі у `.env` файл:
```
GROK_API_KEY=your_grok_key_here
GEMINI_API_KEY=your_gemini_key_here
GLM_API_KEY=your_glm_key_here
CLAUDE_API_KEY=your_claude_key_here
GROQ_API_KEY=your_groq_key_here
```
2. Перезапустити контейнер API

### Проблема 5: Веб-панель не оновлюється
**Симптом:** Дані на панелі не змінюються
**Причина:** Проблема з WebSocket підключенням
**Рішення:**
1. Перевірити консоль браузера на помилки WebSocket
2. Переконатися, що WebSocket endpoint доступний
3. Перевірити, чи генерує емулятор дані

---

## 📝 Корисні команди

### Моніторинг:
```bash
# Перевірка здоров'я API
curl http://localhost:8000/health

# Остання телеметрія
curl http://localhost:8000/telemetry/latest

# Статус місії
curl http://localhost:8000/mission/status

# Портфоліо місій
curl http://localhost:8000/missions/portfolio
```

### Docker керування:
```bash
# Запуск усіх сервісів
cd /root/grim-fpv-ai && docker-compose up -d

# Зупинка усіх сервісів
cd /root/grim-fpv-ai && docker-compose down

# Перегляд логів API
docker logs grim-fpv-api --tail 50

# Перегляд логів SITL
docker logs grim-fpv-sitl --tail 50

# Перезапуск API
docker restart grim-fpv-api
```

### Тестування:
```bash
# Тест усіх калькуляторів
./test_all_missions.py

# Тест однієї місії
curl "http://localhost:8000/simulate/mission?type=recon"

# Тест WebSocket (використовувати wscat або браузер)
wscat -c ws://localhost:8000/ws/telemetry
```

---

## 🔗 Корисні посилання

### Внутрішні:
- **Swagger UI:** `http://localhost:8000/docs`
- **Веб-панель:** `http://localhost:8000/dashboard/`
- **Git репозиторій:** `https://github.com/Redrock453/grim-fpv-ai`

### Зовнішні:
- **ArduPilot документація:** http://ardupilot.org/
- **MAVLink протокол:** https://mavlink.io/
- **QGroundControl:** https://qgroundcontrol.com/

### Документація в репозиторії:
1. `CLAUDE.md` - повний технічний опис
2. `COMBAT_JOURNAL.md` - операційний статус
3. `MISSION_LOG.md` - інженерний лог
4. `ardupilot/PRESET_METHODOLOGY.md` - налаштування ArduPilot
5. `prompts/` - системні промпти для AI

---

## 🎯 Рекомендації щодо використання

### Для інженерних розрахунків:
1. Використовуйте калькулятори для точних розрахунків
2. Перевіряйте RF link budget перед польотами на дальність
3. Моніторьте теплові характеристики компонентів

### Для тестування місій:
1. Використовуйте `/simulate/mission` для швидкого тестування
2. Аналізуйте телеметрію симульованих місій
3. Тестуйте різні типи місій для розуміння характеристик

### Для розробки:
1. Вивчіть архітектуру в `CLAUDE.md`
2. Використовуйте Swagger UI для тестування API
3. Перевіряйте логи при проблемах з підключенням

### Для production використання:
1. Поліпшіть SITL для реального симулювання польотів
2. Налаштуйте API ключі для Multi-AI аналізу
3. Налаштуйте моніторинг та логування

---

## 📞 Підтримка

### Контакти:
- **Lead Engineer:** Victoria (AI)
- **CEO:** В'ячеслав
- **Telegram бот:** @vika_fpv_bot

### Канали зв'язку:
1. **GitHub Issues:** https://github.com/Redrock453/grim-fpv-ai/issues
2. **Telegram:** @vika_fpv_bot
3. **Внутрішня документація:** COMBAT_JOURNAL.md

---

## 🔄 Оновлення

### Останні зміни (з MISSION_LOG.md):
- **2026-04-03:** Major Platform Upgrade
  - 7 калькуляторів
  - 5 AI engines
  - Core архітектура
  - Flight Simulator з 5 типами місій

### Плани на майбутнє:
1. Поліпшити SITL Docker образ
2. Додати більше типів місій
3. Покращити веб-панель
4. Додати інтеграцію з реальним дроном

---

*Документація створена на основі аналізу репозиторію GRIM-FPV-AI*
*Оновлено: 2026-04-14*
*Автор: Victoria (AI Assistant)*