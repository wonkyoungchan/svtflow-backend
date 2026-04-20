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

SVT_KEYWORDS = [
    "세븐틴", "seventeen", "svt",
    "에스쿱스", "정한", "조슈아", "호시", "원우", "우지",
    "디에잇", "민규", "도겸", "승관", "버논", "디노",
    "s.coups", "jeonghan", "joshua", "hoshi", "wonwoo", "woozi",
    "the8", "mingyu", "dokyeom", "seungkwan", "vernon", "dino",
    "최승철", "윤정한", "홍지수", "권순영", "전원우", "이지훈",
    "서명호", "김민규", "이석민", "부승관", "최한솔", "이찬", "문준휘",
]

def _is_svt(text):
    t = text.lower()
    return any(k in t for k in SVT_KEYWORDS)

def classify_posts(posts):
    filtered = []
    for post in posts:
        title  = post.get("title", "")
        full_text = title + " " + post.get("text", "")
        source = post.get("source", "")
        author = post.get("author", "")

        if source == "youtube":
            if "hybe" in author.lower():
                post["content_type"] = "mv"
            elif "seventeen official" in author.lower():
                post["content_type"] = "going17"
            elif "going seventeen" in author.lower():
                post["content_type"] = "going17"
            elif "seventeen mv" in author.lower():
                post["content_type"] = "mv"
        else:
            if not _is_svt(full_text):
                continue
            post["content_type"] = "general"

        # 멤버 분류는 제목(title)만 사용 - 본문 오탐 방지
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

    print("분류 완료: " + str(len(filtered)) + "개 / 원본: " + str(len(posts)) + "개")
    return filtered
