import re
import time
import json
import urllib.request
import urllib.error

from config.settings import FAMOUS_AUTHORS, AGENT_KEYWORDS, DEEPSEEK_KEY


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    for k, v in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&quot;",'"'),("&#39;","'")]:
        text = text.replace(k, v)
    return re.sub(r"\s+", " ", text).strip()


def http_get(url: str, extra_headers: dict = None, timeout: int = 30, retries: int = 3) -> str:
    headers = {"User-Agent": "Mozilla/5.0 AgentDailyBot/2.0"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = 2 ** attempt * 5  # 10s, 20s, 40s
                print(f"  [http_get] 第{attempt}次失败(429 Rate Limit)，{wait}秒后重试...")
                time.sleep(wait)
            else:
                if attempt < retries:
                    print(f"  [http_get] 第{attempt}次失败({e})，2秒后重试...")
                    time.sleep(2)
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f"  [http_get] 第{attempt}次失败({e})，2秒后重试...")
                time.sleep(2)
    raise last_err


def is_agent_related(title: str, body: str = "") -> bool:
    text = (title + " " + body).lower()
    return any(kw in text for kw in AGENT_KEYWORDS)


def truncate(text: str, n: int) -> str:
    text = clean_html(text)
    return text[:n] + ("..." if len(text) > n else "")


def format_authors(raw_authors: list, max_show: int = 5) -> str:
    names = []
    for a in raw_authors[:max_show]:
        name = a.get("name", "") if isinstance(a, dict) else str(a)
        cn = FAMOUS_AUTHORS.get(name)
        names.append(f"{name}（{cn}）" if cn else name)
    result = ", ".join(names)
    if len(raw_authors) > max_show:
        result += f" 等{len(raw_authors)}人"
    return result


def deepseek_call(prompt: str, max_tokens: int = 1500) -> str:
    if not DEEPSEEK_KEY:
        return ""
    try:
        body = json.dumps({
            "model":      "deepseek-chat",
            "max_tokens": max_tokens,
            "messages":   [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode("utf-8"))
            return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[WARN] DeepSeek API: {e}")
        return ""

# 兼容旧名称
claude_call = deepseek_call
