"""
app/main.py — Expenses Tracker health check server (minimal)
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

app = FastAPI(title="Expenses Tracker", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}
