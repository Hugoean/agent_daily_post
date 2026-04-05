import re
import datetime
import time
import feedparser

from config.settings import PRODUCT_SOURCES, PRODUCT_KEYWORDS
from utils.helpers import http_get, clean_html


def fetch_products() -> list:
    raw_items = []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

    for src in PRODUCT_SOURCES:
        try:
            feed  = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                title = entry.get("title", "")
                body  = clean_html(
                    entry.get("summary", "") or
                    (entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
                )
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    pub_dt = datetime.datetime(*pub[:6])
                    if pub_dt < cutoff:
                        continue
                text = (title + " " + body).lower()
                if not any(kw in text for kw in PRODUCT_KEYWORDS):
                    continue
                raw_items.append({
                    "title":    title,
                    "link":     entry.get("link", "#"),
                    "abstract": body[:300],
                    "authors":  "", "affil": "",
                    "source":   src["name"],
                    "type":     "product",
                })
                count += 1
                if count >= src["max"]:
                    break
            print(f"  {src['name']}: {count}条")
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] {src['name']}: {e}")

    try:
        html = http_get("https://github.com/trending?since=daily&spoken_language_code=")
        repos = re.findall(
            r'<h2[^>]*>\s*<a[^>]*href="(/[^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<p[^>]*>(.*?)</p>)?',
            html, re.DOTALL
        )
        count = 0
        for repo_path, repo_name, desc in repos[:30]:
            repo_name = clean_html(repo_name).strip()
            desc      = clean_html(desc or "").strip()
            text      = (repo_name + " " + desc).lower()
            if not any(kw in text for kw in PRODUCT_KEYWORDS):
                continue
            raw_items.append({
                "title":    f"🔥 GitHub Trending: {repo_name.strip()}",
                "link":     f"https://github.com{repo_path.strip()}",
                "abstract": desc or "今日GitHub热门AI项目",
                "authors":  "", "affil": "",
                "source":   "GitHub Trending",
                "type":     "product",
            })
            count += 1
            if count >= 4:
                break
        print(f"  GitHub Trending: {count}条")
    except Exception as e:
        print(f"[WARN] GitHub Trending: {e}")
    return raw_items
