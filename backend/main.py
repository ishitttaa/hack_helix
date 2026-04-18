"""
PromptGuard — FastAPI Application Entry Point
"""

import os
from dotenv import load_dotenv

# Load .env before anything else so API keys are available
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db.database import init_db
from api.routes import router
from llm_service import is_openai_available


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
