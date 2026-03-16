from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    employee = "employee"
    manager  = "manager"
    admin    = "admin"


class Priority(str, enum.Enum):
    critical = "Critical"
    high     = "High"
    medium   = "Medium"
    low      = "Low"


class ReqStatus(str, enum.Enum):
    pending   = "Pending"
    approved  = "Approved"
    rejected  = "Rejected"
    cancelled = "Cancelled"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    full_name       = Column(String(120), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    employee_id     = Column(String(50), unique=True, nullable=True)
    department      = Column(String(100), nullable=True)
    role            = Column(Enum(UserRole), default=UserRole.employee, nullable=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    last_login      = Column(DateTime, nullable=True)

    submitted  = relationship("ApprovalRequest", foreign_keys="ApprovalRequest.requester_id", back_populates="requester")
    assigned   = relationship("ApprovalRequest", foreign_keys="ApprovalRequest.approver_id",  back_populates="approver")
    audit_logs = relationship("AuditLog",        back_populates="actor")
    comments   = relationship("Comment",         back_populates="author")
    notifs     = relationship("Notification",    back_populates="user")

    def initials(self):
        parts = self.full_name.split()
        return "".join(p[0] for p in parts[:2]).upper()


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id               = Column(Integer, primary_key=True, index=True)
    ref              = Column(String(20), unique=True, nullable=False)
    title            = Column(String(255), nullable=False)
    category         = Column(String(100), nullable=False)
    description      = Column(Text, nullable=False)
    priority         = Column(Enum(Priority),   default=Priority.medium,    nullable=False)
    status           = Column(Enum(ReqStatus),  default=ReqStatus.pending,  nullable=False)
    amount           = Column(Float,   nullable=True)
    currency         = Column(String(5), default="GBP")
    requester_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_date         = Column(DateTime, nullable=True)
    submitted_at     = Column(DateTime, default=datetime.utcnow)
    actioned_at      = Column(DateTime, nullable=True)
    reject_reason    = Column(Text, nullable=True)

    requester    = relationship("User",        foreign_keys=[requester_id], back_populates="submitted")
    approver     = relationship("User",        foreign_keys=[approver_id],  back_populates="assigned")
    attachments  = relationship("Attachment",  back_populates="request",    cascade="all, delete-orphan")
    audit_logs   = relationship("AuditLog",    back_populates="request",    cascade="all, delete-orphan")
    comments     = relationship("Comment",     back_populates="request",    cascade="all, delete-orphan")
    notifs       = relationship("Notification",back_populates="request",    cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"

    id          = Column(Integer, primary_key=True, index=True)
    request_id  = Column(Integer, ForeignKey("approval_requests.id"), nullable=False)
    filename    = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    file_path   = Column(String(500), nullable=False)
    file_size   = Column(Integer,     nullable=False)
    mime_type   = Column(String(100), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("ApprovalRequest", back_populates="attachments")

    def size_human(self):
        s = self.file_size
        for u in ["B", "KB", "MB"]:
            if s < 1024:
                return f"{s:.1f} {u}"
            s /= 1024
        return f"{s:.1f} GB"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=True)
    actor_id   = Column(Integer, ForeignKey("users.id"),             nullable=False)
    action     = Column(String(50), nullable=False)
    detail     = Column(Text, nullable=True)
    timestamp  = Column(DateTime, default=datetime.utcnow)

    request = relationship("ApprovalRequest", back_populates="audit_logs")
    actor   = relationship("User",            back_populates="audit_logs")


class Comment(Base):
    __tablename__ = "comments"

    id          = Column(Integer, primary_key=True, index=True)
    request_id  = Column(Integer, ForeignKey("approval_requests.id"), nullable=False)
    author_id   = Column(Integer, ForeignKey("users.id"),             nullable=False)
    body        = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    request = relationship("ApprovalRequest", back_populates="comments")
    author  = relationship("User",            back_populates="comments")


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"),             nullable=False)
    request_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=True)
    title      = Column(String(255), nullable=False)
    body       = Column(Text,        nullable=False)
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user    = relationship("User",            back_populates="notifs")
    request = relationship("ApprovalRequest", back_populates="notifs")
