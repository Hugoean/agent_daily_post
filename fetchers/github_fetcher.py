import datetime
import time
import feedparser

from config.settings import GITHUB_REPOS, BUGFIX_PATTERNS
from utils.helpers import clean_html


def fetch_github_releases() -> list:
    results = []
    cutoff  = datetime.datetime.utcnow() - datetime.timedelta(hours=72)
    for owner, repo in GITHUB_REPOS:
        try:
            feed = feedparser.parse(
                f"https://github.com/{owner}/{repo}/releases.atom"
            )
            for entry in feed.entries[:5]:
                title = entry.get("title","")
                if BUGFIX_PATTERNS.match(title):
                    continue
                pub = entry.get("updated_parsed") or entry.get("published_parsed")
                if pub and datetime.datetime(*pub[:6]) < cutoff:
                    continue
                content = entry.get("content",[{}])
                body    = clean_html(content[0].get("value","") if content else "")
                results.append({
                    "title":    f"{repo}: {title}",
                    "link":     entry.get("link","#"),
                    "abstract": body[:400] or "点击查看更新详情",
                    "authors":  "", "affil": "",
                    "source":   "GitHub Release", "type": "release",
                })
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"[WARN] GitHub {owner}/{repo}: {e}")
    print(f"  GitHub Release: {len(results)}条")
    return results
