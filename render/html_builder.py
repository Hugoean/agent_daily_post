from config.settings import SOURCE_COLORS, SCORE_BADGE, MY_FOCUS, DEEPSEEK_KEY
from utils.helpers import deepseek_call


def generate_summary(all_items: list, date_str: str) -> str:
    if not DEEPSEEK_KEY or not all_items:
        return ""
    titles_and_abstracts = "\n".join(
        f"- {item['title']}（{item['source']}）：{item.get('abstract','')[:150]}"
        for item in all_items[:30]
    )
    prompt = f"""你是AI Agent领域的研究助手。
今天（{date_str}）收集到以下内容：

{titles_and_abstracts}

请用中文生成一份简洁的每日总结，包含：
1. 📊 今日趋势（2-3句，指出今天最热门的方向/话题）
2. 🔥 重点关注（列出2-3个最值得关注的内容，一句话说明为什么）
3. 💡 对AI Agent开发者的启示（1-2句实践建议）

语言要求：简洁、有见地、像专家同行之间的交流，不要废话。
总字数控制在200字以内。"""
    return deepseek_call(prompt, max_tokens=600)


def get_score_badge(score: int):
    for (lo, hi), (label, color) in SCORE_BADGE.items():
        if lo <= score <= hi:
            return label, color
    return "📌 参考", "#4A90D9"


def item_card(item: dict) -> str:
    src_color   = SOURCE_COLORS.get(item["source"], "#4A90D9")
    score       = item.get("score", 5)
    title_zh    = item.get("title_zh", "")
    abstract_zh = item.get("abstract_zh", "")
    hf_also     = item.get("hf_also", False)   # arXiv 条目是否在 HF 也有收录

    # 翻译折叠块
    if title_zh or abstract_zh:
        t_title    = f"<b>【{title_zh}】</b><br>" if title_zh else ""
        t_abstract = abstract_zh if abstract_zh else ""
        translate_html = f"""
      <details style="margin:6px 0 8px;">
        <summary style="color:#6366F1;font-size:12px;font-weight:bold;
                        cursor:pointer;user-select:none;list-style:none;
                        padding:5px 10px;background:#EEF2FF;border-radius:6px;
                        display:inline-block;">
          🈯 查看中文翻译
        </summary>
        <div style="background:#F8FAFF;border:1px solid #C7D2FE;border-radius:0 8px 8px 8px;
                    padding:10px 12px;margin-top:4px;font-size:13px;
                    color:#374151;line-height:1.8;">
          {t_title}{t_abstract}
        </div>
      </details>"""
    else:
        translate_html = ""

    reason = item.get("score_reason", "")
    rank   = item.get("rank", "")
    badge_text, badge_color = get_score_badge(score)

    src_badge = (
        f'<span style="background:{src_color};color:white;font-size:10px;'
        f'padding:2px 7px;border-radius:4px;margin-right:4px;">{item["source"]}</span>'
    )
    # HF 同步收录角标
    hf_badge = (
        '<span style="background:#FF6B35;color:white;font-size:10px;'
        'padding:2px 7px;border-radius:4px;margin-right:4px;">📑 HuggingFace同步</span>'
    ) if hf_also else ""

    score_badge = (
        f'<span style="background:{badge_color};color:white;font-size:10px;'
        f'padding:2px 7px;border-radius:4px;margin-right:4px;">'
        f'{badge_text} {score}/10</span>'
    )
    rank_badge = (
        f'<span style="background:#F3F4F6;color:#374151;font-size:10px;'
        f'padding:2px 6px;border-radius:4px;">#{rank}</span>'
    ) if rank else ""

    upvotes    = item.get("upvotes", 0)
    upvote_str = f" · 👍 {upvotes}" if upvotes > 0 else ""
    author_html = (
        f'<div style="color:#888;font-size:11px;margin:3px 0 4px;">✍️ {item["authors"]}{upvote_str}</div>'
    ) if item.get("authors") else (
        f'<div style="color:#888;font-size:11px;margin:3px 0 4px;">{upvote_str}</div>'
        if upvote_str else ""
    )

    citations  = item.get("citations", 0)
    cite_str   = f" · 📊 引用{citations}次" if citations > 0 else ""
    if item.get("affil"):
        # affil_guessed=True 说明是 DeepSeek 推测，用 🤖 角标弱化显示
        if item.get("affil_guessed"):
            affil_icon  = "🤖 推测机构："
            affil_color = "#a0aec0"
        else:
            affil_icon  = "🏛️"
            affil_color = "#aaa"
        affil_html = (
            f'<div style="color:{affil_color};font-size:11px;margin-bottom:4px;">'
            f'{affil_icon} {item["affil"]}{cite_str}</div>'
        )
    else:
        affil_html = (
            f'<div style="color:#aaa;font-size:11px;margin-bottom:4px;">{cite_str}</div>'
            if cite_str else ""
        )

    reason_html = (
        f'<div style="background:#FEF3C7;border-left:3px solid #F59E0B;'
        f'padding:5px 8px;border-radius:0 4px 4px 0;font-size:12px;color:#92400E;'
        f'margin:6px 0;">💡 优先理由：{reason}</div>'
    ) if reason else ""

    abstract = item.get("abstract","")

    return f"""
    <div style="background:#fff;border-radius:10px;padding:14px;
                margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,0.07);">
      <div style="margin-bottom:7px;display:flex;flex-wrap:wrap;gap:4px;align-items:center;">
        {rank_badge}{src_badge}{hf_badge}{score_badge}
      </div>
      <a href="{item['link']}" style="color:#111;text-decoration:none;
         font-size:15px;font-weight:700;line-height:1.4;display:block;margin-bottom:5px;">
        {item['title']}
      </a>
      {author_html}{affil_html}{reason_html}
      <p style="color:#444;font-size:13px;line-height:1.8;margin:6px 0 8px;
                white-space:pre-wrap;">{abstract}</p>
      {translate_html}
      <a href="{item['link']}" style="color:{src_color};font-size:12px;
         font-weight:bold;text-decoration:none;">阅读原文 →</a>
    </div>"""


def section_block(emoji: str, title: str, items: list) -> str:
    if not items:
        return ""
    cards = "".join(item_card(i) for i in items)
    return f"""
    <div style="font-size:12px;color:#888;font-weight:bold;
                letter-spacing:1px;margin:18px 0 8px;">{emoji} {title}（{len(items)}条）</div>
    {cards}"""


def summary_block(summary_text: str) -> str:
    if not summary_text:
        return ""
    html_text = summary_text.replace("\n", "<br>")
    return f"""
    <div style="background:linear-gradient(135deg,#EEF2FF,#F5F3FF);
                border-radius:12px;padding:16px;margin-bottom:14px;
                border:1px solid #C7D2FE;">
      <div style="font-size:13px;font-weight:bold;color:#4338CA;margin-bottom:8px;">
        🧠 今日AI Agent趋势分析
      </div>
      <div style="font-size:13px;color:#374151;line-height:1.8;">
        {html_text}
      </div>
    </div>"""


def build_html(all_items: dict, summary: str, date_str: str) -> str:
    papers    = all_items.get("paper", [])
    blogs     = all_items.get("blog", [])
    releases  = all_items.get("release", [])
    products  = all_items.get("product", [])
    total     = sum(len(v) for v in all_items.values())

    body = summary_block(summary)
    body += section_block("📄", "最新论文", papers)
    body += section_block("📝", "技术博客", blogs)
    body += section_block("🚀", "框架更新", releases)
    body += section_block("🛠️", "AI产品动态", products)

    if total == 0:
        body = '<div style="text-align:center;padding:40px;color:#aaa;">今日暂无新内容</div>'

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f0f2f5;
             font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;">
<div style="max-width:620px;margin:0 auto;padding:12px;">

  <div style="background:linear-gradient(135deg,#667eea,#764ba2);
              border-radius:14px;padding:22px;margin-bottom:14px;text-align:center;">
    <div style="color:white;font-size:22px;font-weight:800;margin-bottom:5px;">
      🤖 AI Agent 每日进展
    </div>
    <div style="color:rgba(255,255,255,0.85);font-size:13px;">
      {date_str} &nbsp;·&nbsp; 共 {total} 条更新
    </div>
  </div>

  {body}

  <div style="text-align:center;padding:14px 0;color:#bbb;font-size:11px;line-height:2;">
    HuggingFace · arXiv cs.AI/CL/LG · LangChain Blog<br>
    Papers with Code · GitHub Release · Product Hunt · Hacker News
  </div>
</div>
</body>
</html>"""
