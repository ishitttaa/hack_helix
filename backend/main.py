"""
PromptGuard — FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db.database import init_db
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Status: PromptGuard Firewall is live.")
    yield


app = FastAPI(
    title="PromptGuard API",
    description="Adversarial Prompt Firewall for LLM-Integrated Products",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "PromptGuard",
        "tagline": "Adversarial Prompt Firewall for LLM-Integrated Products",
        "docs": "/docs",
        "status": "🟢 Online",
    }
