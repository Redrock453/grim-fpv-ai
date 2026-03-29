# Grim FPV AI — Мультироторный AI-пилот

Архитектурное решение для FPV дрона с AI-навигацией и объектным распознаванием.

## Структура

```
grim-fpv-ai/
├── core/
│   ├── data_contracts.py   # Все типы данных (Pose3D, DetectedObject, WorldModel)
│   ├── state_machine.py    # HFSM с приоритетом SAFETY > NAVIGATION
│   ├── event_bus.py        # Asyncio Pub/Sub для модулей
│   └── world_model.py      # Объединяет SLAM, Perception, команды полёта
├── slam/
│   ├── sensor_sync.py      # Синхронизация IMU и Camera
│   └── openvins_bridge.py  # Мост к OpenVINS
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

### 4. sensor_sync.py — Критичный для OpenVINS

**Проблема**:
- Camera (USB): кадр с задержкой 50-100ms
- IMU: строчит на 200Hz

**Решение**:
- Буферизация IMU по времени
- Линейная интерполяция на таймстемп кадра
- Hardware trigger mode (если железо поддерживает)
- Camera latency compensation (33ms USB overhead)
- Quality metrics и diagnostics

### 5. openvins_bridge.py — Интеграция с OpenVINS

**Flow**:
```
SensorSync → OpenVINSBridge → OpenVINS API
                               ↓
                          Position/Orientation → WorldModel
```

**Функции**:
- Timestamp validation (gap < 100ms)
- Формирование VIO-кадров для OpenVINS
- Placeholder для реального API вызова (TODO)
- Buffering и error handling

### 6. world_model.py — Вершина пирамиды

**Объединяет все данные**:
- SLAM позицию из `openvins_bridge`
- Perception из `DetectedObject`
- `FlightCommand` из HFSM
- Стало единый `WorldModel` для всей системы

**Критично**: это единственное место где все данные изолированы от друг друга.
Остальные модули знают только про `data_contracts`.

## Таблица решений

| Ситуация | State | Действие |
|----------|-------|----------|
| Цель найдена | IDLE → SEARCH | Паттерн поиска (spiral/lawnmower) |
| Цель появилась в TRACK | SEARCH_LAST_KNOWN → TRACK | Не вызываем IDLE |
| Препятствие обнаружено | AVOID (Interrupt) | Прерываем Navigation |
| Препятствие исчезло | NAVIGATION (return_to) | Продолжаем в том же стейте |
| Заряд < 20% | SAFETY → RETURN | Эвакуация |
| Заряд < 10% | SAFETY → EMERGENCY_LAND | Жесткая посадка |

## Следующие шаги

- [x] `core/data_contracts.py`
- [x] `core/state_machine.py`
- [x] `core/event_bus.py`
- [x] `slam/sensor_sync.py`
- [x] `slam/openvins_bridge.py`
- [x] `core/world_model.py`
- [ ] `perception/` — объектное распознавание (ByteTrack + YOLO)
- [ ] `core/mavlink_client.py` — MAVLink transport

## Статус

✅ **v1.3** — Добавлен world_model.py как вершина пирамиды данных
