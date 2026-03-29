# ГРІМ-5 FPV AI (FastAPI)

Теперь с поддержкой **Gemini + GLM + Groq** и всеми калькуляторами.

**Эндпоинты:**
- GET `/health`
- POST `/calculate/flight-time`
- POST `/calculate/thermal`
- POST `/calculate/range`
- POST `/calculate/pid`
- POST `/calculate/multi-ai` ← вызывает все 3 ИИ параллельно

Запуск:
```bash
pip install -r requirements.txt
cp .env.example .env
# Добавь в .env: GEMINI_API_KEY, GLM_API_KEY, GROQ_API_KEY
python -m uvicorn api.fastapi_server:app --host 0.0.0.0 --port 8000 --reload
```
