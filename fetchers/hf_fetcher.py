import json
import datetime
import time
import feedparser

from utils.helpers import http_get, is_agent_related, clean_html, format_authors

# HF 域名优先级：先试镜像，再试官方
HF_HOSTS = [
    "https://hf-mirror.com",
    "https://huggingface.co",
]


def fetch_hf_papers() -> list:
    results = []
    today = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    # 对每个 host 最多重试3次，成功立即返回
    for host in HF_HOSTS:
        for attempt in range(1, 4):
            try:
                data = json.loads(http_get(
                    f"{host}/api/daily_papers?date={today}",
                    extra_headers={"Accept": "application/json"},
                ))
                for item in data:
                    paper    = item.get("paper", {})
                    title    = paper.get("title", "")
                    abstract = paper.get("summary", "")
                    if not is_agent_related(title, abstract):
                        continue
                    authors = paper.get("authors", [])
                    results.append({
                        "title":    title,
                        "link":     f"https://huggingface.co/papers/{paper.get('id','')}",
                        "abstract": clean_html(abstract),
                        "authors":  format_authors(authors),
                        "affil":    "",
                        "source":   "HuggingFace Daily Papers",
                        "type":     "paper",
                    })
                    if len(results) >= 10:
                        break
                print(f"  [HF] {host} 成功，获取{len(results)}篇")
                return results   # 成功直接返回，不继续尝试其他host

            except Exception as e:
                wait = attempt * 3
                print(f"  [WARN] HF {host} 第{attempt}次失败: {e}，等待{wait}s...")
                time.sleep(wait)

    # 所有host都失败，走feedparser备用
    print("  [WARN] HF API全部失败，尝试feedparser备用...")
    try:
        feed = feedparser.parse("https://jamesg.blog/hf-papers.xml")
        for entry in feed.entries[:15]:
            title = entry.get("title", "")
            body  = clean_html(entry.get("summary", ""))
            if not is_agent_related(title, body):
                continue
            results.append({
                "title": title, "link": entry.get("link","#"),
                "abstract": body, "authors": "", "affil": "",
                "source": "HuggingFace Daily Papers", "type": "paper",
            })
            if len(results) >= 10:
                break
    except Exception as e2:
        print(f"  [ERROR] HF备用也失败: {e2}")
    return results
