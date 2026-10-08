#!/usr/bin/env python3
"""יוצר את social.json מההרצה האחרונה (שהצליחה) של Instagram Hashtag Scraper ב-Apify.

הרצה:  python scripts/sync_apify.py
האסימון נקרא ממשתנה הסביבה APIFY_TOKEN או מקובץ .env (שלא עולה לריפו).
הסקריפט רק קורא מ-Apify, ולא משנה שום דבר בחשבון.
"""
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTOR = "apify~instagram-hashtag-scraper"
API = "https://api.apify.com/v2"


def load_token():
    token = os.environ.get("APIFY_TOKEN", "").strip()
    env_file = ROOT / ".env"
    if not token and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*APIFY_TOKEN\s*=\s*(.+)", line)
            if m:
                token = m.group(1).strip().strip('"').strip("'")
    if not token:
        sys.exit("חסר APIFY_TOKEN (משתנה סביבה או שורה בקובץ .env)")
    return token


def get(path, token):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.load(res)


def main():
    token = load_token()
    runs = get(f"/acts/{ACTOR}/runs?limit=1&desc=1&status=SUCCEEDED", token)["data"]["items"]
    if not runs:
        sys.exit("לא נמצאה הרצה מוצלחת של ה-Actor")
    run = runs[0]
    raw = get(f"/datasets/{run['defaultDatasetId']}/items?clean=true&format=json&limit=1000", token)

    posts, seen = [], set()
    for it in raw:
        code = it.get("shortCode") or it.get("id")
        if not code or code in seen:
            continue
        seen.add(code)
        posts.append({
            "id": code,
            "url": it.get("url") or "",
            "caption": (it.get("caption") or "").strip(),
            "author": it.get("ownerFullName") or "",
            "username": it.get("ownerUsername") or "",
            "likes": max(it.get("likesCount") or 0, 0),
            "comments": it.get("commentsCount") or 0,
            "timestamp": it.get("timestamp") or "",
            "type": it.get("type") or "",
            "hashtags": [h.lower() for h in (it.get("hashtags") or [])],
            "searchTag": (it.get("inputUrl") or "").rstrip("/").split("/")[-1],
        })

    doc = {
        "meta": {
            "source": "apify",
            "actor": "apify/instagram-hashtag-scraper",
            "runId": run["id"],
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(posts),
            "searchTags": sorted({p["searchTag"] for p in posts if p["searchTag"]}),
        },
        "posts": posts,
    }
    out = ROOT / "social.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    top = Counter(h for p in posts for h in p["hashtags"]).most_common(5)
    print(f"נשמרו {len(posts)} פוסטים ב-{out.name}. האשטאגים נפוצים: {top}")


if __name__ == "__main__":
    main()
