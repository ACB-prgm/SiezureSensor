from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import devices, events, export, health, imu, sessions, status


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
  init_db()
  yield


app = FastAPI(title="Dog Seizure Sensor V0", lifespan=lifespan)
app.add_middleware(
  CORSMiddleware,
  allow_origins=[
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://192.168.0.114:5173",
  ],
  allow_credentials=False,
  allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
  allow_headers=["Content-Type"],
)
app.include_router(health.router)
app.include_router(imu.router)
app.include_router(devices.router)
app.include_router(events.router)
app.include_router(export.router)
app.include_router(sessions.router)
app.include_router(status.router)
