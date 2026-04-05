import re
import json
import datetime
import time
import urllib.parse
import feedparser

from config.settings import (
    KW_WEIGHTS, TOP_VENUE_KEYWORDS, THEORY_ONLY_PATTERNS,
    TITLE_MULTIPLIER, MIN_RELEVANCE_SCORE, ARXIV_HOURS,
    AFFIL_MAP, DEEPSEEK_KEY,
)
from utils.helpers import http_get, format_authors, clean_html, deepseek_call


def relevance_score(title: str, abstract: str) -> int:
    title_lower    = title.lower()
    abstract_lower = abstract.lower()
    full_text      = title_lower + " " + abstract_lower

    theory_hits = sum(1 for pat in THEORY_ONLY_PATTERNS if re.search(pat, full_text))
    has_experiment = any(
        kw in full_text for kw in
        ["experiment", "evaluation", "benchmark", "dataset",
         "implement", "code", "system", "deploy", "demo"]
    )
    if theory_hits >= 2 and not has_experiment:
        return 0

    score = 0
    for kw, weight in KW_WEIGHTS.items():
        if kw in title_lower:
            score += weight * TITLE_MULTIPLIER
        elif kw in abstract_lower:
            score += weight

    for venue in TOP_VENUE_KEYWORDS:
        if venue in full_text:
            score += 2
            break
    return score


def fetch_paper_detail(arxiv_id: str, title: str = "", abstract: str = "") -> dict:
    """
    通过解析 arXiv HTML 页面提取机构信息。
    arXiv 从2023年起为大多数论文生成 HTML 版本，机构信息在 ltx_authors 块内。
    相比 API/Email 方案，这是目前最可靠的实时方案（无需第三方，当天论文即可用）。

    HTML 结构示例：
      <div class="ltx_authors">
        <span class="ltx_creator ltx_role_author">
          <span class="ltx_personname">Author Name</span>
          <span class="ltx_author_notes">
            <span class="ltx_contact ltx_role_affiliation">MIT CSAIL</span>
          </span>
        </span>
      </div>

    fallback：若 HTML 页面不存在（部分老论文），退回摘要关键词匹配。
    """
    result = {"affil": "", "citations": 0}
    clean_id = re.sub(r"v\d+$", "", arxiv_id.strip())  # 去掉版本号如 v2

    # ── 方案1：解析 arXiv HTML 页面 ──────────────────────────
    try:
        html_url = f"https://arxiv.org/html/{clean_id}"
        html = http_get(html_url)

        affils = []

        # 优先：抓 ltx_role_affiliation 标签（最准确）
        role_affils = re.findall(
            r'class="ltx_contact ltx_role_affiliation"[^>]*>(.*?)</span>',
            html, re.DOTALL
        )
        for raw in role_affils:
            text = clean_html(raw).strip()
            if text and len(text) > 3:
                affils.append(text)

        # 备选：抓 ltx_author_notes 内的文本
        if not affils:
            note_blocks = re.findall(
                r'class="ltx_author_notes"[^>]*>(.*?)</span>\s*</span>',
                html, re.DOTALL
            )
            for block in note_blocks:
                text = clean_html(block).strip()
                if text and len(text) > 3:
                    affils.append(text)

        if affils:
            # 去重 + 只取前3个机构
            seen = []
            for a in affils:
                if a not in seen:
                    seen.append(a)
            # 用 AFFIL_MAP 标准化（能匹配到就换成标准名）
            normalized = []
            for raw_affil in seen[:3]:
                matched = False
                for domain_key, std_name in AFFIL_MAP.items():
                    # 去掉.edu/.com等后缀，取核心词匹配
                    core = domain_key.split(".")[0].lower()
                    if core in raw_affil.lower():
                        if std_name not in normalized:
                            normalized.append(std_name)
                        matched = True
                        break
                if not matched:
                    normalized.append(raw_affil[:40])  # 截断过长的原始机构名
            result["affil"] = "; ".join(normalized[:3])
            print(f"  [机构-HTML] {clean_id}: {result['affil']}")
            return result

    except Exception as e:
        print(f"  [机构-HTML] {clean_id} HTML页面不可用: {e}")

    # ── 方案2（fallback）：摘要关键词匹配 ───────────────────
    if abstract:
        found = []
        for domain_key, std_name in AFFIL_MAP.items():
            core = domain_key.split(".")[0]
            if core.lower() in abstract.lower() and std_name not in found:
                found.append(std_name)
        if found:
            result["affil"] = "; ".join(found[:2])
            print(f"  [机构-摘要fallback] {clean_id}: {result['affil']}")
            return result

    # ── 方案3（fallback）：DeepSeek 推测 ─────────────────────
    # 注意：这是推测结果，准确率约50%，item 里会附加 affil_guessed=True 标记
    # 渲染时显示 🤖 推测 角标加以区分，避免误导
    if title and DEEPSEEK_KEY:
        try:
            prompt = (
                f"根据以下论文的标题和作者名，推测第一作者最可能来自哪个机构/大学/公司。\n"
                f"只返回机构名称，不要解释，不确定就返回空字符串。\n"
                f"标题：{title}\n"
                f"摘要前100字：{abstract[:100]}\n"
                f"只返回JSON：{{\"affil\": \"机构名或空字符串\"}}"
            )
            resp = deepseek_call(prompt, max_tokens=80)
            m = re.search(r'\{.*?\}', resp, re.DOTALL)
            if m:
                guessed = json.loads(m.group(0)).get("affil", "").strip()
                if guessed and len(guessed) > 2:
                    result["affil"]         = guessed
                    result["affil_guessed"] = True   # 标记为推测
                    print(f"  [机构-DeepSeek推测] {clean_id}: {guessed}")
        except Exception as e:
            print(f"  [机构-DeepSeek推测] 失败: {e}")

    return result


def fetch_arxiv(category: str, fetch_n: int = 30) -> list:
    results = []
    try:
        kw_query = " OR ".join(
            f'ti:"{kw}"' for kw in
            ["agent","multi-agent","agentic","tool use","memory",
             "planning","retrieval augmented","tool calling","agentic workflow"]
        )
        query = urllib.parse.quote(f"cat:{category} AND ({kw_query})")
        url   = (f"https://export.arxiv.org/api/query?"
                 f"search_query={query}&sortBy=submittedDate"
                 f"&sortOrder=descending&max_results={fetch_n}")
        feed  = feedparser.parse(http_get(url))

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=ARXIV_HOURS)
        skipped_time  = 0
        skipped_score = 0

        for entry in feed.entries:
            title    = entry.get("title","").replace("\n"," ").strip()
            abstract = entry.get("summary","").replace("\n"," ").strip()

            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if pub:
                pub_dt = datetime.datetime(*pub[:6])
                if pub_dt < cutoff:
                    skipped_time += 1
                    continue

            score = relevance_score(title, abstract)
            if score < MIN_RELEVANCE_SCORE:
                skipped_score += 1
                continue

            authors = entry.get("authors", [])
            link    = entry.get("link","#")
            results.append({
                "title":      title,
                "link":       link,
                "abstract":   abstract,
                "authors":    format_authors(authors),
                "affil":      "",
                "source":     f"arXiv {category}",
                "type":       "paper",
                "_relevance": score,
            })

        results.sort(key=lambda x: x["_relevance"], reverse=True)
        print(
            f"    {category}: 候选{len(feed.entries)}篇 "
            f"→ 时间过滤{skipped_time} 相关度过滤{skipped_score} "
            f"→ 保留{len(results)}篇"
        )
        time.sleep(3)
    except Exception as e:
        print(f"[ERROR] arXiv {category}: {e}")
    return results
