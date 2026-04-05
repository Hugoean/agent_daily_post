import datetime

from processors.dedup import load_sent, save_sent, dedup, dedup_cross_source
from processors.scorer import score_and_rank
from processors.translator import translate_batch
from fetchers.hf_fetcher import fetch_hf_papers
from fetchers.arxiv_fetcher import fetch_arxiv, fetch_paper_detail
from fetchers.blog_fetcher import fetch_blogs
from fetchers.github_fetcher import fetch_github_releases
from fetchers.product_fetcher import fetch_products
from render.html_builder import build_html, generate_summary
from sender.email_sender import send_email
from processors.dedup import extract_arxiv_id


def main():
    today    = datetime.date.today()
    date_str = today.strftime("%Y年%m月%d日")
    print(f"[START] {date_str}")

    sent = load_sent()
    print(f"[INFO] 已发送记录: {len(sent)}条")

    all_items = {
        "paper": [], "blog": [], "release": [], "product": []
    }

    # ── 抓取 ──
    hf = fetch_hf_papers()
    print(f"  HuggingFace: {len(hf)}篇")

    arxiv_papers = []
    for cat in ["cs.AI", "cs.CL", "cs.LG"]:
        p = fetch_arxiv(cat)
        print(f"  arXiv {cat}: {len(p)}篇（相关）")
        arxiv_papers.extend(p)

    # ── 跨源去重：同一篇 arXiv 优先，HF 加角标 ──
    combined_papers = hf + arxiv_papers
    combined_papers = dedup_cross_source(combined_papers)
    print(f"  跨源去重后论文: {len(combined_papers)}篇")
    all_items["paper"] = combined_papers

    all_items["blog"]    = fetch_blogs()
    all_items["release"] = fetch_github_releases()
    all_items["product"] = fetch_products()
    print(f"  AI产品动态: {len(all_items['product'])}条")

    # ── 跨天去重（sent.json，基于 arxiv ID） ──
    total_before = sum(len(v) for v in all_items.values())
    for key in list(all_items.keys()):
        all_items[key], skipped = dedup(all_items[key], sent)
        if skipped:
            print(f"  [{key}] 过滤重复: {skipped}条")
    total_after = sum(len(v) for v in all_items.values())
    print(f"[INFO] 去重后: {total_before} → {total_after} 条")

    # ── DeepSeek 打分 + 水文过滤 ──
    print("[INFO] DeepSeek打分 + 水文过滤中...")
    scoreable = all_items["paper"] + all_items["blog"]
    if scoreable:
        scoreable = score_and_rank(scoreable)
        all_items["paper"] = [i for i in scoreable if i["type"] == "paper"]
        all_items["blog"]  = [i for i in scoreable if i["type"] == "blog"]

    # ── 高分论文抓机构信息 ──
    print("[INFO] 抓取高分论文机构信息...")
    for item in all_items["paper"]:
        if item.get("score", 0) >= 8 and not item.get("affil"):
            link = item.get("link", "")
            # 兼容 arxiv.org/abs/xxx 和 huggingface.co/papers/xxx
            arxiv_id = extract_arxiv_id(link)
            if arxiv_id:
                detail = fetch_paper_detail(arxiv_id, abstract=item.get("abstract", ""))
                if detail["affil"]:
                    item["affil"] = detail["affil"]
                print(f"  [{item['title'][:40]}] 机构:{detail['affil']}")

    # ── 翻译高分内容 ──
    print("[INFO] 翻译高分内容（score>=7）...")
    high_score = [
        i for i in (all_items["paper"] + all_items["blog"])
        if i.get("score", 0) >= 7
    ]
    print(f"  需翻译: {len(high_score)}条")
    translate_batch(high_score)

    # ── 生成总结 ──
    print("[INFO] DeepSeek生成总结...")
    all_flat = (all_items["paper"] + all_items["blog"] +
                all_items["release"] + all_items.get("product", []))
    summary = generate_summary(all_flat, date_str)

    total = len(all_flat)
    print(f"[INFO] 合计 {total} 条")

    if total == 0:
        print("[INFO] 今日无新内容，跳过发送")
        return

    html = build_html(all_items, summary, date_str)
    send_email(html, date_str, total)
    save_sent(all_flat)
    print("[DONE]")


if __name__ == "__main__":
    main()
