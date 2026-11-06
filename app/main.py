from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title=get_settings().app_name,
    description="Construction drawing, specification and BIM consistency checking.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {"name": get_settings().app_name, "docs": "/docs", "api": "/api/v1"}
