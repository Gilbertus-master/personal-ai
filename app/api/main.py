from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "Gilbertus Albans")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "dev")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "env": APP_ENV,
    }


@app.get("/version")
def version() -> dict:
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
    }