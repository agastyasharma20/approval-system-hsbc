from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import (ApprovalRequest, Attachment, AuditLog, Comment,
                        Notification, User, UserRole, Priority, ReqStatus)
from app.templates_config import templates
from app.services.auth import get_current_user, require_manager
from app.services.files import save_upload

router    = APIRouter(prefix="/requests", tags=["requests"])

CATEGORIES = [
    "Budget / Finance", "IT / Software Access", "HR / Leave",
    "Procurement", "Travel & Expense", "Policy Exception",
    "Legal & Compliance", "Infrastructure", "Other",
]


def _next_ref(db: Session) -> str:
    n = db.query(func.count(ApprovalRequest.id)).scalar() + 1
    return f"REQ-{datetime.utcnow().year}-{n:04d}"


def _audit(db, actor, action, req_id=None, detail=None):
    db.add(AuditLog(request_id=req_id, actor_id=actor.id, action=action, detail=detail))


def _notify(db, user, req_id, title, body):
    db.add(Notification(user_id=user.id, request_id=req_id, title=title, body=body))


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def list_requests(
    request:       Request,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    search:        Optional[str] = None,
    page:          int = 1,
    db:            Session = Depends(get_db),
    current_user:  User    = Depends(get_current_user),
):
    PAGE = 15
    q = db.query(ApprovalRequest).options(
        selectinload(ApprovalRequest.requester),
        selectinload(ApprovalRequest.approver),
    )
    if current_user.role == UserRole.employee:
        q = q.filter(ApprovalRequest.requester_id == current_user.id)
    if status_filter:
        try:
            q = q.filter(ApprovalRequest.status == ReqStatus(status_filter))
        except ValueError:
            pass
    if priority_filter:
        try:
            q = q.filter(ApprovalRequest.priority == Priority(priority_filter))
        except ValueError:
            pass
    if search:
        t = f"%{search}%"
        q = q.filter(ApprovalRequest.title.ilike(t) | ApprovalRequest.ref.ilike(t))

    total   = q.count()
    items   = q.order_by(ApprovalRequest.submitted_at.desc()).offset((page-1)*PAGE).limit(PAGE).all()
    pages   = max(1, (total + PAGE - 1) // PAGE)

    unread = (db.query(Notification)
              .filter(Notification.user_id == current_user.id,
                      Notification.is_read == False).count())  # noqa

    return templates.TemplateResponse("requests/list.html", {
        "request": request, "current_user": current_user,
        "reqs": items, "total": total, "page": page, "pages": pages,
        "status_filter": status_filter, "priority_filter": priority_filter, "search": search,
        "statuses":   [s.value for s in ReqStatus],
        "priorities": [p.value for p in Priority],
        "unread_notifs": unread,
    })


# ── New ───────────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
async def new_page(
    request:      Request,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    managers = (db.query(User)
                .filter(User.role.in_([UserRole.manager, UserRole.admin]),
                        User.is_active == True,
                        User.id != current_user.id)
                .all())
    unread = (db.query(Notification)
              .filter(Notification.user_id == current_user.id,
                      Notification.is_read == False).count())  # noqa
    return templates.TemplateResponse("requests/new.html", {
        "request": request, "current_user": current_user,
        "managers":    managers,
        "priorities":  [p.value for p in Priority],
        "categories":  CATEGORIES,
        "unread_notifs": unread,
    })


@router.post("/new")
async def create_request(
    request:     Request,
    title:       str = Form(...),
    category:    str = Form(...),
    description: str = Form(...),
    priority:    str = Form(...),
    approver_id: int = Form(...),
    amount:      Optional[str] = Form(None),
    currency:    str = Form("GBP"),
    due_date:    Optional[str] = Form(None),
    files:       List[UploadFile] = File(default=[]),
    db:          Session = Depends(get_db),
    current_user: User   = Depends(get_current_user),
):
    approver = db.get(User, approver_id)
    if not approver:
        raise HTTPException(404, "Approver not found")

    amt = None
    if amount and amount.strip():
        try:
            amt = float(amount.replace(",", "").replace("£","").replace("$","").replace("₹","").strip())
        except ValueError:
            pass

    due = None
    if due_date:
        try:
            due = datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            pass

    req = ApprovalRequest(
        ref          = _next_ref(db),
        title        = title.strip(),
        category     = category,
        description  = description.strip(),
        priority     = Priority(priority),
        status       = ReqStatus.pending,
        requester_id = current_user.id,
        approver_id  = approver_id,
        amount       = amt,
        currency     = currency,
        due_date     = due,
    )
    db.add(req)
    db.flush()

    for f in files:
        if f.filename:
            meta = await save_upload(f, req.ref)
            db.add(Attachment(request_id=req.id, uploaded_by=current_user.id, **meta))
            _audit(db, current_user, "File Attached", req.id, meta["filename"])

    _audit(db, current_user, "Submitted", req.id, "Request submitted")
    _notify(db, approver, req.id,
            f"Action Required: {req.ref}",
            f"{current_user.full_name} submitted a {priority} priority request: {title}")
    db.commit()
    return RedirectResponse(f"/requests/{req.id}", 302)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{req_id}", response_class=HTMLResponse)
async def detail(
    req_id:       int,
    request:      Request,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    req = (db.query(ApprovalRequest)
           .options(selectinload(ApprovalRequest.requester),
                    selectinload(ApprovalRequest.approver),
                    selectinload(ApprovalRequest.attachments),
                    selectinload(ApprovalRequest.audit_logs).selectinload(AuditLog.actor),
                    selectinload(ApprovalRequest.comments).selectinload(Comment.author))
           .filter(ApprovalRequest.id == req_id).first())

    if not req:
        raise HTTPException(404)
    if current_user.role == UserRole.employee and req.requester_id != current_user.id:
        raise HTTPException(403)

    unread = (db.query(Notification)
              .filter(Notification.user_id == current_user.id,
                      Notification.is_read == False).count())  # noqa

    return templates.TemplateResponse("requests/detail.html", {
        "request": request, "current_user": current_user,
        "req": req, "unread_notifs": unread,
    })


# ── Decide ────────────────────────────────────────────────────────────────────

@router.post("/{req_id}/decide")
async def decide(
    req_id:       int,
    request:      Request,
    action:       str = Form(...),
    reason:       Optional[str] = Form(None),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager),
):
    req = db.get(ApprovalRequest, req_id)
    if not req:
        raise HTTPException(404)
    if req.status != ReqStatus.pending:
        raise HTTPException(400, "Already actioned")
    if req.approver_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(403, "Not assigned approver")

    if action == "approve":
        req.status      = ReqStatus.approved
        req.actioned_at = datetime.utcnow()
        _audit(db, current_user, "Approved", req.id)
        _notify(db, req.requester, req.id,
                f"{req.ref} Approved",
                f"Your request '{req.title}' was approved by {current_user.full_name}.")
    elif action == "reject":
        if not reason or not reason.strip():
            raise HTTPException(400, "Rejection reason required")
        req.status       = ReqStatus.rejected
        req.reject_reason = reason.strip()
        req.actioned_at  = datetime.utcnow()
        _audit(db, current_user, "Rejected", req.id, reason.strip())
        _notify(db, req.requester, req.id,
                f"{req.ref} Rejected",
                f"Your request '{req.title}' was rejected. Reason: {reason.strip()}")
    else:
        raise HTTPException(400, "Invalid action")

    db.commit()
    return RedirectResponse(f"/requests/{req_id}", 302)


# ── Cancel ────────────────────────────────────────────────────────────────────

@router.post("/{req_id}/cancel")
async def cancel(req_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    req = db.get(ApprovalRequest, req_id)
    if not req or req.requester_id != current_user.id:
        raise HTTPException(403)
    if req.status != ReqStatus.pending:
        raise HTTPException(400, "Only pending requests can be cancelled")
    req.status = ReqStatus.cancelled
    _audit(db, current_user, "Cancelled", req.id)
    db.commit()
    return RedirectResponse("/requests/", 302)


# ── Comment ───────────────────────────────────────────────────────────────────

@router.post("/{req_id}/comment")
async def add_comment(req_id: int, body: str = Form(...),
                      is_internal: bool = Form(False),
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    req = db.get(ApprovalRequest, req_id)
    if not req:
        raise HTTPException(404)
    db.add(Comment(request_id=req_id, author_id=current_user.id,
                   body=body.strip(), is_internal=is_internal))
    _audit(db, current_user, "Commented", req_id)
    db.commit()
    return RedirectResponse(f"/requests/{req_id}#comments", 302)


# ── Attach ────────────────────────────────────────────────────────────────────

@router.post("/{req_id}/attach")
async def attach(req_id: int, file: UploadFile = File(...),
                 db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    req = db.get(ApprovalRequest, req_id)
    if not req:
        raise HTTPException(404)
    meta = await save_upload(file, req.ref)
    db.add(Attachment(request_id=req_id, uploaded_by=current_user.id, **meta))
    _audit(db, current_user, "File Attached", req_id, meta["filename"])
    db.commit()
    return RedirectResponse(f"/requests/{req_id}", 302)


# ── Download ──────────────────────────────────────────────────────────────────

@router.get("/{req_id}/attachments/{att_id}")
async def download(req_id: int, att_id: int,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    att = db.get(Attachment, att_id)
    if not att or att.request_id != req_id:
        raise HTTPException(404)
    return FileResponse(att.file_path, filename=att.filename, media_type=att.mime_type)
