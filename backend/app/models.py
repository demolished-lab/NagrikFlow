"""DB models: users, consent-gated vault, roadmap snapshots, progress, reviews.

Every personal row carries user_id (tenant). No query may omit it.
Docs are referenced by DigiLocker URI, never stored as blobs unless
explicitly consented (DPDP Act: purpose limitation + storage limitation).
"""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = ""
    password_hash: str = ""
    city: str = ""
    state: str = ""
    is_admin: bool = False
    telegram_chat: str = ""
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class Consent(SQLModel, table=True):
    """DPDP consent receipt: what purpose, what data, withdrawable."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    purpose: str  # e.g. "digilocker.documents.read"
    scopes: str = ""  # comma-separated granted scopes
    granted_at: datetime = Field(default_factory=utcnow)
    withdrawn_at: Optional[datetime] = None


class VaultItem(SQLModel, table=True):
    """Per-user verified fact: doc type + issuer + reference, NOT the blob."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    kind: str  # aadhaar | pan | udyam | gstin | dl | ...
    label: str = ""
    issuer: str = ""  # e.g. "in.gov.pan"
    reference: str = ""  # DigiLocker URI or registration number
    verified_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = None  # e.g. DL validity, filing due
    meta: str = "{}"  # small JSON: status, dates, venue


class TaskMap(SQLModel, table=True):
    """Curated/verified civic procedure snapshot (admin-stamped)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)  # "udyam-register"
    title: str = ""
    city: str = ""
    graph_json: str = "{}"  # node_link_data: steps + edges
    verified_at: Optional[datetime] = None
    source_urls: str = "[]"
    content_hash: str = ""  # sha256 of fetched source texts at build/verify
    checked_at: Optional[datetime] = None


class Progress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    map_slug: str = Field(index=True)
    step_id: str = ""
    done_at: datetime = Field(default_factory=utcnow)


class OtpCode(SQLModel, table=True):
    """Hashed OTP for passwordless login. Single-use, 10-min expiry."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    code_hash: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    used_at: Optional[datetime] = None


class LinkCode(SQLModel, table=True):
    """One-time code binding a Telegram chat to a user. Expires in 15 min."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    code: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    used_at: Optional[datetime] = None


class Job(SQLModel, table=True):
    """Background job: build-map / recheck run async, polled by frontend."""
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = ""  # build | recheck
    status: str = "queued"  # queued | running | done | failed
    payload: str = "{}"  # input params
    result: str = "{}"  # output summary
    created_by: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
