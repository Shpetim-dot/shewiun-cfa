"""Public Agent Launch Review conversion endpoints and protected review admin APIs."""
from __future__ import annotations

import os
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .agent_launch_runtime import (
    capture_lead,
    create_test_request,
    get_review_by_token,
    list_test_requests,
    purge_expired_review_data,
    record_analytics,
    review_analytics_summary,
    _preview_result,
)

router = APIRouter()


def _main():
    # Resolve the app module lazily to avoid a circular import during route registration.
    from . import main
    return main


def _db_path():
    main = _main()
    return None if main.database_url() else main.DB_PATH


def privacy_notice_url() -> str | None:
    value = os.getenv("CFA_PRIVACY_NOTICE_URL", "").strip()
    return value if value.startswith("https://") and len(value) <= 2048 else None


def email_capture_enabled() -> bool:
    main = _main()
    if not main.IS_VERCEL:
        return True
    return main.database_backend() == "postgresql" and privacy_notice_url() is not None


def lead_gate_enabled() -> bool:
    main = _main()
    return main.IS_VERCEL and email_capture_enabled()


def _valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email.strip()))


class ReviewEventIn(BaseModel):
    event_name: str = Field(min_length=1, max_length=40)
    share_token: str | None = Field(default=None, min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)
    analytics_consent: bool = False


class ReviewLeadUnlockIn(BaseModel):
    share_token: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    email: str = Field(min_length=3, max_length=254)
    consent: bool


class AuthorizationTestRequestIn(BaseModel):
    share_token: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    company: str = Field(default="", max_length=200)
    role: str = Field(min_length=1, max_length=160)
    use_case: str = Field(min_length=10, max_length=3000)
    consent: bool


@router.post("/api/review/agent-launch/event")
def record_agent_launch_event(item: ReviewEventIn) -> dict[str, Any]:
    allowed = {"page_view", "step_completed", "result_viewed", "pdf_downloaded", "cta_clicked"}
    if item.event_name not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported analytics event.")
    if not item.analytics_consent:
        return {"status": "ignored", "reason": "analytics consent not granted"}
    if len(str(item.metadata).encode("utf-8")) > 2048:
        raise HTTPException(status_code=413, detail="Analytics metadata exceeds 2 KB.")
    if _main().IS_VERCEL and (_main().database_backend() != "postgresql" or privacy_notice_url() is None):
        raise HTTPException(status_code=503, detail="Analytics storage requires persistent PostgreSQL.")
    submission_id = None
    if item.share_token:
        result = get_review_by_token(_db_path(), item.share_token)
        if result is None:
            raise HTTPException(status_code=404, detail="Review not found.")
        submission_id = result["id"]
    elif item.event_name not in {"page_view", "step_completed"}:
        raise HTTPException(status_code=400, detail="A valid review token is required for this event.")
    record_analytics(_db_path(), item.event_name, submission_id, item.metadata)
    return {"status": "recorded"}


@router.post("/api/review/agent-launch/unlock")
def unlock_agent_launch_memo(item: ReviewLeadUnlockIn) -> dict[str, Any]:
    if _main().IS_VERCEL and not email_capture_enabled():
        raise HTTPException(status_code=503, detail="Email unlock is disabled until PostgreSQL and a public HTTPS privacy notice are configured.")
    if not item.consent:
        raise HTTPException(status_code=400, detail="Explicit consent is required to store the email for memo access.")
    if not _valid_email(item.email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    result = get_review_by_token(_db_path(), item.share_token)
    if result is None:
        raise HTTPException(status_code=404, detail="Review not found or link revoked.")
    try:
        capture_lead(_db_path(), result["id"], item.email, item.consent)
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found or link revoked.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    unlocked = get_review_by_token(_db_path(), item.share_token)
    if unlocked:
        unlocked["privacy_notice_url"] = privacy_notice_url()
    return unlocked or result


@router.post("/api/review/agent-launch/authorization-test-request")
def request_authorization_test(item: AuthorizationTestRequestIn) -> dict[str, Any]:
    if _main().IS_VERCEL and not email_capture_enabled():
        raise HTTPException(status_code=503, detail="Test requests are disabled until PostgreSQL and a public HTTPS privacy notice are configured.")
    if not item.consent:
        raise HTTPException(status_code=400, detail="Consent to be contacted is required.")
    if not _valid_email(item.email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    review = get_review_by_token(_db_path(), item.share_token, require_lead=lead_gate_enabled())
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found or link revoked.")
    if review.get("lead_required"):
        raise HTTPException(status_code=403, detail="Unlock the memo before requesting an Authorization Test.")
    payload = {"name": item.name.strip(), "email": item.email.strip().lower(),
               "company": item.company.strip(), "role": item.role.strip(),
               "use_case": item.use_case.strip(), "consent": True}
    request_id = create_test_request(_db_path(), review["id"], payload)
    return {"status": "received", "request_id": request_id, "delivery": "stored_only",
            "note": "The request is stored. No email notification is configured; authorized workspace users can view it in the admin endpoint."}


@router.get("/api/review/agent-launch/admin/analytics")
def get_agent_launch_analytics(days: int = 30) -> dict[str, Any]:
    return review_analytics_summary(_db_path(), days)


@router.get("/api/review/agent-launch/admin/requests")
def get_agent_launch_test_requests(limit: int = 50) -> list[dict[str, Any]]:
    return list_test_requests(_db_path(), limit)


@router.get("/api/maintenance/retention")
def run_retention_job(request: Request) -> dict[str, Any]:
    main = _main()
    secret = os.getenv("CRON_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured.")
    if request.headers.get("authorization", "") != "Bearer " + secret:
        raise HTTPException(status_code=403, detail="Forbidden.")
    if main.IS_VERCEL and main.database_backend() != "postgresql":
        raise HTTPException(status_code=503, detail="Retention job requires persistent PostgreSQL.")
    return {"status": "completed", "retention_days": 90,
            "deleted": purge_expired_review_data(_db_path(), 90)}
