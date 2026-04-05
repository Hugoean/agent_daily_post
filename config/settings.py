import os
import re
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

# ── arXiv 相关度打分常量 ──────────────────────────────────────
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
ARXIV_HOURS = 72

# ── HTML 渲染常量 ─────────────────────────────────────────────
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
