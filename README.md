# Grim FPV AI — Мультироторный AI-пилот

Архитектурное решение для FPV дрона с AI-навигацией и объектным распознаванием.

## Структура

```
grim-fpv-ai/
├── core/
│   ├── data_contracts.py   # Все типы данных (Pose3D, DetectedObject, WorldModel)
│   ├── state_machine.py    # HFSM с приоритетом SAFETY > NAVIGATION
│   └── event_bus.py        # Asyncio Pub/Sub для модулей
└── README.md
```

## Архитектурные решения

### 1. data_contracts.py — Единый источник правды

Все типы данных вынесены в один файл:
- `Pose3D`, `Velocity3D` — SLAM координаты
- `DetectedObject` — распознанные объекты
- `WorldModel` — объединённое состояние системы
- `FlightCommand` — команды в MAVLink

Модули не имеют своих типов — импортируют отсюда.

### 2. state_machine.py — HFSM с приоритетом SAFETY

**Hierarchy**:
```
SAFETY LAYER (Always evaluates first)
  ├─ Emergency Land (низкий заряд/связь)
  ├─ Manual Override (оператор)
  └─ Avoid (препятствие) — Interrupt Navigation
      └─ Возвращает в NAVIGATION после устранения
```

**Navigation States**:
- IDLE → SEARCH → TRACK (при появлении цели)
- SEARCH_LAST_KNOWN — не сбрасываться в IDLE, таймаут 10с
- PATROL — waypoint следование
- RETURN — домой

### 3. event_bus.py — Loose Coupling

Модули подписываются на события через `bus.subscribe()`:
```python
bus.subscribe("flight_command", my_handler)
```

API совместим с Redis/NATS для горизонтального масштабирования.

## Таблица решений

| Ситуация | State | Действие |
|----------|-------|----------|
| Цель найдена | IDLE → SEARCH | Паттерн поиска (spiral/lawnmower) |
| Цель появилась в TRACK | SEARCH_LAST_KNOWN → TRACK | Возвращаемся к IDLE не вызываем |
| Препятствие обнаружено | AVOID (Interrupt) | Прерываем Navigation |
| Препятствие исчезло | NAVIGATION (return_to) | Продолжаем в том же стейте |
| Заряд < 20% | SAFETY → RETURN | Эвакуация |
| Заряд < 10% | SAFETY → EMERGENCY_LAND | Жесткая посадка |

## Следующие шаги

- [ ] `core/world_model.py` — интеграция SLAM
- [ ] `slam/sensor_sync.py` — синхронизация сенсоров
- [ ] `core/mavlink_client.py` — MAVLink transport
- [ ] `perception/byte_track.py` — отслеживание объектов

## Статус

✅ **v1.0** — Архитектура определена, типы данных, HFSM, Event Bus
