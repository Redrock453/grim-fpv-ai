# 📚 Единое руководство по GRIM-FPV-AI

*Объединение всей документации из репозитория*
*Версия: 1.0 | Дата: 2026-04-14*

---

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Быстрый старт](#быстрый-старт)
3. [Архитектура](#архитектура)
4. [API Endpoints](#api-endpoints)
5. [Калькуляторы](#калькуляторы)
6. [Миссии](#миссии)
7. [Настройка SITL](#настройка-sitl)
8. [Веб-дашборд](#веб-дашборд)
9. [Операционная информация](#операционная-информация)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 Обзор системы

**GRIM-FPV-AI** — AI-powered FPV engineering platform для 5" боевого FPV дрона **ГРІМ-5**.

### Основные возможности:
- **7 математических калькуляторов** для инженерных расчётов
- **5 типов боевых миссий** с эмуляцией
- **Multi-AI анализ** (Groq/Gemini/GLM/Claude/Grok)
- **Веб-дашборд** с картой и телеметрией в реальном времени
- **ArduPilot SITL** интеграция
- **MAVLink** транспорт для управления дроном

### Спецификация ГРІМ-5:
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
| FC | SpeedyBee F405 V4 / Pixhawk 6X (STM32H743) |
| GPS | UBLOX M9N (dual antenna) |
| Rangefinder | Benewake TF02 Pro (LiDAR 40m) |

---

## 🚀 Быстрый старт

### Docker развёртывание (VPS Ubuntu 2 CPU 8GB RAM):
```bash
git clone https://github.com/Redrock453/grim-fpv-ai.git
cd grim-fpv-ai
cp .env.example .env
docker-compose up -d
```

### Порты:
| Port | Protocol | Назначение |
|------|----------|------------|
| 5760 | TCP | MAVLink TCP (SITL ↔ FastAPI) |
| 14550 | UDP | MAVLink UDP (QGroundControl) |
| 8000 | TCP | FastAPI + Веб-дашборд |

### Сервисы:
- **Веб-дашборд:** `http://VPS_IP:8000/dashboard/`
- **API Docs:** `http://VPS_IP:8000/docs`
- **QGroundControl:** `udp://VPS_IP:14550`

---

## 🏗️ Архитектура

### Структура проекта:
```
grim-fpv-ai/
├── api/                 # FastAPI сервер + модели
├── calculators/         # 7 математических калькуляторов
├── ai_engines/         # Multi-AI интеграция
├── ai/                 # Computer Vision pipeline
├── core/               # Autonomous flight core
├── slam/               # SLAM интеграция
├── ardupilot/          # ArduPilot SITL
├── flight_simulator.py # Эмулятор боевых миссий
├── drone_specs/        # Конфигурации дронов
├── prompts/            # System prompts для AI
└── utils/              # Утилиты, config, DB
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

### Калькуляторы (POST):
| Endpoint | Описание |
|----------|----------|
| `/calculate/flight-time` | Расчёт времени полёта |
| `/calculate/hover-current` | Ток в висении |
| `/calculate/rf-link` | RF link budget |
| `/calculate/rf-thermal` | Тепловой расчёт TX |
| `/calculate/thermal` | Полный тепловой анализ |
| `/calculate/range` | Дальность связи |
| `/calculate/pid` | Рекомендации PID |
| `/calculate/multi-ai` | Multi-AI анализ |

### Миссии:
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/mission/start` | POST | Запуск миссии (требует SITL) |
| `/mission/status` | GET | Статус текущей миссии |
| `/mission/stop` | POST | Остановка миссии (RTL) |
| `/missions/portfolio` | GET | Портфолио завершённых миссий |
| `/missions/{type}/simulate` | GET | Симуляция миссии по типу |
| `/simulate/mission` | GET | Симуляция миссии (параметр ?type=) |

### Телеметрия и мониторинг:
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/telemetry/latest` | GET | Последняя телеметрия |
| `/health` | GET | Статус системы |
| `/ws/telemetry` | WebSocket | Стрим телеметрии в реальном времени |

---

## 🧮 Калькуляторы

### 1. Время полёта (`/calculate/flight-time`)
```bash
curl -X POST "http://localhost:8000/calculate/flight-time" \
  -H "Content-Type: application/json" \
  -d '{"battery_wh": 18.87, "avg_power_watts": 150}'
```
**Ответ:** `{"flight_time_min":6.42,"params":{"wh":18.87,"watts":150.0,"sag":0.85}}`

### 2. RF link budget (`/calculate/rf-link`)
```bash
curl -X POST "http://localhost:8000/calculate/rf-link" \
  -H "Content-Type: application/json" \
  -d '{"freq_mhz": 5800, "distance_km": 2.5, "tx_power_watts": 0.6}'
```
**Ответ:** `{"tx_power_dbm":27.78,"path_loss_db":115.67,"rssi_dbm":-91.89,"status":"Weak"}`

### 3. Тепловой анализ TX (`/calculate/rf-thermal`)
```bash
curl -X POST "http://localhost:8000/calculate/rf-thermal" \
  -H "Content-Type: application/json" \
  -d '{"p_out_watts": 0.6, "efficiency": 0.35}'
```
**Ответ:** `{"p_out_watts":0.6,"p_total_in_watts":1.71,"p_heat_watts":1.11,"efficiency_pct":35.0,"status":"Manageable"}`

### 4. PID рекомендации (`/calculate/pid`)
```bash
curl -X POST "http://localhost:8000/calculate/pid" \
  -H "Content-Type: application/json" \
  -d '{"kv": 2000, "prop_size": "5045", "weight_g": 865}'
```
**Ответ:** `{"roll":{"P":45,"I":35,"D":22},"pitch":{"P":50,"I":35,"D":24},"yaw":{"P":30,"I":25,"D":0}}`

### 5. Ток в висении (`/calculate/hover-current`)
```bash
curl -X POST "http://localhost:8000/calculate/hover-current" \
  -H "Content-Type: application/json" \
  -d '{"kv": 2000, "battery_cells": 6, "prop_size": "5045", "weight_g": 865, "thrust_kg": 4.2, "max_current_a": 40}'
```
**Ответ:** `{"hover_current_a":8.24,"params":{"weight":865.0,"thrust":4.2,"max_current":40.0}}`

### 6. Дальность связи (`/calculate/range`)
```bash
curl -X POST "http://localhost:8000/calculate/range" \
  -H "Content-Type: application/json" \
  -d '{"freq_mhz": 5800, "tx_power_watts": 0.6, "rx_sensitivity_dbm": -95, "antenna_gain_tx_dbi": 4, "antenna_gain_rx_dbi": 3}'
```
**Ответ:** `{"range_km":44.39,"realistic_range_km":28.85,"tx_power_dbm":27.0,"max_path_loss_db":133.0}`

### 7. Тепловой анализ (`/calculate/thermal`)
```bash
curl -X POST "http://localhost:8000/calculate/thermal" \
  -H "Content-Type: application/json" \
  -d '{"motor_count": 4, "motor_current_a": 15, "esc_efficiency": 0.95, "ambient_temp_c": 25}'
```
**Ответ:** `{"esc_temp_c":67.0,"motor_temp_c":88.0,"warning":"OK","notes":"Расчёт при непрерывном полёте, без обдува"}`

### 8. Multi-AI анализ (`/calculate/multi-ai`)
```bash
curl -X POST "http://localhost:8000/calculate/multi-ai" \
  -H "Content-Type: application/json" \
  -d '{"calculation_type": "flight_analysis", "params": {"kv": 2000, "battery_cells": 6, "prop_size": "5045"}, "engines": ["gemini"]}'
```
*Требует настройки API ключей в .env файле*

---

## 🎯 Миссии

### Типы миссий:
1. **recon** (разведка) - позывной HAWK
2. **intercept** (перехват) - позывной VIPER
3. **loiter** (барражирование) - позывной OWL
4. **strike** (удар) - позывной FALCON
5. **delivery** (доставка) - позывной PELICAN

### Запуск симулированной миссии:
```bash
# Разведка
curl "http://localhost:8000/simulate/mission?type=recon"

# Перехват
curl "http://localhost:8000/simulate/mission?type=intercept"

# Барражирование
curl "http://localhost:8000/simulate/mission?type=loiter"

# Удар
curl "http://localhost:8000/simulate/mission?type=strike"

# Доставка
curl "http://localhost:8000/simulate/mission?type=delivery"
```

### Запуск "реальной" миссии (требует SITL):
```bash
curl -X POST "http://localhost:8000/mission/start" \
  -H "Content-Type: application/json" \
  -d '{"mission_type": "recon", "callsign": "HAWK", "duration_sec": 120}'
```

### Примеры завершённых миссий:
```
Миссия #1: HAWK — Разведка маршрута
Тип: recon | Длительность: 3 мин | Дистанция: 2.7 км
Макс. высота: 78 м | Макс. скорость: 19 м/с (68 км/ч)
Батарея: 100% → 72% | Расход: 28%

Миссия #2: VIPER — Перехват цели
Тип: intercept | Длительность: 2 мин | Дистанция: 3.1 км
Макс. высота: 48 м | Макс. скорость: 32 м/с (115 км/ч)
Батарея: 100% → 41% | Расход: 59%

Миссия #3: OWL — Барражирование
Тип: loiter | Длительность: 5 мин | Дистанция: 1.8 км
Макс. высота: 104 м | Макс. скорость: 12 м/с (43 км/ч)
Батарея: 100% → 55% | Расход: 45%
```

---

## 🛠️ Настройка SITL

### Проблема:
SITL Docker образ не запускается (падает с ошибкой 127).

### Решение:
1. **Проверить Docker образ:**
```bash
docker build -t grim-fpv-ai-sitl-fixed -f Dockerfile.sitl .
```

2. **Запустить вручную:**
```bash
docker run -d --name grim-fpv-sitl \
  -p 5760:5760 -p 14550:14550/udp \
  grim-fpv-ai-sitl-fixed
```

3. **Настроить подключение FastAPI:**
В `docker-compose.yml` установить:
```yaml
environment:
  - MAVLINK_URL=tcp:sitl:5760  # Без "//"
```

### Альтернатива: Использовать внешний SITL
1. Установить ArduPilot на хост-машине
2. Запустить: `sim_vehicle.py -v ArduCopter -f quad --out tcp:0.0.0.0:5760`
3. Настроить FastAPI на подключение к `localhost:5760`

---

## 🖥️ Веб-дашборд

### Доступ:
- `http://[IP_машины]:8000/dashboard/`
- Через Tailscale: `http://100.123.130.38:8000/dashboard/`
- Публично: `http://68.183.101.60:8000/dashboard/` (если порт открыт)

### Функции:
1. **Карта** с позицией дрона (Leaflet.js)
2. **Панель телеметрии**: батарея, скорость, высота, RSSI, режим, throttle
3. **Графики в реальном времени** (Chart.js)
4. **Кнопки управления миссиями**: Recon, Intercept, Loiter, Strike, Delivery, Stop
5. **WebSocket подключение** для live данных

### WebSocket:
```javascript
// Подключение к WebSocket
const ws = new WebSocket('ws://' + window.location.host + '/ws/telemetry');
```

---

## 📊 Операционная информация

### Текущий статус (из COMBAT_JOURNAL.md):
- ✅ **grim-fpv-ai** (GitHub PUBLIC) — FPV инженерия
- ✅ **secrets-vault** (GitHub PRIVATE) — все ключи
- ✅ **vika_ok v15.6** (DO Droplet) — Telegram агент
- ✅ **vika_fpv_bot** (Telegram) — FPV AI бот
- ⏳ **Telegram-bot миграция** — FastAPI → aiogram

### Организация:
```
ВЯЧЕСЛАВ (ты):
  ✅ CEO + Decision maker
  
CLAUDE (браузер):
  ✅ FPV инженер (расчёты, рекомендации)
  ✅ RF инженер (link budget, дальность)
  ✅ AI аналитик (multi-AI анализ)

VIKA (Telegram бот):
  ✅ FPV AI ассистент
  ✅ Уведомления о миссиях
  ✅ Статус системы
```

### AI Models:
- ✅ Gemini 3-flash-preview (основной)
- ✅ Groq llama-3.3-70b
- ✅ DO Agent

---

## 🔧 Troubleshooting

### Проблема 1: SITL не запускается
**Симптом:** Docker контейнер падает с кодом 127
**Решение:**
1. Проверить Dockerfile.sitl на ошибки
2. Попробовать собрать образ заново
3. Использовать эмулятор вместо SITL

### Проблема 2: "SITL недоступный" на дашборде
**Симптом:** На дашборде отображается "SITL недоступный"
**Причина:** FastAPI не может подключиться к SITL
**Решение:**
1. Проверить формат MAVLINK_URL (должен быть `tcp:sitl:5760` без `//`)
2. Убедиться, что контейнеры в одной сети Docker
3. Проверить разрешение имени `sitl` из контейнера API

### Проблема 3: Миссии не запускаются
**Симптом:** `/mission/start` возвращает ошибку или миссия не "взлетает"
**Причина:** Проблема с подключением к SITL или эмулятором
**Решение:**
1. Использовать `/simulate/mission` вместо `/mission/start`
2. Проверить логи FastAPI на ошибки подключения
3. Убедиться, что SITL запущен и принимает подключения

### Проблема 4: Multi-AI не работает
**Симптом:** `/calculate/multi-ai` возвращает ошибки API
**Причина:** Не настроены API ключи
**Решение:**
1. Добавить API ключи в `.env` файл:
```
GROK_API_KEY=your_grok_key_here
GEMINI_API_KEY=your_gemini_key_here
GLM_API_KEY=your_glm_key_here
CLAUDE_API_KEY=your_claude_key_here
GROQ_API_KEY=your_groq_key_here
```
2. Перезапустить контейнер API

### Проблема 5: Веб-дашборд не обновляется
**Симптом:** Данные на дашборде не меняются
**Причина:** Проблема с WebSocket подключением
**Решение:**
1. Проверить консоль браузера на ошибки WebSocket
2. Убедиться, что WebSocket endpoint доступен
3. Проверить, генерирует ли эмулятор данные

---

## 📝 Полезные команды

### Мониторинг:
```bash
# Проверка здоровья API
curl http://localhost:8000/health

# Последняя телеметрия
curl http://localhost:8000/telemetry/latest

# Статус миссии
curl http://localhost:8000/mission/status

# Портфолио миссий
curl http://localhost:8000/missions/portfolio
```

### Docker управление:
```bash
# Запуск всех сервисов
cd /root/grim-fpv-ai && docker-compose up -d

# Остановка всех сервисов
cd /root/grim-fpv-ai && docker-compose down

# Просмотр логов API
docker logs grim-fpv-api --tail 50

# Просмотр логов SITL
docker logs grim-fpv-sitl --tail 50

# Перезапуск API
docker restart grim-fpv-api
```

### Тестирование:
```bash
# Тест всех калькуляторов
./test_all_missions.py

# Тест одной миссии
curl "http://localhost:8000/simulate/mission?type=recon"

# Тест WebSocket (использовать wscat или браузер)
wscat -c ws://localhost:8000/ws/telemetry
```

---

## 🔗 Полезные ссылки

### Внутренние:
- **Swagger UI:** `http://localhost:8000/docs`
- **Веб-дашборд:** `http://localhost:8000/dashboard/`
- **Git репозиторий:** `https://github.com/Redrock453/grim-fpv-ai`

### Внешние:
- **ArduPilot документация:** http://ardupilot.org/
- **MAVLink протокол:** https://mavlink.io/
- **QGroundControl:** https://qgroundcontrol.com/

### Документация в репозитории:
1. `CLAUDE.md` - полное техническое описание
2. `COMBAT_JOURNAL.md` - операционный статус
3. `MISSION_LOG.md` - инженерный лог
4. `ardupilot/PRESET_METHODOLOGY.md` - настройка ArduPilot
5. `prompts/` - системные промпты для AI

---

## 🎯 Рекомендации по использованию

### Для инженерных расчётов:
1. Используйте калькуляторы для точных расчётов
2. Проверяйте RF link budget перед полётами на дальность
3. Мониторьте тепловые характеристики компонентов

### Для тестирования миссий:
1. Используйте `/simulate/mission` для быстрого тестирования
2. Анализируйте телеметрию симулированных миссий
3. Тестируйте разные типы миссий для понимания характеристик

### Для разработки:
1. Изучите архитектуру в `CLAUDE.md`
2. Используйте Swagger UI для тестирования API
3. Проверяйте логи при проблемах с подключением

### Для production использования:
1. Почините SITL для реального симулирования полётов
2. Настройте API ключи для Multi-AI анализа
3. Настройте мониторинг и логирование

---

## 📞 Поддержка

### Контакты:
- **Lead Engineer:** Victoria (AI)
- **CEO:** Вячеслав
- **Telegram бот:** @vika_fpv_bot

### Каналы связи:
1. **GitHub Issues:** https://github.com/Redrock453/grim-fpv-ai/issues
2. **Telegram:** @vika_fpv_bot
3. **Внутренняя документация:** COMBAT_JOURNAL.md

---

## 🔄 Обновления

### Последние изменения (из MISSION_LOG.md):
- **2026-04-03:** Major Platform Upgrade
  - 7 калькуляторов
  - 5 AI engines
  - Core архитектура
  - Flight Simulator с 5 типами миссий

### Планы на будущее:
1. Починить SITL Docker образ
2. Добавить больше типов миссий
3. Улучшить веб-дашборд
4. Добавить интеграцию с реальным дроном

---

*Документация создана на основе анализа репозитория GRIM-FPV-AI*
*Обновлено: 2026-04-14*
*Автор: Victoria (AI Assistant)*