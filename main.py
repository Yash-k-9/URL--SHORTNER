import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from databse_models import base
from api.auth import router as auth_router
from api.routes import router
from core.config import ALLOWED_ORIGINS

logging.basicConfig(level=logging.INFO)

# Initialize database tables
base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Browsers reject credentials with a wildcard origin, so only enable them
    # when explicit origins are configured
    allow_credentials="*" not in ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# auth first: routes.py ends with a catch-all /{short_code}
app.include_router(auth_router)
app.include_router(router)
