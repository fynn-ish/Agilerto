"""Run one refresh by hand (handy for demos and testing):   python refresh.py"""
import logging

from app.db import init_db
from app.ingest import run_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("uvicorn.error.ingest").setLevel(logging.INFO)

if __name__ == "__main__":
    init_db()
    result = run_all()
    print("Result:", result)
