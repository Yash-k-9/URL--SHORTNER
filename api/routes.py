from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
import json
import logging
from datetime import datetime

import redis

from database import get_db, SessionLocal
from databse_models import Url, Click, User
from api.auth import get_current_user, get_optional_user
from core.config import CACHE_TTL_SECONDS
from core.utils import generate_short_code, utcnow
from core.rediss import redis_client
from middleware.rate_limit import rate_limit

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_CODE_ATTEMPTS = 5

class ShortenRequest(BaseModel):
    url: HttpUrl

class ShortenResponse(BaseModel):
    short_url: str
    orig_url: str

def _is_expired(expires_at: datetime | None) -> bool:
    return expires_at is not None and expires_at <= utcnow()

def cache_get(short_code: str) -> dict | None:
    try:
        cached = redis_client.get(f"url:{short_code}")
    except redis.RedisError:
        logger.warning("Redis unavailable, falling back to Postgres", exc_info=True)
        return None
    return json.loads(cached) if cached else None

def cache_set(url_obj: Url) -> None:
    # Never keep a link in the cache past its expiry
    ttl = CACHE_TTL_SECONDS
    if url_obj.expires_at is not None:
        ttl = min(ttl, int((url_obj.expires_at - utcnow()).total_seconds()))
    if ttl <= 0:
        return

    # Format: url:<short_code> -> { "orig_url": ..., "id": ..., "expires_at": ... }
    cache_data = {
        "orig_url": url_obj.orig_url,
        "id": url_obj.id,
        "expires_at": url_obj.expires_at.isoformat() if url_obj.expires_at else None,
    }
    try:
        redis_client.set(f"url:{url_obj.short_url}", json.dumps(cache_data), ex=ttl)
    except redis.RedisError:
        logger.warning("Could not write to Redis cache", exc_info=True)

def record_click(url_id: int, client_ip: str | None, user_agent: str | None, referrer: str | None):
    db = SessionLocal()
    try:
        click = Click(
            url_id=url_id,
            ip_address=client_ip,
            browser=user_agent,
            referrer=referrer,
            clicked_at=utcnow()
        )
        db.add(click)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record click for url_id=%s", url_id)
    finally:
        db.close()

def _find_reusable(db: Session, orig_url: str) -> Url | None:
    # Only reuse anonymous, non-expiring links so one user never gets another user's link
    return db.query(Url).filter(
        Url.orig_url == orig_url,
        Url.user_id.is_(None),
        Url.expires_at.is_(None),
    ).first()

@router.post("/shorten", response_model=ShortenResponse)
@rate_limit(max_requests=3, time_window=60)
def shorten_url(
    request: Request,
    payload: ShortenRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    orig_url_str = str(payload.url)
    domain = str(request.base_url)

    for _ in range(MAX_CODE_ATTEMPTS):
        # Logged-in users always get their own link so it shows up in their /urls
        existing_url = _find_reusable(db, orig_url_str) if user is None else None
        if existing_url:
            return ShortenResponse(
                short_url=f"{domain}{existing_url.short_url}",
                orig_url=orig_url_str
            )

        # Let the unique constraint on short_url catch collisions instead of a
        # check-then-insert, which races under concurrent requests
        new_url = Url(
            orig_url=orig_url_str,
            short_url=generate_short_code(),
            user_id=user.id if user else None,
        )
        db.add(new_url)
        try:
            db.commit()
        except IntegrityError:
            # Short code collision, or a concurrent request inserted the same URL
            db.rollback()
            continue

        db.refresh(new_url)
        cache_set(new_url)
        return ShortenResponse(
            short_url=f"{domain}{new_url.short_url}",
            orig_url=orig_url_str
        )

    logger.error("Could not generate a unique short code after %d attempts", MAX_CODE_ATTEMPTS)
    raise HTTPException(status_code=503, detail="Could not create short URL, please try again.")

@router.get("/urls", response_model=list[ShortenResponse])
def get_all_urls(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Only the logged-in user's own links
    urls = db.query(Url).filter(Url.user_id == user.id).order_by(Url.id.desc()).offset(skip).limit(limit).all()
    domain = str(request.base_url)

    return [
        ShortenResponse(
            short_url=f"{domain}{u.short_url}",
            orig_url=u.orig_url
        ) for u in urls
    ]

@router.get("/responses")
def url_response(db:Session = Depends(get_db)):
    urls=db.execute(select(Url.orig_url)).scalars().all()
    lis=[]
    for u in urls:
        parsed=urlparse(u)
        lis.append({"domain": parsed.netloc, "scheme": parsed.scheme})
    return lis


@router.get("/url", response_model=ShortenResponse)
def get_url_by_original(request: Request, orig_url: HttpUrl, db: Session = Depends(get_db)):
    orig_url_str = str(orig_url)
    url_obj = db.query(Url).filter(Url.orig_url == orig_url_str).first()

    if not url_obj:
        raise HTTPException(status_code=404, detail="Original URL not found")

    domain = str(request.base_url)
    return ShortenResponse(
        short_url=f"{domain}{url_obj.short_url}",
        orig_url=url_obj.orig_url
    )

@router.get("/{short_code}")
@rate_limit(max_requests=60, time_window=60)
def redirect_url(request: Request, short_code: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Extract request info for background task
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")

    # 1. Try Redis cache
    data = cache_get(short_code)
    if data:
        orig_url = data["orig_url"]
        url_id = data["id"]
        expires_at = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
    else:
        # 2. Cache miss (or Redis down), check Postgres
        url_obj = db.query(Url).filter(Url.short_url == short_code).first()
        if not url_obj:
            raise HTTPException(status_code=404, detail="URL not found")
        orig_url, url_id, expires_at = url_obj.orig_url, url_obj.id, url_obj.expires_at

        # 3. Save back to cache
        cache_set(url_obj)

    if _is_expired(expires_at):
        raise HTTPException(status_code=410, detail="This short URL has expired")

    # Track click async
    background_tasks.add_task(record_click, url_id, client_ip, user_agent, referrer)

    return RedirectResponse(url=orig_url, status_code=307)
