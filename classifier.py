import re

MEMBER_KEYWORDS = {
    "에스쿱스": ["에스쿱스", "s.coups", "최승철"],
    "정한":    ["정한", "jeonghan", "윤정한"],
    "조슈아":  ["조슈아", "joshua", "홍지수"],
    "준":     ["준", "문준휘", "junhui"],
    "호시":   ["호시", "hoshi", "권순영"],
    "원우":   ["원우", "wonwoo", "전원우"],
    "우지":   ["우지", "woozi", "이지훈"],
    "디에잇":  ["디에잇", "the8", "서명호"],
    "민규":   ["민규", "mingyu", "김민규"],
    "도겸":   ["도겸", "dokyeom", "이석민"],
    "승관":   ["승관", "seungkwan", "부승관"],
    "버논":   ["버논", "vernon", "최한솔"],
    "디노":   ["디노", "dino", "이찬"],
}

_MV_PATTERN = re.compile(
    r'\bM/?V\b|Official\s*(Music\s*)?Video|Performance\s*Video|Official\s*MV',
    re.IGNORECASE,
)

_GOING17_PATTERN = re.compile(
    r'going\s*seventeen|고잉\s*세븐틴|going\s*svt|going\s*dxs',
    re.IGNORECASE,
)

def _is_mv_title(title):
    return bool(_MV_PATTERN.search(title))

def _is_going17_title(title):
    return bool(_GOING17_PATTERN.search(title))

def classify_posts(posts, quiet=False):
    filtered = []
    for post in posts:
        title = post.get("title", "")
        source = post.get("source", "")
        ct = post.get("content_type", "")

        if source == "youtube":
            if ct == "going17" and _is_mv_title(title):
                post["content_type"] = "mv"
            elif ct == "mv" and _is_going17_title(title) and not _is_mv_title(title):
                post["content_type"] = "going17"
            elif ct not in ("going17", "mv"):
                if _is_going17_title(title) and not _is_mv_title(title):
                    post["content_type"] = "going17"
                else:
                    post["content_type"] = "mv"

        t = title.lower()
        scores = {}
        for member, keywords in MEMBER_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in t)
            if score > 0:
                scores[member] = score

        if scores:
            post["members"] = sorted(scores, key=scores.get, reverse=True)[:2]
        else:
            post["members"] = ["전체"]

        filtered.append(post)

    if not quiet:
        print("분류 완료: " + str(len(filtered)) + "개 / 원본: " + str(len(posts)) + "개")
    return filtered
