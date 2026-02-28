from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import game, voice
from db.models import init_db
from contextlib import asynccontextmanager
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Shiok Lah! API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game.router, prefix="/api/game", tags=["game"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])


@app.get("/")
def root():
    return {"status": "Shiok!"}
