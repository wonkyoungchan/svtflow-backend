import httpx
import re

YOUTUBE_API_KEY = "AIzaSyCgdFF9MZK_Yt_GfYQ-rCtOQhr2ypCdqq4"
TIMEOUT = httpx.Timeout(15.0)

# HYBE LABELS 채널 ID
HYBE_CHANNEL_ID = "UC3IZKseVpdzPSBaWxBxundA"

SVT_KEYWORDS = [
    "seventeen", "세븐틴", "svt", "hoshi", "woozi", "mingyu",
    "s.coups", "jeonghan", "joshua", "wonwoo", "the8", "dokyeom",
    "seungkwan", "vernon", "dino", "bss", "dxs", "cxm",
    "호시", "우지", "민규", "도겸", "승관", "버논", "디노",
    "부석순", "도겸x승관", "에스쿱스x민규",
]

def _is_svt(title):
    t = title.lower()
    return any(k in t for k in SVT_KEYWORDS)

async def fetch_hybe_new_mvs() -> list:
    """HYBE 채널에서 최신 세븐틴 MV 자동 검색"""
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        "?part=snippet"
        "&channelId=" + HYBE_CHANNEL_ID +
        "&q=SEVENTEEN+Official+MV"
        "&type=video"
        "&order=date"
        "&maxResults=20"
        "&key=" + YOUTUBE_API_KEY
    )
    posts = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    vid_id = item.get("id", {}).get("videoId", "")
                    snippet = item.get("snippet", {})
                    title = snippet.get("title", "")
                    published = snippet.get("publishedAt", "").replace("Z", "")
                    thumb = snippet.get("thumbnails", {}).get("high", {}).get("url")

                    if not vid_id or not _is_svt(title):
                        continue

                    posts.append({
                        "vid_id": vid_id,
                        "title": title,
                        "published": published,
                        "thumbnail": thumb,
                    })
        print("[YouTube Search] HYBE 새 MV " + str(len(posts)) + "개 발견")
    except Exception as e:
        print("[YouTube Search] 오류: " + str(e))
    return posts


async def fetch_video_stats(video_ids: list) -> dict:
    """조회수 + 정확한 업로드 날짜 함께 가져오기"""
    if not video_ids:
        return {}

    stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            "?part=statistics,snippet"
            "&id=" + ",".join(batch) +
            "&key=" + YOUTUBE_API_KEY
        )
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        vid_id = item.get("id", "")
                        view_count = int(
                            item.get("statistics", {}).get("viewCount", 0) or 0
                        )
                        published_at = item.get("snippet", {}).get("publishedAt", "")
                        if published_at:
                            published_at = published_at.replace("Z", "")
                        stats[vid_id] = {
                            "views": view_count,
                            "published": published_at,
                        }
        except Exception as e:
            print("[YouTube API] 오류: " + str(e))

    print("[YouTube API] " + str(len(stats)) + "개 조회수+날짜 가져옴")
    return stats


def extract_video_id(url: str) -> str:
    match = re.search(r'(?:v=|youtu\.be/|/v/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else ""
