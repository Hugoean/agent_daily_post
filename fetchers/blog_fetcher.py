import time
import feedparser

from config.settings import BLOG_SOURCES
from utils.helpers import clean_html, is_agent_related


def fetch_blogs() -> list:
    results = []
    for src in BLOG_SOURCES:
        try:
            feed  = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                title = entry.get("title","")
                body  = clean_html(
                    entry.get("summary","") or
                    (entry.get("content",[{}])[0].get("value","") if entry.get("content") else "")
                )
                if not is_agent_related(title, body):
                    continue
                results.append({
                    "title": title, "link": entry.get("link","#"),
                    "abstract": body, "authors": "", "affil": "",
                    "source": src["name"], "type": "blog",
                })
                count += 1
                if count >= src["max"]: break
            print(f"  {src['name']}: {count}条")
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] {src['name']}: {e}")
    return results
