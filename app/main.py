from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal
from app.models import Base, User, UserRole
from app.services.auth import hash_password
from app.routers import auth, requests, dashboard
from app.templates_config import templates   # registers all Jinja2 filters

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SmartApprove starting...")
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield
    logger.info("SmartApprove stopped.")


def _seed_admin():
    db: Session = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.ADMIN_EMAIL).first():
            db.add(User(
                full_name       = "System Administrator",
                email           = settings.ADMIN_EMAIL,
                hashed_password = hash_password(settings.ADMIN_PASSWORD),
                role            = UserRole.admin,
                employee_id     = "ADMIN-0001",
                department      = "IT Administration",
                is_active       = True,
            ))
            db.commit()
            logger.info(f"Admin created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


app = FastAPI(
    title     = settings.APP_NAME,
    version   = "3.1.0",
    lifespan  = lifespan,
    docs_url  = "/api/docs",
    redoc_url = "/api/redoc",
)

Path("app/static/uploads").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(dashboard.router)


@app.exception_handler(404)
async def e404(request: Request, exc):
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

@app.exception_handler(403)
async def e403(request: Request, exc):
    return templates.TemplateResponse("errors/403.html", {"request": request}, status_code=403)

@app.exception_handler(500)
async def e500(request: Request, exc):
    logger.exception("500 error")
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)
