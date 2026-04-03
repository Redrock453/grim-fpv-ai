# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## User
- **Имя:** Adam
- **Стиль:** русский разговорный, мат ок, кратко

## Project Overview

GRIM-5 FPV AI Engineering Agent — расчётный и AI-инструмент для 5" боевого FPV дрона ГРІМ-5 и 30W 433MHz RF-бустера. FastAPI бэкенд + математические калькуляторы + multi-AI движки (Grok, Gemini, Claude).

**ГРІМ-5 спеки:** iFlight XL5 Pro 5", T-Motor U8 Pro 2000KV, 865g AUW, 6S 850mAh 75C (18.87Wh), тяга 4.2кг (TWR 4.86), ExpressLRS 2.4GHz.

## Commands

```bash
# Install
pip install -r requirements.txt

# Run API server
python -m uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/
# Or single test
python -m pytest tests/test_calculations.py::TestCalculations::test_flight_time -v

# Run calculator standalone
python calculators/flight_time_calc.py
python calculators/hover_current.py
python calculators/rf_link_budget.py
python calculators/thermal_rf.py
```

## Architecture

```
calculators/       — Pure math modules, no deps on FastAPI
  flight_time_calc  — (battery_wh / power_w) * 60 * sag_factor
  hover_current     — (weight_kg / thrust_kg) * max_current
  rf_link_budget    — FSPL + link budget (dBm), watts↔dBm
  thermal_rf        — PA heat dissipation (P_out / efficiency - P_out)

api/
  fastapi_server    — 5 endpoints: /health, /calculate/{flight-time,hover-current,rf-link,rf-thermal}, /calculate/multi-ai
  models            — Pydantic request models (duplicated inline in server — needs refactor)

ai_engines/        — Stub async functions: get_{grok,gemini,claude}_response(prompt) → placeholder strings
drone_specs/       — grim5_config.json: single source of truth for drone parameters
utils/             — config.py (dotenv), db_sqlite.py (aiosqlite calculations log, not yet wired to API)
prompts/           — System prompts for AI personas: Victoria (RF engineer), FPV engineer, calculation templates
tests/             — unittest, only flight_time tests so far
```

**Data flow:** JSON request → FastAPI endpoint → calculator pure function → JSON response. DB logging exists but not integrated.

## Key Patterns

- Calculators are **pure functions** — no side effects, no DB, no API calls. Easy to test.
- All calculator modules have `if __name__ == "__main__"` blocks for quick CLI testing with GRIM-5 defaults.
- RF calculations use dBm/dBi/dB throughout. `watts_to_dbm()` for conversion at API boundary.
- Pydantic models in `api/models.py` are out of sync with inline models in `fastapi_server.py` — server is the source of truth.
- AI engines are stubs returning placeholder strings — not yet connected to real APIs.
- `.env` holds API keys (GROK_API_KEY, GEMINI_API_KEY, CLAUDE_API_KEY) — never commit.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Status check |
| POST | `/calculate/flight-time` | Flight time from battery Wh + power |
| POST | `/calculate/hover-current` | Hover current from weight + thrust |
| POST | `/calculate/rf-link` | RF link budget (FSPL, RSSI) |
| POST | `/calculate/rf-thermal` | RF PA thermal analysis |
| POST | `/calculate/multi-ai` | Placeholder for multi-AI queries |

## Branches

- `master` — stable, main development
- `dev` — development branch
- `fast_api` — FastAPI-specific changes
- `grok` — Grok AI engine integration

## Test Coverage Gaps

Tests only cover `flight_time_calc`. Missing tests for: `hover_current`, `rf_link_budget`, `thermal_rf`.
