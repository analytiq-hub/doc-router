"""License evaluation, in-process cache, and periodic checker."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from .claims import LicenseClaims
from .store import (
    bootstrap_license_if_needed,
    clear_license_checked_at,
    ensure_installation_id,
    get_license_document,
    put_license_key_raw,
    update_license_state,
)
from .verifier import LicenseVerifyError, verify_license_token

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_SECONDS = 300
CACHE_TTL_SECONDS = 30

_cache_lock = asyncio.Lock()
_cached_at: float = 0.0
_cached_status: Optional["LicenseStatus"] = None
_cached_claims: Optional[LicenseClaims] = None
_checker_task: Optional[asyncio.Task] = None
_checker_stop: Optional[asyncio.Event] = None


class LicenseStatus(BaseModel):
    valid: bool
    mode: str  # licensed | grace | expired | unlicensed | invalid
    license_id: Optional[str] = None
    customer_name: Optional[str] = None
    issued_at: Optional[datetime] = None
    not_before: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    grace_days: Optional[int] = None
    days_remaining: Optional[int] = None
    in_grace: bool = False
    features: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    installation_id: Optional[str] = None
    state: str = "ok"  # ok | disabled
    checked_at: Optional[datetime] = None
    code: Optional[str] = None
    message: Optional[str] = None
    masked_key: Optional[str] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _mask_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 12:
        return "DRLIC1.…"
    return f"{key[:7]}…{key[-6:]}"


def _status_unlicensed(installation_id: str) -> LicenseStatus:
    return LicenseStatus(
        valid=False,
        mode="unlicensed",
        features=[],
        limits={},
        installation_id=installation_id,
        state="ok",
        code="LICENSE_MISSING",
        message="No product license is installed.",
    )


def evaluate_claims(
    claims: LicenseClaims,
    *,
    installation_id: str,
    now: Optional[datetime] = None,
    masked_key: Optional[str] = None,
    checked_at: Optional[datetime] = None,
) -> LicenseStatus:
    current = _as_aware(now or _utcnow())
    expires = _as_aware(claims.expires_at)
    grace_days = claims.grace_days if claims.grace_days is not None else 7
    hard_end = expires + timedelta(days=grace_days)
    in_grace = expires <= current < hard_end
    expired_hard = current >= hard_end

    days_remaining = int((expires - current).total_seconds() // 86400)

    if expired_hard:
        return LicenseStatus(
            valid=False,
            mode="expired",
            license_id=claims.license_id,
            customer_name=claims.customer_name,
            issued_at=claims.issued_at,
            not_before=claims.not_before,
            expires_at=claims.expires_at,
            grace_days=grace_days,
            days_remaining=days_remaining,
            in_grace=False,
            features=claims.recognized_features(),
            limits=claims.limits_dict(),
            installation_id=installation_id,
            state="disabled",
            checked_at=checked_at or current,
            code="LICENSE_EXPIRED",
            message="Product license has expired.",
            masked_key=masked_key,
        )

    mode = "grace" if in_grace else "licensed"
    return LicenseStatus(
        valid=True,
        mode=mode,
        license_id=claims.license_id,
        customer_name=claims.customer_name,
        issued_at=claims.issued_at,
        not_before=claims.not_before,
        expires_at=claims.expires_at,
        grace_days=grace_days,
        days_remaining=days_remaining,
        in_grace=in_grace,
        features=claims.recognized_features(),
        limits=claims.limits_dict(),
        installation_id=installation_id,
        state="ok",
        checked_at=checked_at or current,
        code=None,
        message=None,
        masked_key=masked_key,
    )


def evaluate_license_key(
    license_key: str,
    *,
    installation_id: str,
    now: Optional[datetime] = None,
) -> LicenseStatus:
    try:
        claims = verify_license_token(
            license_key,
            installation_id=installation_id,
            now=now,
        )
    except LicenseVerifyError as e:
        return LicenseStatus(
            valid=False,
            mode="invalid",
            features=[],
            limits={},
            installation_id=installation_id,
            state="disabled",
            checked_at=now or _utcnow(),
            code=e.code,
            message=e.message,
            masked_key=_mask_key(license_key),
        )
    return evaluate_claims(
        claims,
        installation_id=installation_id,
        now=now,
        masked_key=_mask_key(license_key),
    )


def invalidate_license_cache() -> None:
    global _cached_at, _cached_status, _cached_claims
    _cached_at = 0.0
    _cached_status = None
    _cached_claims = None


async def _load_status(*, force: bool = False) -> tuple[LicenseStatus, Optional[LicenseClaims]]:
    global _cached_at, _cached_status, _cached_claims

    now_mono = time.monotonic()
    if (
        not force
        and _cached_status is not None
        and (now_mono - _cached_at) < CACHE_TTL_SECONDS
    ):
        # Re-evaluate temporal fields against wall clock using cached claims if present
        if _cached_claims is not None and _cached_status.installation_id:
            refreshed = evaluate_claims(
                _cached_claims,
                installation_id=_cached_status.installation_id,
                masked_key=_cached_status.masked_key,
                checked_at=_cached_status.checked_at,
            )
            return refreshed, _cached_claims
        return _cached_status, _cached_claims

    installation_id = await ensure_installation_id()
    doc = await get_license_document()
    key = (doc or {}).get("license_key") if doc else None

    if not key:
        status = _status_unlicensed(installation_id)
        claims = None
    else:
        status = evaluate_license_key(key, installation_id=installation_id)
        claims = None
        if status.mode in ("licensed", "grace"):
            try:
                claims = verify_license_token(key, installation_id=installation_id)
            except LicenseVerifyError:
                claims = None

        # Prefer the stored last-check time from Mongo (set by checker / PUT).
        stored_checked_at = (doc or {}).get("checked_at")
        if isinstance(stored_checked_at, datetime) and stored_checked_at.tzinfo is None:
            stored_checked_at = stored_checked_at.replace(tzinfo=timezone.utc)
        status.checked_at = stored_checked_at

        # Persist state if drifted (e.g. first read after bootstrap). Do not
        # treat a missing checked_at as a reason to stamp "now" — restart clears
        # checked_at until the checker runs.
        stored_state = (doc or {}).get("state")
        if stored_state != status.state:
            await update_license_state(
                state=status.state,
                state_code=status.code,
                state_message=status.message,
                set_checked_at=False,
            )

    _cached_at = now_mono
    _cached_status = status
    _cached_claims = claims
    return status, claims


async def get_cached_status(*, force: bool = False, include_masked_key: bool = False) -> LicenseStatus:
    async with _cache_lock:
        status, _ = await _load_status(force=force)
    out = status.model_copy()
    if not include_masked_key:
        out.masked_key = None
    return out


async def get_verified_claims() -> Optional[LicenseClaims]:
    """Return verified claims when a valid (or grace) license is installed."""
    async with _cache_lock:
        status, claims = await _load_status()
    if status.state != "ok" or not status.valid:
        return None
    return claims


async def refresh_license_state() -> LicenseStatus:
    """Re-read Mongo, verify, update state document, refresh cache."""
    global _cached_at, _cached_status, _cached_claims
    async with _cache_lock:
        invalidate_license_cache()
        status, claims = await _load_status(force=True)
        await update_license_state(
            state=status.state,
            state_code=status.code,
            state_message=status.message,
            set_checked_at=True,
        )
        status.checked_at = _utcnow()
        _cached_at = time.monotonic()
        _cached_status = status
        _cached_claims = claims
        return status


async def put_license_key(
    license_key: str,
    *,
    updated_by_user_id: Optional[str] = None,
) -> LicenseStatus:
    installation_id = await ensure_installation_id()
    status = evaluate_license_key(license_key, installation_id=installation_id)
    if status.mode == "invalid":
        # Do not clobber existing key
        raise LicenseVerifyError(
            status.code or "LICENSE_INVALID",
            status.message or "Invalid license key",
        )

    await put_license_key_raw(
        license_key,
        state=status.state,
        state_code=status.code,
        state_message=status.message,
        updated_by_user_id=updated_by_user_id,
    )
    invalidate_license_cache()
    return await get_cached_status(force=True, include_masked_key=True)


async def _checker_loop(stop: asyncio.Event, interval: float) -> None:
    while not stop.is_set():
        try:
            await refresh_license_state()
        except Exception:
            logger.exception("License checker failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def start_license_checker() -> None:
    """Bootstrap key if needed and start the periodic API checker.

    Clears ``checked_at`` on each process start so "Last checked" does not carry
    over from a previous DocRouter process; the first checker tick then stamps
    a fresh value.
    """
    global _checker_task, _checker_stop

    await bootstrap_license_if_needed()
    try:
        await clear_license_checked_at()
        invalidate_license_cache()
    except Exception:
        logger.exception("Failed to clear license checked_at on startup")

    try:
        await refresh_license_state()
    except Exception:
        logger.exception("Initial license refresh failed")

    if _checker_task is not None and not _checker_task.done():
        return

    interval = float(
        os.getenv("LICENSE_CHECK_INTERVAL_SECONDS", str(DEFAULT_CHECK_INTERVAL_SECONDS))
    )
    _checker_stop = asyncio.Event()
    _checker_task = asyncio.create_task(
        _checker_loop(_checker_stop, interval),
        name="license-checker",
    )
    logger.info(f"License checker started (interval={interval}s)")


async def stop_license_checker() -> None:
    global _checker_task, _checker_stop
    if _checker_stop is not None:
        _checker_stop.set()
    if _checker_task is not None:
        _checker_task.cancel()
        try:
            await _checker_task
        except asyncio.CancelledError:
            pass
    _checker_task = None
    _checker_stop = None
