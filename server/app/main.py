from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import events, health, imu


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
  init_db()
  yield


app = FastAPI(title="Dog Seizure Sensor V0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(imu.router)
app.include_router(events.router)
