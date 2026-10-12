from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from databse_models import base
from api.routes import router

# Initialize database tables
base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)