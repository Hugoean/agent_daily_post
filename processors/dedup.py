import os
import re
import json
import datetime

SENT_FILE = "sent.json"


def extract_arxiv_id(url: str) -> str:
    """
    从任意 URL 中提取 arxiv ID（如 2501.01234 或 2501.01234v2）
    支持：
      https://arxiv.org/abs/2501.01234
      https://huggingface.co/papers/2501.01234
      https://arxiv.org/pdf/2501.01234v2
    没有 arxiv ID 则返回空字符串
    """
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", url)
    return m.group(1) if m else ""


def make_key(item: dict) -> str:
    """
    生成唯一 key：
    1. 优先用 arxiv ID（保证 HF 和 arXiv 同一篇用同一个 key）
    2. 没有 arxiv ID 则用 URL 路径
    3. 都没有则用标题前 50 字符
    """
    link = item.get("link", "")
    arxiv_id = extract_arxiv_id(link)
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    if link and link != "#":
        return re.sub(r"\?.*$", "", link).strip("/")
    return item.get("title", "")[:50]


def dedup_cross_source(papers: list) -> list:
    """
    同一篇论文在 HF 和 arXiv 都出现时：
    - arXiv 条目保留
    - HF 条目打上 📑 HuggingFace 同步收录 角标，然后丢弃
    返回去重后的列表，arXiv 条目带 hf_also=True 标记（用于渲染角标）
    """
    arxiv_ids_from_arxiv = {}   # arxiv_id -> item (来源是 arXiv 的)
    hf_items = []
    other_items = []

    for item in papers:
        src = item.get("source", "")
        link = item.get("link", "")
        aid = extract_arxiv_id(link)

        if "arXiv" in src and aid:
            arxiv_ids_from_arxiv[aid] = item
        elif "HuggingFace" in src:
            hf_items.append((aid, item))
        else:
            other_items.append(item)

    # 处理 HF 条目
    for aid, hf_item in hf_items:
        if aid and aid in arxiv_ids_from_arxiv:
            # arXiv 已有，给 arXiv 条目加标记，HF 条目丢弃
            arxiv_ids_from_arxiv[aid]["hf_also"] = True
        else:
            # arXiv 没有，保留 HF 条目
            other_items.append(hf_item)

    result = list(arxiv_ids_from_arxiv.values()) + other_items
    return result


def load_sent() -> set:
    if not os.path.exists(SENT_FILE):
        return set()
    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        return set(
            v for v in data.get("sent", [])
            if data.get("dates", {}).get(v, "9999") >= cutoff
        )
    except:
        return set()


def save_sent(items: list):
    existing = {}
    if os.path.exists(SENT_FILE):
        try:
            with open(SENT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            existing = {}

    sent_list  = existing.get("sent", [])
    dates_dict = existing.get("dates", {})
    today_str  = datetime.date.today().isoformat()

    for item in items:
        key = make_key(item)
        if key not in sent_list:
            sent_list.append(key)
        dates_dict[key] = today_str

    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    sent_list  = [k for k in sent_list  if dates_dict.get(k, "9999") >= cutoff]
    dates_dict = {k: v for k, v in dates_dict.items() if v >= cutoff}

    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump({"sent": sent_list, "dates": dates_dict}, f, ensure_ascii=False, indent=2)


def dedup(items: list, sent: set) -> tuple:
    new_items = []
    skipped   = 0
    for item in items:
        key = make_key(item)
        if key in sent:
            skipped += 1
        else:
            new_items.append(item)
    return new_items, skipped
