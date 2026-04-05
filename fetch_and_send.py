"""
agent_daily/fetch_and_send.py  v7
每日AI Agent进展推送
改动说明（v6→v7）：
1. 删除 Reddit 全部相关代码
2. 新增国内知名导师/大厂研究者到 FAMOUS_AUTHORS
3. 新增阿里/千问到 AFFIL_MAP
4. 统一用 extract_arxiv_id() 提取 arxiv ID 作为去重 key
5. 新增 dedup_cross_source()：同一篇论文 HF+arXiv 都有时 arXiv 优先，HF 条目加 📑 标记
6. score_and_rank() 新增 quality 字段（1-5），低于 3 的直接过滤（DeepSeek 水文审核）
7. sent.json 跨天去重基于 arxiv ID，保证每天不重复
"""

import os, smtplib, datetime, time, re, json
import urllib.request, urllib.parse
import feedparser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── 配置 ──────────────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()

SENDER       = os.getenv("EMAIL_SENDER")
QQ_AUTH_CODE = os.getenv("EMAIL_AUTH_CODE")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
RECEIVER     = os.getenv("EMAIL_RECEIVER")

CLASH_PROXY  = "http://127.0.0.1:7897"  # Clash本地HTTP代理，作为发送兜底

MY_FOCUS = (
    "AI Agent, Multi-Agent系统, RAG检索增强生成, LangGraph, "
    "LLM应用开发, 记忆系统, 工具调用, 金融NLP, 叙事仿真"
)

# ── 知名研究者中英对照 ────────────────────────────────────────
FAMOUS_AUTHORS = {
    # 国际顶级
    "Yann LeCun":        "杨立昆",
    "Geoffrey Hinton":   "杰弗里·辛顿",
    "Andrew Ng":         "吴恩达",
    "Andrej Karpathy":   "安德烈·卡帕西",
    "Demis Hassabis":    "德米斯·哈萨比斯",
    "Ilya Sutskever":    "伊利亚·苏茨克维",
    "Sam Altman":        "萨姆·奥特曼",
    "Yoshua Bengio":     "约书亚·本吉奥",
    "Fei-Fei Li":        "李飞飞",
    "Percy Liang":       "梁磊",
    "Chelsea Finn":      "切尔西·芬",
    "Pieter Abbeel":     "彼得·阿比尔",
    "Dario Amodei":      "达里奥·阿莫迪",
    "Harrison Chase":    "哈里森·蔡斯",
    "Jerry Liu":         "刘杰锐",
    "Jason Wei":         "魏杰森",
    "Noam Shazeer":      "诺姆·沙泽尔",
    "Jeff Dean":         "杰夫·迪恩",
    "Quoc Le":           "黎国权",
    "Tom Brown":         "汤姆·布朗",
    "John Schulman":     "约翰·舒尔曼",
    "Alec Radford":      "亚历克·拉德福德",
    # 国内顶级学者（NLP/LLM/Agent方向）
    "Zhiyuan Liu":       "刘知远（清华）",
    "Xipeng Qiu":        "邱锡鹏（复旦）",
    "Ming Zhou":         "周明（澳门大学/MSRA）",
    "Maosong Sun":       "孙茂松（清华）",
    "Jie Tang":          "唐杰（清华，知识图谱/Agent）",
    "Xiangnan He":       "何向南（中科大，推荐系统）",
    "Yue Zhang":         "张岳（西湖大学，NLP）",
    "Shuicheng Yan":     "颜水成（奇虎360/NUS）",
    "Songchun Zhu":      "朱松纯（北大，具身智能）",
    "Zhaohua Pan":       "涂兆鹏（腾讯AI Lab）",
    "Hang Li":           "李航（字节跳动）",
    "Weinan Zhang":      "张伟楠（上交，RL/LLM）",
    "Minlie Huang":      "黄民烈（清华，对话系统）",
    "Wanxiang Che":      "车万翔（哈工大，NLP）",
    "Ting Liu":          "刘挺（哈工大，NLP）",
    "Yuanbin Wu":        "吴远彬",
    # 大厂知名研究员
    "David Luan":        "栾睿（Adept AI）",
    "Shengding Hu":      "胡胜丁（清华/智谱）",
    "An Yang":           "杨安（阿里千问）",
    "Jinze Bai":         "白金泽（阿里千问）",
    "Shuai Bai":         "白帅（阿里千问）",
}

AGENT_KEYWORDS = [
    "agent", "multi-agent", "agentic", "tool use", "tool call",
    "planning", "memory", "rag", "retrieval augmented", "langgraph",
    "mcp", "model context protocol", "autonomous", "workflow",
    "react", "reflexion", "self-refine", "critic", "function call",
    "tool calling", "llm agent", "ai agent", "crewai", "autogen",
    "llamaindex", "langchain", "dify", "coze", "orchestrat",
]

GITHUB_REPOS = [
    ("langchain-ai", "langgraph"),
    ("run-llama",    "llama_index"),
    ("microsoft",    "autogen"),
    ("crewAIInc",    "crewAI"),
    ("langchain-ai", "langchain"),
    ("microsoft",    "semantic-kernel"),
]

BLOG_SOURCES = [
    {"name": "LangChain Blog",           "url": "https://blog.langchain.dev/rss/",          "max": 3},
    {"name": "Papers with Code",          "url": "https://paperswithcode.com/rss.xml",        "max": 4},
    {"name": "Towards Data Science",      "url": "https://towardsdatascience.com/feed",       "max": 3},
    {"name": "DeepLearning.AI The Batch", "url": "https://www.deeplearning.ai/the-batch/rss/","max": 2},
]

# AI产品动态源
PRODUCT_SOURCES = [
    {"name": "Product Hunt (AI)", "url": "https://www.producthunt.com/feed",              "max": 5},
    {"name": "Hacker News",       "url": "https://news.ycombinator.com/rss",              "max": 5},
]

PRODUCT_KEYWORDS = [
    "agent", "ai tool", "ai app", "llm", "gpt", "claude", "gemini",
    "copilot", "assistant", "chatbot", "automation", "workflow",
    "open source", "launch", "release", "new model", "benchmark",
    "deepseek", "qwen", "mistral", "coze", "dify", "cursor",
    "mcp", "rag", "multimodal", "voice ai", "ai coding",
]

BUGFIX_PATTERNS = re.compile(
    r"^(bug\s*fix|hotfix|patch|minor\s*fix|fix:|chore:|docs:|style:|refactor:)",
    re.IGNORECASE
)

# ── 机构映射表 ────────────────────────────────────────────────
AFFIL_MAP = {
    "stanford.edu":    "Stanford University",
    "mit.edu":         "MIT",
    "berkeley.edu":    "UC Berkeley",
    "google.com":      "Google DeepMind",
    "openai.com":      "OpenAI",
    "microsoft.com":   "Microsoft Research",
    "meta.com":        "Meta AI",
    "anthropic.com":   "Anthropic",
    "nvidia.com":      "NVIDIA",
    "amazon.com":      "Amazon AWS AI",
    "apple.com":       "Apple AI",
    # 国内高校
    "tsinghua.edu.cn": "清华大学",
    "pku.edu.cn":      "北京大学",
    "sjtu.edu.cn":     "上海交通大学",
    "fudan.edu.cn":    "复旦大学",
    "zju.edu.cn":      "浙江大学",
    "ustc.edu.cn":     "中科大",
    "hku.hk":          "香港大学",
    "ust.hk":          "香港科技大学",
    "cuhk.edu.hk":     "香港中文大学",
    "nus.edu.sg":      "NUS",
    "ntu.edu.sg":      "NTU",
    # 国内大厂/研究院
    "alibaba-inc.com": "阿里巴巴",
    "aliyun.com":      "阿里云",
    "tongyi.aliyun":   "Qwen Team（阿里通义）",
    "taobao.com":      "阿里巴巴",
    "tencent.com":     "腾讯AI Lab",
    "baidu.com":       "百度研究院",
    "huawei.com":      "华为诺亚方舟",
    "bytedance.com":   "字节跳动",
    "zhipuai.cn":      "智谱AI",
    "minimax.chat":    "MiniMax",
    "stepfun.com":     "阶跃星辰",
    "moonshot.cn":     "月之暗面",
    "deepseek.com":    "DeepSeek",
    # 顶校
    "ox.ac.uk":        "Oxford",
    "cam.ac.uk":       "Cambridge",
    "cmu.edu":         "CMU",
    "cornell.edu":     "Cornell",
    "washington.edu":  "UW",
    "toronto.edu":     "U of Toronto",
}

# ── 工具函数 ──────────────────────────────────────────────────
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


# ── arxiv ID 提取（去重核心） ──────────────────────────────────
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


# ── 跨源去重：HF + arXiv 同一篇，arXiv 优先 ──────────────────
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


# ── DeepSeek API ───────────────────────────────────────────────
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


# ── 打分 + 水文过滤 ───────────────────────────────────────────
def score_and_rank(items: list) -> list:
    """
    用 DeepSeek 对每篇内容打分（relevance 1-10）+ 质量审核（quality 1-5）
    quality < 3 的直接过滤（水文）
    """
    if not DEEPSEEK_KEY or not items:
        for i, item in enumerate(items):
            item["score"] = 5
            item["score_reason"] = ""
            item["rank"] = i + 1
        return items

    BATCH = 15
    all_scores = {}

    for batch_start in range(0, len(items), BATCH):
        batch = items[batch_start: batch_start + BATCH]
        items_text = ""
        for i, item in enumerate(batch):
            items_text += (
                f"[{i}] 标题：{item['title']}\n"
                f"    来源：{item['source']}\n"
                f"    摘要：{item.get('abstract','')[:200]}\n\n"
            )

        prompt = f"""你是AI Agent领域论文质量审核专家，标准极其严格。
我的方向：{MY_FOCUS}

对以下{len(batch)}条内容打两个分：
1. score（1-10）：与Agent/RAG/Multi-Agent的相关度和新颖性
2. quality（1-5）：论文质量，按以下标准严格评分

【quality=1，直接判定为水文，命中任意一条即为1分】
- 标题含"novel framework/comprehensive survey/systematic review"且摘要无具体创新点
- 摘要套路：we propose X + extensive experiments show SOTA，无具体数值/消融实验
- 方法=已有模型A+已有模型B简单拼接，无架构创新
- 场景陈旧：2023年前已被充分研究的任务（如基础文本分类、简单问答）上做微调
- 换皮：把GPT-4/Claude/Qwen包一层Prompt或API，称为"新系统/新框架"
- 摘要读完仍不清楚具体做了什么、解决了什么问题

【quality=2】有工作量但贡献边际，或实验不充分，或创新点过于微小

【quality=3】普通质量，方法清晰，实验基本完整，有一定参考价值

【quality=4】有明确创新点，实验完整，解决了真实问题

【quality=5】顶会水平/知名机构，方法突破，实验扎实，有开源代码或benchmark

同时给出一句话推荐理由（score>=7才写，否则留空）。

只返回JSON，不要其他文字：
[{{"idx":0,"score":8,"quality":4,"reason":"一句话"}}]

内容：
{items_text}"""

        result = deepseek_call(prompt, max_tokens=1000)
        try:
            m = re.search(r"\[.*?\]", result, re.DOTALL)
            if m:
                for s in json.loads(m.group(0)):
                    global_idx = batch_start + s["idx"]
                    all_scores[global_idx] = s
        except Exception as e:
            print(f"  [WARN] 批次{batch_start}打分解析失败: {e}")
        time.sleep(0.5)

    # 赋分 + 过滤水文
    filtered_items = []
    water_count = 0
    for i, item in enumerate(items):
        s = all_scores.get(i, {})
        item["score"]        = s.get("score", 5)
        item["quality"]      = s.get("quality", 3)
        item["score_reason"] = s.get("reason", "")
        # quality < 3 过滤掉
        if item["quality"] < 3:
            water_count += 1
            print(f"  [水文过滤] {item['title'][:50]} (quality={item['quality']})")
            continue
        filtered_items.append(item)

    print(f"  [水文过滤] 共过滤 {water_count} 篇")
    filtered_items.sort(key=lambda x: x.get("score", 0), reverse=True)
    for i, item in enumerate(filtered_items):
        item["rank"] = i + 1

    return filtered_items


# ── 批量翻译 ──────────────────────────────────────────────────
def translate_batch(items: list) -> list:
    if not DEEPSEEK_KEY:
        return items
    to_translate = [
        i for i in items
        if i.get("type") in ("paper", "blog") and not i.get("title_zh")
    ]
    if not to_translate:
        return items
    print(f"  [翻译] 共{len(to_translate)}条...")
    batch_size = 10
    for batch_start in range(0, len(to_translate), batch_size):
        batch = to_translate[batch_start: batch_start + batch_size]
        lines = ""
        for idx, item in enumerate(batch):
            lines += (
                f"[{idx}]\n"
                f"标题：{item['title']}\n"
                f"摘要：{item.get('abstract','')[:600]}\n\n"
            )
        prompt = f"""请将以下{len(batch)}篇论文/文章的标题和摘要翻译成中文。
要求：专业术语保持准确（Agent、RAG、LLM等可保留英文），摘要翻译完整。
严格按JSON格式返回，不要有其他文字：
[
  {{"idx": 0, "title_zh": "中文标题", "abstract_zh": "中文摘要"}}
]

内容：
{lines}"""
        result = deepseek_call(prompt, max_tokens=4000)
        try:
            m = re.search(r"\[.*\]", result, re.DOTALL)
            if m:
                translations = json.loads(m.group(0))
                for t in translations:
                    idx = t.get("idx", -1)
                    if 0 <= idx < len(batch):
                        batch[idx]["title_zh"]    = t.get("title_zh", "")
                        batch[idx]["abstract_zh"] = t.get("abstract_zh", "")
        except Exception as e:
            print(f"  [WARN] 翻译解析失败: {e}")
        time.sleep(0.5)
    return items


# ── 趋势总结 ──────────────────────────────────────────────────
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


# ── 机构抓取 ──────────────────────────────────────────────────
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


# ── arXiv 相关度打分 ──────────────────────────────────────────
KW_WEIGHTS = {
    "multi-agent":            3,
    "agentic":                3,
    "tool use":               3,
    "tool calling":           3,
    "function call":          3,
    "agentic workflow":       3,
    "langgraph":              3,
    "mcp":                    3,
    "model context protocol": 3,
    "agent memory":           3,
    "agent planning":         3,
    "agent":                  2,
    "retrieval augmented":    2,
    "rag":                    2,
    "memory":                 2,
    "planning":               2,
    "orchestrat":             2,
    "autogen":                2,
    "crewai":                 2,
    "llamaindex":             2,
    "langchain":              2,
    "autonomous":             1,
    "workflow":               1,
    "tool":                   1,
}

TOP_VENUE_KEYWORDS = [
    "neurips", "nips", "icml", "iclr", "acl", "emnlp", "naacl",
    "aaai", "ijcai", "cvpr", "iccv", "eccv", "sigkdd", "www",
]

THEORY_ONLY_PATTERNS = [
    r"proof", r"theorem", r"lemma", r"proposition",
    r"converg", r"regret bound", r"sample complexity",
    r"without experiment", r"no experiment",
]

TITLE_MULTIPLIER = 2
MIN_RELEVANCE_SCORE = 3
ARXIV_HOURS = 48


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


# ── 数据源：HuggingFace ───────────────────────────────────────
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


# ── 数据源：arXiv ─────────────────────────────────────────────
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


# ── 数据源：博客 ──────────────────────────────────────────────
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


# ── 数据源：GitHub Release ────────────────────────────────────
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


# ── 数据源：AI产品动态 ────────────────────────────────────────
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


# ── 去重：跨天（sent.json）────────────────────────────────────
SENT_FILE = "sent.json"


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


# ── 生成HTML ──────────────────────────────────────────────────
SOURCE_COLORS = {
    "HuggingFace Daily Papers":   "#FF6B35",
    "Product Hunt (AI)":          "#DA552F",
    "Hacker News":                "#FF6600",
    "GitHub Trending":            "#24292E",
    "arXiv cs.AI":                "#4A90D9",
    "arXiv cs.CL":                "#27AE60",
    "arXiv cs.LG":                "#8B5CF6",
    "LangChain Blog":             "#1C7293",
    "Papers with Code":           "#E84855",
    "Towards Data Science":       "#3A86FF",
    "DeepLearning.AI The Batch":  "#FF006E",
    "GitHub Release":             "#764ba2",
}

SCORE_BADGE = {
    (9,10): ("🔥 必读", "#DC2626"),
    (7, 8): ("⭐ 推荐", "#D97706"),
    (5, 6): ("📌 参考", "#4A90D9"),
    (1, 4): ("💤 一般", "#9CA3AF"),
}

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


# ── 发送邮件 ──────────────────────────────────────────────────
def send_email(html: str, date_str: str, total: int):
    """
    发送逻辑（双重保障）：
    1. 优先 QQ SMTP 直连
    2. 直连失败，用 socks 劫持 socket 走 Clash 代理重试
       （smtplib 不读系统代理，必须用 socks.set_default_proxy 接管）
    """
    import socket
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 AI Agent {date_str} · {total}条"
    msg["From"]    = SENDER
    msg["To"]      = RECEIVER
    msg.attach(MIMEText(html, "html", "utf-8"))
    raw = msg.as_string()

    # ── 方案1：QQ SMTP 直连 ──────────────────────────────────
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=20) as server:
            server.login(SENDER, QQ_AUTH_CODE)
            server.sendmail(SENDER, [RECEIVER], raw)
        print(f"[OK] QQ邮件已发送 → {RECEIVER}")
        return
    except Exception as e:
        print(f"[WARN] QQ SMTP直连失败: {e}，尝试走Clash代理...")

    # ── 方案2：socks劫持socket走Clash代理 ────────────────────
    _orig_socket = socket.socket   # 保存原始socket，发完后还原
    try:
        import socks
        socks.set_default_proxy(socks.HTTP, "127.0.0.1", 7897)
        socket.socket = socks.socksocket
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=20) as server:
            server.login(SENDER, QQ_AUTH_CODE)
            server.sendmail(SENDER, [RECEIVER], raw)
        print(f"[OK] QQ邮件（Clash代理）已发送 → {RECEIVER}")
    except Exception as e:
        print(f"[ERROR] 代理发送也失败: {e}")
        raise
    finally:
        # 务必还原socket，否则后续所有网络请求都走代理
        socket.socket = _orig_socket


# ── 主流程 ────────────────────────────────────────────────────
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
