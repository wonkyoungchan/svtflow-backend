import httpx
from datetime import datetime
import hashlib

NAVER_CLIENT_ID = "l_FcauE4uOYFmW1nWUOd"
NAVER_CLIENT_SECRET = "uEnbahULbM"

HEADERS = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
}

TIMEOUT = httpx.Timeout(10.0)

# 검색 키워드 목록
KEYWORDS = [
    "세븐틴", "SEVENTEEN", "에스쿱스", "정한 세븐틴", "조슈아 세븐틴",
    "준 세븐틴", "호시 세븐틴", "원우 세븐틴", "우지 세븐틴",
    "디에잇 세븐틴", "민규 세븐틴", "도겸 세븐틴", "승관 세븐틴",
    "버논 세븐틴", "디노 세븐틴", "세븐틴 컴백", "세븐틴 콘서트",
    "세븐틴 앨범", "세븐틴 투어",
]

def _make_id(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]

def _parse_date(pub_date: str) -> str:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub_date).replace(tzinfo=None).isoformat()
    except:
        return ""

async def fetch_naver_news_api(keyword: str) -> list:
    from urllib.parse import quote
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {
        "query": keyword,
        "display": 20,
        "sort": "date",  # 최신순
    }
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                print("[Naver API] " + keyword + " 오류: " + str(resp.status_code))
                return []
            items = resp.json().get("items", [])
            posts = []
            for item in items:
                # HTML 태그 제거
                import re
                title = re.sub(r'<[^>]+>', '', item.get("title", ""))
                desc  = re.sub(r'<[^>]+>', '', item.get("description", ""))
                link  = item.get("originallink") or item.get("link", "")
                # 언론사 추출 (link에서)
                author = ""
                m = re.search(r'https?://(?:www\.)?([^/]+)', link)
                if m:
                    domain = m.group(1)
                    # 도메인에서 언론사명 추출
                    author = domain.split('.')[0].upper()

                posts.append({
                    "id": _make_id("naver_api", link),
                    "source": "news",
                    "title": title,
                    "text": title + " " + desc,
                    "url": link,
                    "thumbnail": None,
                    "author": author or "네이버뉴스",
                    "published": _parse_date(item.get("pubDate", "")),
                    "members": [],
                    "likes": 0,
                    "content_type": "general",
                })
            return posts
    except Exception as e:
        print("[Naver API] " + keyword + " 오류: " + str(e))
        return []

async def fetch_all_naver_news() -> list:
    import asyncio
    tasks = [fetch_naver_news_api(kw) for kw in KEYWORDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_posts = []
    seen = set()
    for result in results:
        if isinstance(result, list):
            for p in result:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    all_posts.append(p)
    
    print("[Naver API] 총 " + str(len(all_posts)) + "개 뉴스 수집")
    return all_posts
