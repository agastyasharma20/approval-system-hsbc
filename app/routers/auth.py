from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.templates_config import templates
from app.services.auth import hash_password, verify_password, create_access_token, get_token_from_cookie, decode_token

router     = APIRouter(prefix="/auth", tags=["auth"])


def _logged_in_user(request: Request, db: Session) -> User | None:
    token = get_token_from_cookie(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
        return db.get(User, int(payload["sub"]))
    except Exception:
        return None


# ── Register ──────────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    if _logged_in_user(request, db):
        return RedirectResponse("/dashboard", 302)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register(
    request:     Request,
    full_name:   str = Form(...),
    email:       str = Form(...),
    password:    str = Form(...),
    department:  str = Form(""),
    employee_id: str = Form(""),
    db:          Session = Depends(get_db),
):
    email = email.lower().strip()

    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "Email already registered."
        }, status_code=400)

    if len(password) < 8:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "Password must be at least 8 characters."
        }, status_code=400)

    user = User(
        full_name       = full_name.strip(),
        email           = email,
        hashed_password = hash_password(password),
        department      = department.strip() or None,
        employee_id     = employee_id.strip() or None,
        role            = UserRole.employee,
    )
    db.add(user)
    db.commit()
    return RedirectResponse("/auth/login?registered=1", 302)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    if _logged_in_user(request, db):
        return RedirectResponse("/dashboard", 302)
    registered = request.query_params.get("registered")
    return templates.TemplateResponse("auth/login.html", {"request": request, "registered": registered})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request:  Request,
    email:    str = Form(...),
    password: str = Form(...),
    db:       Session = Depends(get_db),
):
    email = email.lower().strip()
    user  = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Invalid email or password."
        }, status_code=401)

    if not user.is_active:
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Account deactivated. Contact admin."
        }, status_code=403)

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id, user.role)
    resp  = RedirectResponse("/dashboard", 302)
    resp.set_cookie("access_token", token, httponly=True, max_age=3600, samesite="lax")
    return resp


# ── Logout ────────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    resp = RedirectResponse("/auth/login", 302)
    resp.delete_cookie("access_token")
    return resp
