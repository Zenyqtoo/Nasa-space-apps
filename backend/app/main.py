"""Агро-Севооборот: API бэкенда."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .model.rules import get_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Агро-Севооборот API",
    description="Инструмент поддержки решений по севообороту для Северного Казахстана. "
    "Окончательное решение принимает фермер.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
async def _startup() -> None:
    get_rules()  # правила проверяются при запуске: ошибка в YAML не даст серверу стартовать
    settings = get_settings()
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
