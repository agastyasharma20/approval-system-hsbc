from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import ApprovalRequest, AuditLog, Notification, User, UserRole, ReqStatus, Priority
from app.templates_config import templates
from app.services.auth import get_current_user, require_admin, hash_password

router    = APIRouter(tags=["dashboard"])

_PRIO_ORDER = {Priority.critical: 0, Priority.high: 1, Priority.medium: 2, Priority.low: 3}


@router.get("/")
async def root():
    return RedirectResponse("/dashboard", 302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request:      Request,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    q = db.query(ApprovalRequest)
    if current_user.role == UserRole.employee:
        q = q.filter(ApprovalRequest.requester_id == current_user.id)

    total    = q.count()
    pending  = q.filter(ApprovalRequest.status == ReqStatus.pending).count()
    approved = q.filter(ApprovalRequest.status == ReqStatus.approved).count()
    rejected = q.filter(ApprovalRequest.status == ReqStatus.rejected).count()
    critical = q.filter(ApprovalRequest.status == ReqStatus.pending,
                        ApprovalRequest.priority == Priority.critical).count()

    recent = (db.query(ApprovalRequest)
              .options(selectinload(ApprovalRequest.requester),
                       selectinload(ApprovalRequest.approver))
              .filter(ApprovalRequest.requester_id == current_user.id
                      if current_user.role == UserRole.employee
                      else True)
              .order_by(ApprovalRequest.submitted_at.desc())
              .limit(5).all())

    pending_for_me = []
    if current_user.role in (UserRole.manager, UserRole.admin):
        rows = (db.query(ApprovalRequest)
                .options(selectinload(ApprovalRequest.requester))
                .filter(ApprovalRequest.approver_id == current_user.id,
                        ApprovalRequest.status      == ReqStatus.pending)
                .all())
        pending_for_me = sorted(rows, key=lambda r: _PRIO_ORDER.get(r.priority, 99))

    unread = (db.query(Notification)
              .filter(Notification.user_id == current_user.id,
                      Notification.is_read == False).count())  # noqa

    return templates.TemplateResponse("dashboard/index.html", {
        "request":        request,
        "current_user":   current_user,
        "stats":          {"total": total, "pending": pending,
                           "approved": approved, "rejected": rejected, "critical": critical},
        "recent":         recent,
        "pending_for_me": pending_for_me,
        "unread_notifs":  unread,
    })


@router.get("/notifications", response_class=HTMLResponse)
async def notifications(
    request:      Request,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    notifs = (db.query(Notification)
              .filter(Notification.user_id == current_user.id)
              .order_by(Notification.created_at.desc()).all())
    for n in notifs:
        n.is_read = True
    db.commit()
    return templates.TemplateResponse("dashboard/notifications.html", {
        "request": request, "current_user": current_user,
        "notifications": notifs, "unread_notifs": 0,
    })


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request:      Request,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_admin),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    audit = (db.query(AuditLog)
             .options(selectinload(AuditLog.actor),
                      selectinload(AuditLog.request))
             .order_by(AuditLog.timestamp.desc()).limit(50).all())
    unread = (db.query(Notification)
              .filter(Notification.user_id == current_user.id,
                      Notification.is_read == False).count())  # noqa
    return templates.TemplateResponse("admin/panel.html", {
        "request": request, "current_user": current_user,
        "users": users, "audit": audit,
        "roles": [r.value for r in UserRole],
        "unread_notifs": unread,
    })


@router.post("/admin/users/{uid}/role")
async def change_role(uid: int, role: str = Form(...),
                      db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin)):
    user = db.get(User, uid)
    if not user:
        raise HTTPException(404)
    try:
        user.role = UserRole(role)
    except ValueError:
        raise HTTPException(400, "Invalid role")
    db.commit()
    return RedirectResponse("/admin", 302)


@router.post("/admin/users/{uid}/toggle")
async def toggle_user(uid: int, db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin)):
    user = db.get(User, uid)
    if not user or user.id == current_user.id:
        raise HTTPException(400)
    user.is_active = not user.is_active
    db.commit()
    return RedirectResponse("/admin", 302)


# ── Real-time notification API (polled by frontend) ───────────

@router.get("/api/notifications/poll")
async def poll_notifications(
    request:      Request,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Polled every 15s by JS. Returns new unread notifications."""
    from fastapi.responses import JSONResponse
    from datetime import datetime

    since_str = request.query_params.get("since", "")
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa
    )
    if since_str:
        try:
            query = query.filter(Notification.created_at > datetime.fromisoformat(since_str))
        except ValueError:
            pass

    notifs = query.order_by(Notification.created_at.desc()).limit(5).all()
    return JSONResponse({
        "count": len(notifs),
        "items": [
            {
                "id":         n.id,
                "title":      n.title,
                "body":       n.body,
                "request_id": n.request_id,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifs
        ],
    })


@router.post("/api/notifications/{nid}/read")
async def mark_notification_read(
    nid:          int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    from fastapi.responses import JSONResponse
    n = db.get(Notification, nid)
    if n and n.user_id == current_user.id:
        n.is_read = True
        db.commit()
    return JSONResponse({"ok": True})
