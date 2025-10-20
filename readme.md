
venv\Scripts\activate
python src/utils/db.py
python src/etl/ingest_to_sqlite.py
uvicorn src.api.app:app --reload --port 8000
http://127.0.0.1:8000/docs#/

python src/dashboard/app.py