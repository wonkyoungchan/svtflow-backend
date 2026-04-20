import asyncio, hashlib, json, re
from datetime import datetime, timedelta
import feedparser
import httpx
from bs4 import BeautifulSoup

SVT_KEYWORDS = [
    "seventeen","세븐틴","svt","s.coups","jeonghan","joshua","hoshi",
    "wonwoo","woozi","the8","mingyu","dokyeom","seungkwan","vernon","dino",
    "에스쿱스","정한","조슈아","호시","원우","우지","디에잇","민규","도겸","승관","버논","디노",
]

GOOGLE_KEYWORDS = [
    "세븐틴","SEVENTEEN","에스쿱스 세븐틴","정한+세븐틴","조슈아+세븐틴",
    "호시+세븐틴","원우+세븐틴","우지+세븐틴","민규+세븐틴","도겸+세븐틴",
    "승관+세븐틴","버논+세븐틴","디노+세븐틴","SEVENTEEN+comeback","SEVENTEEN+concert",
]

KR_ENT_RSS = [
    ("스타뉴스",    "https://star.mt.co.kr/rss/"),
    ("OSEN",       "https://osen.co.kr/rss/"),
    ("뉴스엔",     "https://www.newsen.com/rss/"),
    ("조이뉴스24",  "https://joynews.inews24.com/rss/"),
    ("마이데일리",  "https://www.mydaily.co.kr/rss/"),
    ("텐아시아",   "https://tenasia.hankyung.com/rss/"),
    ("스포츠조선",  "https://www.sportschosun.com/rss/"),
    ("엑스포츠뉴스","https://xportsnews.com/?act=rss"),
    ("아시아경제",  "https://view.asiae.co.kr/rss/entertain.htm"),
    ("헤럴드POP",  "https://biz.heraldcorp.com/rss/?ct=050100000000"),
    ("이데일리",   "https://rss.edaily.co.kr/entertain.xml"),
    ("한국경제",   "https://www.hankyung.com/rss/entertainment.xml"),
    ("국민일보",   "https://rss.kmib.co.kr/data/kmib_entertain.xml"),
    ("스포츠서울",  "https://www.sportsseoul.com/rss/allArticle.xml"),
    ("연합뉴스",   "https://www.yna.co.kr/rss/entertainment.xml"),
    ("뉴시스",    "https://www.newsis.com/RSS/entertainment.xml"),
]

NAVER_KEYWORDS = [
    "세븐틴","SEVENTEEN","에스쿱스","정한 세븐틴","호시 세븐틴",
    "민규 세븐틴","승관 세븐틴","버논 세븐틴","우지 세븐틴",
]

WEIBO_UIDS = {"SEVENTEEN_official": "6592471661"}
DC_GALLERIES = {}

# 고잉세븐틴 공식 플레이리스트
GOING17_PLAYLISTS = [
    ("PLk_UmMfvZDx21Z9eEQ9DcIlUfZp1uwEup", "going17", "GOING SEVENTEEN"),
    ("PLFo8WcX9UtEdKxtn1XIjOyo2ifV788AC4", "going17", "GOING SEVENTEEN"),
]

# MV 플레이리스트
MV_PLAYLISTS = [
    ("PLRldTKNyS717C0FYxHk5aPrzUM1zPVi-T", "mv", "SEVENTEEN MV"),
    ("PL4qyDL8uSH8bHmGOAeUXBAhqMTxJaymzG", "mv", "SEVENTEEN MV"),
]

TIMEOUT = httpx.Timeout(20.0)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def _make_id(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]

def _is_svt(t):
    return any(k in t.lower() for k in SVT_KEYWORDS)

def _safe_int(tag):
    if not tag:
        return 0
    try:
        return int(tag.get_text(strip=True).replace(",","").replace("-","0").strip())
    except:
        return 0

def _is_shorts(title):
    t = title.lower()
    return "#shorts" in t or "#short" in t

def _parse_views(text):
    if not text:
        return 0
    t = text.lower().replace(",","").replace("views","").replace("조회수","").strip()
    try:
        if "억" in t:   return int(float(t.replace("억","")) * 100000000)
        if "만" in t:   return int(float(t.replace("만","")) * 10000)
        if "b" in t:    return int(float(t.replace("b","")) * 1000000000)
        if "m" in t:    return int(float(t.replace("m","")) * 1000000)
        if "k" in t:    return int(float(t.replace("k","")) * 1000)
        return int(float(t))
    except:
        return 0

def _parse_relative_time(text):
    now = datetime.now()
    t = text.lower().strip()
    m = re.search(r"(\d+)\s*(초|분|시간|일|주|달|개월|년|second|minute|hour|day|week|month|year)", t)
    if not m:
        return ""
    n, unit = int(m.group(1)), m.group(2)
    delta_map = {
        "초": timedelta(seconds=n), "second": timedelta(seconds=n),
        "분": timedelta(minutes=n), "minute": timedelta(minutes=n),
        "시간": timedelta(hours=n), "hour": timedelta(hours=n),
        "일": timedelta(days=n), "day": timedelta(days=n),
        "주": timedelta(weeks=n), "week": timedelta(weeks=n),
        "달": timedelta(days=n*30), "개월": timedelta(days=n*30), "month": timedelta(days=n*30),
        "년": timedelta(days=n*365), "year": timedelta(days=n*365),
    }
    return (now - delta_map.get(unit, timedelta(0))).isoformat()


# ── 세븐틴 공식 채널 RSS → going17 ───────────────────
# ── 최신 MV 고정 목록 (HYBE RSS 보완) ───────────────
RECENT_MV_LIST = [
    # 2026
    ("ScdULYbnjOs", "호시 (HOSHI) '아기자기 (Baby, Honey)' Official MV", "2026-03-14T00:00:00"),
    ("N9X1o0q4aIc", "도겸X승관 (SEVENTEEN) 'Blue' Official MV (Cinema Ver.)", "2026-01-12T00:00:00"),
    ("dZNPbNkKAss", "도겸X승관 (SEVENTEEN) 'Blue' Official MV (Epilogue Ver.)", "2026-01-19T00:00:00"),
    ("skso_fkQcg0", "SEVENTEEN (세븐틴) 'Bad Influence (Prod. by Pharrell Williams)' Official MV", "2026-01-13T00:00:00"),
    # 2025
    ("pS57UX6s-xw", "SEVENTEEN (세븐틴) 'THUNDER' Official MV", "2025-05-26T00:00:00"),
    ("5A7qyhj-HjE", "SEVENTEEN (세븐틴) 'Tiny Light' Official MV", "2025-04-01T00:00:00"),
    ("rEBHjYQ8HoI", "호시X우지 (SEVENTEEN) '동갑내기' Official MV", "2025-03-10T00:00:00"),
    ("Mt9SBZam4X4", "부석순 (SEVENTEEN) '청바지 (Jeans)' Official MV", "2025-01-08T00:00:00"),
    # 2024
    ("5NPe8_gDSr4", "SEVENTEEN (세븐틴) 'LOVE, MONEY, FAME (feat. DJ Khaled)' Official MV", "2024-10-13T00:00:00"),
    
    
    ("bw4AuPrLWeA", "SEVENTEEN (세븐틴) '청춘찬가 (Cheers to Youth)' Official MV", "2024-05-23T00:00:00"),
    ("ThI0pBAbFnk", "SEVENTEEN (세븐틴) 'MAESTRO' Official MV", "2024-04-29T00:00:00"),
    
    # 2023
    
    ("zSQ48zyWZrY", "SEVENTEEN (세븐틴) '음악의 신 (God of Music)' Official MV", "2023-10-23T00:00:00"),
    ("-GQg25oP0S4", "SEVENTEEN (세븐틴) '손오공 (Super)' Official MV", "2023-04-24T00:00:00"),
    # 2022
    ("VCDWg0ljbFQ", "SEVENTEEN (세븐틴) '_WORLD' Official MV", "2022-07-18T00:00:00"),
    ("gRnuFC4Ualw", "SEVENTEEN (세븐틴) 'HOT' Official MV", "2022-05-27T00:00:00"),
    ("bTtNV6hgDno", "SEVENTEEN (세븐틴) 'Darl+ing' Official MV", "2022-04-15T00:00:00"),
    # 2021
    ("WpuatuzSDK4", "SEVENTEEN (세븐틴) 'Rock with you' Official MV", "2021-10-22T00:00:00"),
    ("yCvSR4lSqTg", "SEVENTEEN (세븐틴) 'Ready to love' Official MV", "2021-06-18T00:00:00"),
    # 2020
    ("y3BFuHgBBWk", "SEVENTEEN (세븐틴) 'HOME;RUN' Official MV", "2020-10-19T00:00:00"),
    ("hHFHiNXJBNs", "SEVENTEEN (세븐틴) 'Left & Right' Official MV", "2020-06-22T00:00:00"),
    ("u4iDL3c0T1c", "SEVENTEEN (세븐틴) 'Fallin Flower' Official MV", "2020-04-06T00:00:00"),
    # 2019
    ("ap14O5-G7UA", "SEVENTEEN (세븐틴) '독:Fear' Official MV", "2019-09-16T00:00:00"),
    ("cr_lx0GSfrA", "SEVENTEEN (세븐틴) '숨이 차 (Getting Closer)' Official MV", "2019-09-16T00:00:00"),
    ("F9CrRG6j2SM", "SEVENTEEN (세븐틴) 'HIT' Official MV", "2019-09-16T00:00:00"),
    ("VqfiJCCbTjY", "SEVENTEEN (세븐틴) 'Snap Shoot' Official MV", "2019-07-22T00:00:00"),
    ("_5PELxP8Udg", "SEVENTEEN (세븐틴) '어쩌나 (Oh My!)' Official MV", "2019-01-21T00:00:00"),
    # 2018
    ("gZItyr1SNjU", "SEVENTEEN (세븐틴) '고맙다 (Thanks)' Official MV", "2018-04-09T00:00:00"),
    ("CyzEtbG-sxY", "SEVENTEEN (세븐틴) '박수 (Clap)' Official MV", "2017-10-23T00:00:00"),
    # 2017
    ("zEkg4GBQumc", "SEVENTEEN (세븐틴) '울고 싶지 않아 (Don't Wanna Cry)' Official MV", "2017-05-22T00:00:00"),
    ("J-wFp43XOrA", "SEVENTEEN (세븐틴) 'VERY NICE' Official MV", "2016-07-04T00:00:00"),
    # 2015
    ("ATxFpUUAaB0", "SEVENTEEN (세븐틴) 'Mansae' Official MV", "2015-09-28T00:00:00"),
    ("9rUFQJrCT7M", "SEVENTEEN (세븐틴) 'Adore U' Official MV", "2015-05-29T00:00:00"),
]

def load_recent_mv():
    posts = []
    for vid_id, title, published in RECENT_MV_LIST:
        posts.append({
            "id": _make_id("yt", vid_id),
            "source": "youtube",
            "title": title,
            "text": title,
            "url": "https://www.youtube.com/watch?v=" + vid_id,
            "thumbnail": "https://i.ytimg.com/vi/" + vid_id + "/hqdefault.jpg",
            "author": "HYBE LABELS",
            "published": published,
            "members": [],
            "likes": 0,
            "content_type": "mv",
        })
    print("[Recent MV] " + str(len(posts)) + "개 고정 MV 로드")
    return posts


async def fetch_svt_official():
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCfkXDY7vwkcJ8ddFGz8KusA"
    try:
        feed = feedparser.parse(url)
        posts = []
        for entry in feed.entries[:50]:
            title = entry.get("title", "")
            thumbs = entry.get("media_thumbnail", [{}])
            thumb = thumbs[0].get("url") if thumbs else None
            stats = entry.get("media_statistics", {})
            views = int(stats.get("views", 0) or 0) if isinstance(stats, dict) else 0
            if _is_shorts(title):
                continue
            posts.append({
                "id": _make_id("yt", entry.get("yt_videoid", entry.get("id", ""))),
                "source": "youtube",
                "title": title,
                "text": title,
                "url": entry.get("link", ""),
                "thumbnail": thumb,
                "author": "SEVENTEEN Official",
                "published": entry.get("published", ""),
                "members": [],
                "likes": views,
                "content_type": "going17",
            })
        print("[SVT Official] " + str(len(posts)) + "개 (going17)")
        return posts
    except Exception as e:
        print("[SVT Official] 오류: " + str(e))
        return []


# ── HYBE LABELS RSS → mv ─────────────────────────────
async def fetch_hybe_rss():
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=UC3IZKseVpdzPSBaWxBxundA"
    try:
        feed = feedparser.parse(url)
        posts = []
        for entry in feed.entries[:50]:
            title = entry.get("title", "")
            if not _is_svt(title):
                continue
            if _is_shorts(title):
                continue
            thumbs = entry.get("media_thumbnail", [{}])
            thumb = thumbs[0].get("url") if thumbs else None
            stats = entry.get("media_statistics", {})
            views = int(stats.get("views", 0) or 0) if isinstance(stats, dict) else 0
            link = entry.get("link", "")
            # video ID 추출해서 ID 통일 (플레이리스트와 같은 ID 사용)
            import re as _re
            vid_match = _re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', link)
            vid_id_for_id = vid_match.group(1) if vid_match else entry.get("yt_videoid", entry.get("id", ""))
            posts.append({
                "id": _make_id("yt", vid_id_for_id),
                "source": "youtube",
                "title": title,
                "text": title,
                "url": link,
                "thumbnail": thumb,
                "author": "HYBE LABELS",
                "published": entry.get("published", ""),
                "members": [],
                "likes": views,
                "content_type": "mv",
            })
        print("[HYBE RSS] " + str(len(posts)) + "개 (mv)")
        return posts
    except Exception as e:
        print("[HYBE RSS] 오류: " + str(e))
        return []


# ── 플레이리스트 RSS (조회수 포함) ────────────────────
async def fetch_playlist_rss(playlist_id, content_type, author):
    url = "https://www.youtube.com/feeds/videos.xml?playlist_id=" + playlist_id
    try:
        feed = feedparser.parse(url)
        posts = []
        for entry in feed.entries:
            title = entry.get("title", "")
            thumbs = entry.get("media_thumbnail", [{}])
            thumb = thumbs[0].get("url") if thumbs else None
            stats = entry.get("media_statistics", {})
            views = int(stats.get("views", 0) or 0) if isinstance(stats, dict) else 0
            posts.append({
                "id": _make_id("yt", entry.get("yt_videoid", entry.get("id", ""))),
                "source": "youtube",
                "title": title,
                "text": title,
                "url": entry.get("link", ""),
                "thumbnail": thumb,
                "author": author,
                "published": entry.get("published", ""),
                "members": [],
                "likes": views,
                "content_type": content_type,
            })
        print("[Playlist RSS:" + content_type + "] " + str(len(posts)) + "개")
        return posts
    except Exception as e:
        print("[Playlist RSS] 오류: " + str(e))
        return []


# ── 플레이리스트 스크래핑 (조회수+날짜 포함) ──────────
async def fetch_playlist_scrape(playlist_id, content_type, author):
    url = "https://www.youtube.com/playlist?list=" + playlist_id
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            m = re.search(r'var ytInitialData = ({.*?});</script>', resp.text, re.DOTALL)
            if not m:
                return []
            data = json.loads(m.group(1))
            try:
                contents = (data["contents"]["twoColumnBrowseResultsRenderer"]
                            ["tabs"][0]["tabRenderer"]["content"]
                            ["sectionListRenderer"]["contents"][0]
                            ["itemSectionRenderer"]["contents"][0]
                            ["playlistVideoListRenderer"]["contents"])
            except:
                return []
            posts = []
            for item in contents:
                v = item.get("playlistVideoRenderer", {})
                if not v:
                    continue
                vid_id = v.get("videoId", "")
                title = v.get("title", {}).get("runs", [{}])[0].get("text", "")
                if not title or not vid_id:
                    continue
                view_runs = v.get("videoInfo", {}).get("runs", [])
                view_text = view_runs[0].get("text", "") if view_runs else ""
                views = _parse_views(view_text)
                time_text = ""
                for run in view_runs:
                    t = run.get("text", "")
                    if any(u in t.lower() for u in ["ago","전","년","달","주","일","시간","분","year","month","week","day","hour"]):
                        time_text = t
                        break
                published = _parse_relative_time(time_text)
                posts.append({
                    "id": _make_id("yt", vid_id),
                    "source": "youtube",
                    "title": title,
                    "text": title,
                    "url": "https://www.youtube.com/watch?v=" + vid_id,
                    "thumbnail": "https://i.ytimg.com/vi/" + vid_id + "/hqdefault.jpg",
                    "author": author,
                    "published": published,
                    "members": [],
                    "likes": views,
                    "content_type": content_type,
                })
            print("[Playlist Scrape:" + content_type + "] " + str(len(posts)) + "개")
            return posts
    except Exception as e:
        print("[Playlist Scrape] 오류: " + str(e))
        return []


# ── YouTube API로 플레이리스트 전체 가져오기 (페이지네이션) ──
async def fetch_playlist_all_api(playlist_id, content_type, author):
    """YouTube Data API로 플레이리스트 전체 영상 가져오기"""
    from youtube_api import YOUTUBE_API_KEY
    posts = []
    next_page = None
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            while True:
                url = (
                    "https://www.googleapis.com/youtube/v3/playlistItems"
                    "?part=snippet,contentDetails"
                    "&playlistId=" + playlist_id +
                    "&maxResults=50"
                    "&key=" + YOUTUBE_API_KEY +
                    (("&pageToken=" + next_page) if next_page else "")
                )
                resp = await client.get(url)
                if resp.status_code != 200:
                    break
                    
                data = resp.json()
                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    vid_id = snippet.get("resourceId", {}).get("videoId", "")
                    title = snippet.get("title", "")
                    published = snippet.get("publishedAt", "").replace("Z", "")
                    thumb = snippet.get("thumbnails", {}).get("high", {}).get("url")
                    
                    if not vid_id or title in ("Deleted video", "Private video"):
                        continue
                    
                    posts.append({
                        "id": _make_id("yt", vid_id),
                        "source": "youtube",
                        "title": title,
                        "text": title,
                        "url": "https://www.youtube.com/watch?v=" + vid_id,
                        "thumbnail": thumb or "https://i.ytimg.com/vi/" + vid_id + "/hqdefault.jpg",
                        "author": author,
                        "published": published,
                        "members": [],
                        "likes": 0,
                        "content_type": content_type,
                    })
                
                next_page = data.get("nextPageToken")
                if not next_page:
                    break
                    
        print("[Playlist API:" + content_type + "] " + str(len(posts)) + "개 (전체)")
        return posts
    except Exception as e:
        print("[Playlist API] 오류: " + str(e))
        return []


# ── 한국 연예 뉴스 RSS ────────────────────────────────
async def fetch_kr_ent_rss(name, rss_url):
    try:
        feed = feedparser.parse(rss_url)
        posts = []
        for entry in feed.entries[:50]:
            title = entry.get("title", "")
            if not _is_svt(title + " " + entry.get("summary", "")):
                continue
            thumb = None
            if entry.get("media_thumbnail"):
                thumb = entry["media_thumbnail"][0].get("url")
            elif entry.get("enclosures"):
                for enc in entry["enclosures"]:
                    if "image" in enc.get("type", ""):
                        thumb = enc.get("href") or enc.get("url")
                        break
            if not thumb:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.get("summary",""))
                if img_match:
                    thumb = img_match.group(1)
            posts.append({
                "id": _make_id("news", entry.get("link", entry.get("id", ""))),
                "source": "news",
                "title": title,
                "text": title + " " + entry.get("summary", ""),
                "url": entry.get("link", ""),
                "thumbnail": thumb,
                "author": name,
                "published": entry.get("published", ""),
                "members": [],
                "likes": 0,
                "content_type": "general",
            })
        if posts:
            print("[" + name + "] " + str(len(posts)) + "개")
        return posts
    except Exception as e:
        print("[" + name + "] 오류: " + str(e))
        return []


# ── 구글 뉴스 ─────────────────────────────────────────
async def fetch_google_news(keyword):
    url = "https://news.google.com/rss/search?q=" + keyword + "&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        posts = []
        for entry in feed.entries[:20]:
            src = entry.get("source", {})
            author = src.get("title", "") if isinstance(src, dict) else ""
            posts.append({
                "id": _make_id("news", entry.get("link", entry.get("id", ""))),
                "source": "news",
                "title": entry.get("title", ""),
                "text": entry.get("title","") + " " + entry.get("summary",""),
                "url": entry.get("link", ""),
                "thumbnail": None,
                "author": author,
                "published": entry.get("published", ""),
                "members": [],
                "likes": 0,
                "content_type": "general",
            })
        return posts
    except Exception as e:
        return []


# ── 네이버 뉴스 ───────────────────────────────────────
async def fetch_naver_news(keyword):
    from urllib.parse import quote
    url = "https://search.naver.com/search.naver?where=news&query=" + quote(keyword) + "&sort=1"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            posts = []
            for item in soup.select("div.news_area")[:15]:
                title_tag = item.select_one("a.news_tit")
                if not title_tag:
                    continue
                title = title_tag.get("title", title_tag.get_text(strip=True))
                link = title_tag.get("href", "")
                press = item.select_one("a.info.press")
                author = press.get_text(strip=True) if press else "네이버뉴스"
                thumb_tag = item.select_one("img.thumb")
                thumb = thumb_tag.get("src") if thumb_tag else None
                published = ""
                for tag in item.select("span.info"):
                    t = tag.get_text(strip=True)
                    if any(u in t for u in ["분 전","시간 전","일 전","어제"]):
                        published = _parse_relative_time(t)
                        break
                posts.append({
                    "id": _make_id("news", link),
                    "source": "news",
                    "title": title,
                    "text": title,
                    "url": link,
                    "thumbnail": thumb,
                    "author": author,
                    "published": published,
                    "members": [],
                    "likes": 0,
                    "content_type": "general",
                })
            return posts
    except Exception as e:
        return []


# ── 디스패치 스크래핑 ─────────────────────────────────
async def fetch_dispatch():
    url = "https://www.dispatch.co.kr/category/news"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            posts = []
            for item in soup.select("article, div.item-wrap, li.item")[:30]:
                title_tag = item.select_one("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if not link.startswith("http"):
                    link = "https://www.dispatch.co.kr" + link
                if not _is_svt(title):
                    continue
                posts.append({
                    "id": _make_id("dispatch", link),
                    "source": "news",
                    "title": title,
                    "text": title,
                    "url": link,
                    "thumbnail": None,
                    "author": "디스패치",
                    "published": datetime.now().isoformat(),
                    "members": [],
                    "likes": 0,
                    "content_type": "general",
                })
            print("[디스패치] " + str(len(posts)) + "개")
            return posts
    except Exception as e:
        print("[디스패치] 오류: " + str(e))
        return []


# ── Weibo ─────────────────────────────────────────────
async def fetch_weibo(name, uid):
    url = "https://m.weibo.cn/api/container/getIndex?uid=" + uid + "&type=uid&page=1"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            posts = []
            for card in resp.json().get("data",{}).get("cards",[])[:15]:
                m = card.get("mblog",{})
                if not m:
                    continue
                txt = BeautifulSoup(m.get("text",""), "html.parser").get_text()
                pics = m.get("pic_urls",[])
                posts.append({
                    "id": _make_id("wb", m.get("id","")),
                    "source": "weibo",
                    "title": txt[:80],
                    "text": txt,
                    "url": "https://weibo.com/" + uid + "/" + m.get("id",""),
                    "thumbnail": pics[0].get("thumbnail_pic") if pics else None,
                    "author": name,
                    "published": m.get("created_at",""),
                    "members": [],
                    "likes": m.get("attitudes_count",0),
                    "content_type": "general",
                })
            return posts
    except Exception as e:
        return []


# ── 디씨인사이드 ──────────────────────────────────────
async def fetch_dcinside(name, gall_id):
    url = "https://gall.dcinside.com/board/lists/?id=" + gall_id
    h = dict(HEADERS)
    h["Accept-Language"] = "ko-KR,ko;q=0.9"
    h["Referer"] = "https://gall.dcinside.com/"
    try:
        async with httpx.AsyncClient(headers=h, timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text,"html.parser")
            posts = []
            for row in soup.select("tr.ub-content")[:30]:
                t = row.select_one("td.gall_tit a:first-child")
                if not t:
                    continue
                link = t.get("href","")
                if link and not link.startswith("http"):
                    link = "https://gall.dcinside.com" + link
                posts.append({
                    "id": _make_id("dc",link),
                    "source": "dcinside",
                    "title": t.get_text(strip=True),
                    "text": t.get_text(strip=True),
                    "url": link,
                    "thumbnail": None,
                    "author": name,
                    "published": "",
                    "members": [],
                    "likes": _safe_int(row.select_one("td.gall_recommend")),
                    "content_type": "general",
                })
            posts.sort(key=lambda x: x["likes"], reverse=True)
            return posts
    except Exception as e:
        return []


# ── 전체 수집 ─────────────────────────────────────────
async def fetch_all_sources():
    tasks = []

    # HYBE 채널 → mv
    tasks.append(fetch_hybe_rss())


    # 고잉세븐틴 플레이리스트 (RSS + 스크래핑)
    # 고잉세븐틴은 YouTube API로 전체 가져오기
    for pl_id, ctype, author in GOING17_PLAYLISTS:
        tasks.append(fetch_playlist_all_api(pl_id, ctype, author))

    # MV 플레이리스트 (RSS + 스크래핑)
    # MV 플레이리스트도 YouTube API로 전체 가져오기
    for pl_id, ctype, author in MV_PLAYLISTS:
        tasks.append(fetch_playlist_all_api(pl_id, ctype, author))

    # 뉴스
    for name, rss_url in KR_ENT_RSS:
        tasks.append(fetch_kr_ent_rss(name, rss_url))
    for kw in GOOGLE_KEYWORDS:
        tasks.append(fetch_google_news(kw))
    for kw in NAVER_KEYWORDS:
        tasks.append(fetch_naver_news(kw))
    tasks.append(fetch_dispatch())

    # 네이버 API 뉴스
    from naver_api import fetch_all_naver_news
    tasks.append(fetch_all_naver_news())

    # 커뮤니티
    for name, uid in WEIBO_UIDS.items():
        tasks.append(fetch_weibo(name, uid))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_posts = []
    seen = set()
    for result in results:
        if isinstance(result, list):
            for p in result:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    all_posts.append(p)

    def parse_date(p):
        try:
            return datetime.fromisoformat(
                p["published"].replace("Z","+00:00")
            ).replace(tzinfo=None)
        except:
            return datetime.min

    all_posts.sort(key=parse_date, reverse=True)
    # 최신 MV 고정 목록 추가 (중복은 seen으로 제거됨)
    for p in load_recent_mv():
        if p["id"] not in seen:
            seen.add(p["id"])
            all_posts.append(p)

    # 뉴스 썸네일 보완
    all_posts = await enrich_thumbnails(all_posts)
    print("총 " + str(len(all_posts)) + "개 수집 완료")
    return all_posts





# ── OG 이미지 일괄 가져오기 ───────────────────────────
async def enrich_thumbnails(posts: list) -> list:
    """썸네일 없는 뉴스 기사에서 og:image 가져오기"""
    news_without_thumb = [
        p for p in posts
        if p.get("source") in ("news",) and not p.get("thumbnail")
    ]
    if not news_without_thumb:
        return posts

    async def fetch_og(post):
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(post["url"], follow_redirects=True)
                if resp.status_code != 200:
                    return
                # og:image 추출
                m = re.search(
                    r'<meta[^>]+(?:property=["\']og:image["\']|name=["\']og:image["\'])[^>]+content=["\']([^"\']+)["\']',
                    resp.text, re.IGNORECASE
                )
                if not m:
                    m = re.search(
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                        resp.text, re.IGNORECASE
                    )
                if m:
                    thumb = m.group(1).strip()
                    if thumb.startswith("//"):
                        thumb = "https:" + thumb
                    if thumb.startswith("http"):
                        post["thumbnail"] = thumb
        except:
            pass

    # 최대 150개 병렬로 가져오기
    batch_size = 50
    total_filled = 0
    for i in range(0, min(len(news_without_thumb), 150), batch_size):
        batch = news_without_thumb[i:i+batch_size]
        await asyncio.gather(*[fetch_og(p) for p in batch])
        filled = len([p for p in batch if p.get("thumbnail")])
        total_filled += filled

    print("[OG Image] " + str(total_filled) + "개 썸네일 보완")
    return posts
