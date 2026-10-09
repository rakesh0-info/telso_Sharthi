import asyncio
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database_config import engine, SessionLocal, Base
import admin_seed

from controller.publicController import router as public_router
from controller.SuperAdminController import router as super_admin_router
from controller.contentAdminController import router as content_admin_router

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    db = SessionLocal()
    try:
        admin_seed.seed_admin_user(db)
    finally:
        db.close()
        
    yield  


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(super_admin_router)
app.include_router(content_admin_router)