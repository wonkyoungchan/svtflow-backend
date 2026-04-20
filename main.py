from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json, os

from fetcher import fetch_all_sources
from classifier import classify_posts
from youtube_api import fetch_video_stats, extract_video_id, fetch_hybe_new_mvs

CACHE_FILE = "cache.json"

def save_cache(posts):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _normalize_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    except:
        pass
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    except:
        pass
    return date_str

def parse_date(p):
    pub = p.get("published", "")
    if not pub:
        return datetime.min
    try:
        return datetime.fromisoformat(pub)
    except:
        return datetime.min

async def refresh_data():
    print("데이터 갱신 중...")
    new_posts = await fetch_all_sources()
    new_posts = classify_posts(new_posts)

    existing = load_cache()
    existing_map = {p["id"]: p for p in existing}

    added = 0
    for post in new_posts:
        if post["id"] not in existing_map:
            existing_map[post["id"]] = post
            added += 1
        else:
            existing_map[post["id"]]["likes"] = post.get("likes", 0)

    all_posts = list(existing_map.values())

    # HYBE 채널에서 새 MV 자동 검색 후 추가
    hybe_new = await fetch_hybe_new_mvs()
    for item in hybe_new:
        vid_id = item["vid_id"]
        post_id = __import__('hashlib').md5(("yt|" + vid_id).encode()).hexdigest()[:16]
        if post_id not in {p["id"] for p in all_posts}:
            all_posts.append({
                "id": post_id,
                "source": "youtube",
                "title": item["title"],
                "text": item["title"],
                "url": "https://www.youtube.com/watch?v=" + vid_id,
                "thumbnail": item.get("thumbnail"),
                "author": "HYBE LABELS",
                "published": item["published"],
                "members": [],
                "likes": 0,
                "content_type": "mv",
            })

    # YouTube API로 조회수 + 정확한 날짜 업데이트
    youtube_posts = [p for p in all_posts if p.get("source") == "youtube"]
    video_ids = []
    for p in youtube_posts:
        vid_id = extract_video_id(p.get("url", ""))
        if vid_id:
            video_ids.append(vid_id)

    if video_ids:
        stats = await fetch_video_stats(list(set(video_ids)))
        for p in all_posts:
            if p.get("source") == "youtube":
                vid_id = extract_video_id(p.get("url", ""))
                if vid_id and vid_id in stats:
                    p["likes"] = stats[vid_id]["views"]
                    # API에서 받은 정확한 날짜로 교체
                    if stats[vid_id]["published"]:
                        p["published"] = stats[vid_id]["published"]

    # MV/Going17 중복 제목 제거 (같은 제목 영상은 최신 1개만 유지)
    yt_by_title = {}
    news_posts = []
    for p in all_posts:
        if p.get('source') == 'youtube':
            key = p.get('title','').strip()[:50] + p.get('content_type','')
            existing = yt_by_title.get(key)
            pub = p.get('published','')
            if not existing or pub > existing.get('published',''):
                yt_by_title[key] = p
        else:
            news_posts.append(p)
    all_posts = list(yt_by_title.values()) + news_posts

    # 모든 날짜를 ISO 형식으로 정규화
    for p in all_posts:
        p["published"] = _normalize_date(p.get("published", ""))

    # 날짜 필터
    now = datetime.now()
    filtered = []
    for p in all_posts:
        source = p.get("source", "")
        dt = parse_date(p)
        if source == "youtube":
            filtered.append(p)
        else:
            if dt == datetime.min or dt > now - timedelta(days=90):
                filtered.append(p)

    filtered.sort(key=parse_date, reverse=True)
    filtered = filtered[:5000]

    save_cache(filtered)
    print("새 게시물 " + str(added) + "개 추가, 총 " + str(len(filtered)) + "개")

@asynccontextmanager
async def lifespan(app):
    await refresh_data()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_data, "interval", minutes=3)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="SVT FLOW API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "https://svt-flow-adbc0.web.app",
        "https://svt-flow-adbc0.firebaseapp.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/posts")
async def get_posts(limit: int = Query(default=2000, ge=1, le=5000)):
    return {"posts": load_cache()[:limit], "count": len(load_cache())}

@app.get("/members")
async def get_members():
    return {"members": [
        "에스쿱스","정한","조슈아","준","호시",
        "원우","우지","디에잇","민규","도겸","승관","버논","디노",
    ]}

@app.post("/refresh")
async def manual_refresh():
    await refresh_data()
    return {"status": "ok", "count": len(load_cache())}

@app.get("/health")
async def health():
    data = load_cache()
    youtube = len([p for p in data if p.get("source") == "youtube"])
    news = len([p for p in data if p.get("source") != "youtube"])
    mv = len([p for p in data if p.get("content_type") == "mv"])
    g17 = len([p for p in data if p.get("content_type") == "going17"])
    return {"status": "running", "total": len(data),
            "youtube": youtube, "news": news, "mv": mv, "going17": g17}
