# Run
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python scripts\seed.py
# Owner verifies real data.
uvicorn app.main:app --reload
ruff check .
pytest -q
python scripts\check_contract.py
```

# Environment variables
`DATABASE_URL` (default `sqlite:///./food_guide.db`), `SECRET_KEY`, `CORS_ORIGINS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `AI_SEARCH_URL`, `AI_SEARCH_KEY`, `AI_ITINERARY_URL`, `AI_ITINERARY_KEY`, `AI_TIMEOUT_MS` (default `15000`), `AI_MIN_CONF` (default `0.4`), `MOCK_AI` (default `true`).
