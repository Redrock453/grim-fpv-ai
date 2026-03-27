# GRIM-FPV-AI 🛸

FPV AI Engineering Agent для проекта **ГРІМ-5** (5-дюймовый боевой дрон).

## Спецификация ГРІМ-5
- **Рама:** iFlight XL5 Pro, 5"
- **Моторы:** T-Motor U8 Pro 2000KV
- **Вес:** ~865г
- **Батарея:** 6S 850mAh 75C (18.87Wh)
- **Тяга:** ~4.2кг (TWR 4.86)

## Установка в Termux

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/redrock453/grim-fpv-ai.git
   cd grim-fpv-ai
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Настройте окружение:
   ```bash
   cp .env.example .env
   # Отредактируйте .env и добавьте свои API ключи
   ```

## Запуск API

```bash
python -m uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8000
```

## Использование

### Расчёт времени полёта
```bash
curl -X POST "http://localhost:8000/calculate/flight-time" \
     -H "Content-Type: application/json" \
     -d '{"battery_wh": 18.87, "avg_power_watts": 150}'
```

## Структура проекта
- `calculators/`: Математические модули для расчётов.
- `ai_engines/`: Интеграция с Grok, Gemini и Claude.
- `api/`: FastAPI сервер.
- `drone_specs/`: Конфигурации дронов в JSON.
