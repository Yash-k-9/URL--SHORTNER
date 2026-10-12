from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
import json
from datetime import datetime

from database import get_db
from databse_models import Url, Click
from core.utils import generate_short_code
from core.rediss import redis_client
from middleware.rate_limit import rate_limit

from urllib.parse import urlparse

router = APIRouter()

class ShortenRequest(BaseModel):
    url: HttpUrl

class ShortenResponse(BaseModel):
    short_url: str
    orig_url: str

def record_click(url_id: int, client_ip: str | None, user_agent: str | None, referrer: str | None):
    from database import SessionLocal
    db = SessionLocal()
    try:
        click = Click(
            url_id=url_id,
            ip_address=client_ip,
            browser=user_agent,
            referrer=referrer,
            clicked_at=datetime.utcnow()
        )
        db.add(click)
        db.commit()
    except Exception as e:
        # Log error in real app
        pass
    finally:
        db.close()

@router.post("/shorten", response_model=ShortenResponse)
@rate_limit(max_requests=10, time_window=60)
def shorten_url(request: Request, payload: ShortenRequest, db: Session = Depends(get_db)):
    orig_url_str = str(payload.url)
    # Check if orig_url already exists (orig_url has unique=True)
    existing_url = db.query(Url).filter(Url.orig_url == orig_url_str).first()
    if existing_url:
        domain = str(request.base_url)
        return ShortenResponse(
            short_url=f"{domain}{existing_url.short_url}",
            orig_url=orig_url_str
        )
    
    # Generate unique short code
    while True:
        short_code = generate_short_code()
        existing = db.query(Url).filter(Url.short_url == short_code).first()
        if not existing:
            break
            
    # Save to Postgres
    new_url = Url(
        orig_url=orig_url_str,
        short_url=short_code,
        # user_id=None # Anonymous for now
    )
    db.add(new_url)
    db.commit()
    db.refresh(new_url)
    
    # Cache in Redis
    # Format: short_url -> { "orig_url": ..., "id": ... }
    cache_data = {
        "orig_url": orig_url_str,
        "id": new_url.id
    }
    redis_client.set(f"url:{short_code}", json.dumps(cache_data), ex=86400) # Cache for 24 hours
    
    # Return full short URL (in a real app, combine with base domain)
    # For now returning just the code or a localhost URL
    domain = str(request.base_url)
    return ShortenResponse(
        short_url=f"{domain}{short_code}",
        orig_url=orig_url_str
    )

@router.get("/urls", response_model=list[ShortenResponse])
def get_all_urls(request: Request, db: Session = Depends(get_db)):
    urls = db.query(Url).all()
    domain = str(request.base_url)
    
    return [
        ShortenResponse(
            short_url=f"{domain}{u.short_url}",
            orig_url=urlparse(u.orig_url).netloc
        ) for u in urls
    ]
@router.get("/responses")
def url_response(db:Session = Depends(get_db)):
    urls=db.execute(select(Url.orig_url)).scalars().all()
    lis=[]
    for u in urls:
        dic={}
        dic["domain"]=urlparse(u).netloc
        dic['scheme']=urlparse(u).scheme
        lis.append(dic)
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
    redis_key = f"url:{short_code}"
    
    # Extract request info for background task
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")
    
    # 1. Try Redis cache
    cached_data = redis_client.get(redis_key)
    
    if cached_data:
        data = json.loads(cached_data)
        orig_url = data.get("orig_url")
        url_id = data.get("id")
        
        # Track click async
        if url_id:
            background_tasks.add_task(record_click, url_id, client_ip, user_agent, referrer)
            
        return RedirectResponse(url=orig_url, status_code=307)
        
    # 2. Cache miss, check Postgres
    url_obj = db.query(Url).filter(Url.short_url == short_code).first()
    if not url_obj:
        raise HTTPException(status_code=404, detail="URL not found")
        
    # 3. Save back to cache
    cache_data = {
        "orig_url": url_obj.orig_url,
        "id": url_obj.id
    }
    redis_client.set(redis_key, json.dumps(cache_data), ex=86400)
    
    # Track click async
    background_tasks.add_task(record_click, url_obj.id, client_ip, user_agent, referrer)
    
    return RedirectResponse(url=url_obj.orig_url, status_code=307)
