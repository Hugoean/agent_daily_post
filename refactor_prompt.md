# AgentDaily 重构任务 Prompt

## 背景

当前项目 `fetch_and_send.py` 是一个 800+ 行的单文件脚本，所有功能（抓取、打分、翻译、去重、HTML生成、发送）全部堆在一起。

**重构目标：拆分为模块化结构，功能和行为完全不变，不能改任何业务逻辑。**

---

## 目标目录结构

重构完成后的目录结构如下，严格按照这个来：

```
agent_daily/
├── config/
│   └── settings.py          # 所有常量和环境变量（FAMOUS_AUTHORS, AFFIL_MAP, AGENT_KEYWORDS等）
├── fetchers/
│   ├── __init__.py
│   ├── hf_fetcher.py        # fetch_hf_papers()
│   ├── arxiv_fetcher.py     # fetch_arxiv(), relevance_score(), KW_WEIGHTS等常量
│   ├── blog_fetcher.py      # fetch_blogs()
│   ├── github_fetcher.py    # fetch_github_releases()
│   └── product_fetcher.py   # fetch_products()
├── processors/
│   ├── __init__.py
│   ├── dedup.py             # dedup(), dedup_cross_source(), load_sent(), save_sent(), make_key(), extract_arxiv_id()
│   ├── scorer.py            # score_and_rank()
│   └── translator.py        # translate_batch()
├── render/
│   ├── __init__.py
│   └── html_builder.py      # build_html(), item_card(), section_block(), summary_block(), generate_summary()
├── sender/
│   ├── __init__.py
│   └── email_sender.py      # send_email()
├── utils/
│   ├── __init__.py
│   └── helpers.py           # clean_html(), http_get(), is_agent_related(), truncate(), format_authors(), deepseek_call()
├── main.py                  # main()函数，只负责调用各模块，不含业务逻辑
├── sent.json                # 跨天去重记录（保留原文件）
├── requirements.txt         # 不变
├── run.sh                   # 不变
├── test.py                  # 不变
├── test_basic.py            # 不变
├── .env                     # 不变（本地用）
├── .env.example             # 新增（见下方内容）
├── .gitignore               # 更新（见下方内容）
├── README.md                # 不变
└── .github/
    └── workflows/
        └── daily.yml        # 不变，但入口改为 python main.py
```

---

## 重构规则（必须严格遵守）

### 规则1：功能零改动
- 所有函数的逻辑、参数、返回值完全不变
- 只是把函数从一个文件挪到对应模块文件里
- 不能优化、不能简化、不能重写任何业务代码

### 规则2：常量归属
- `FAMOUS_AUTHORS`, `AFFIL_MAP`, `MY_FOCUS`, `SENDER`, `QQ_AUTH_CODE`, `DEEPSEEK_KEY`, `RECEIVER`, `CLASH_PROXY` → `config/settings.py`
- `AGENT_KEYWORDS`, `BLOG_SOURCES`, `PRODUCT_SOURCES`, `GITHUB_REPOS`, `PRODUCT_KEYWORDS`, `BUGFIX_PATTERNS` → `config/settings.py`
- `KW_WEIGHTS`, `TOP_VENUE_KEYWORDS`, `THEORY_ONLY_PATTERNS`, `TITLE_MULTIPLIER`, `MIN_RELEVANCE_SCORE`, `ARXIV_HOURS` → `config/settings.py`
- `SOURCE_COLORS`, `SCORE_BADGE` → `config/settings.py`
- `SENT_FILE` → `processors/dedup.py`
- `HF_HOSTS` → `fetchers/hf_fetcher.py`

### 规则3：import规范
- 每个模块从 `config.settings` import 需要的常量
- 每个模块从 `utils.helpers` import 工具函数
- `main.py` 从各模块 import 函数，只写主流程

### 规则4：__init__.py
- 所有包目录都要有 `__init__.py`（可以是空文件）

### 规则5：入口
- `main.py` 是唯一入口，`run.sh` 改为 `python main.py`
- `main.py` 里只有 `main()` 函数的调用逻辑，不含任何业务实现

---

## 需要新增的文件

### .env.example
```
# AgentDaily 环境变量配置模板
# 复制本文件为 .env，填入真实值，不要将 .env 提交到 Git

EMAIL_SENDER=your_qq@qq.com
EMAIL_AUTH_CODE=your_qq_auth_code
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_RECEIVER=receiver@example.com
```

### .gitignore（更新）
```
.env
__pycache__/
*.py[cod]
*.pyo
venv/
env/
.venv/
.vscode/
.idea/
.DS_Store
*.log
```

---

## 验收标准

重构完成后，运行以下命令验证：

```bash
# 1. 语法检查所有文件
python -m py_compile main.py
python -m py_compile config/settings.py
python -m py_compile utils/helpers.py
python -m py_compile fetchers/hf_fetcher.py
python -m py_compile fetchers/arxiv_fetcher.py
python -m py_compile fetchers/blog_fetcher.py
python -m py_compile fetchers/github_fetcher.py
python -m py_compile fetchers/product_fetcher.py
python -m py_compile processors/dedup.py
python -m py_compile processors/scorer.py
python -m py_compile processors/translator.py
python -m py_compile render/html_builder.py
python -m py_compile sender/email_sender.py

# 2. import检查
python -c "from config.settings import DEEPSEEK_KEY, FAMOUS_AUTHORS, AFFIL_MAP"
python -c "from utils.helpers import clean_html, http_get, deepseek_call"
python -c "from fetchers.hf_fetcher import fetch_hf_papers"
python -c "from fetchers.arxiv_fetcher import fetch_arxiv"
python -c "from processors.dedup import load_sent, save_sent, dedup"
python -c "from processors.scorer import score_and_rank"
python -c "from render.html_builder import build_html"
python -c "from sender.email_sender import send_email"

# 3. 主流程dry run（不真实发送）
python -c "import main; print('main.py import OK')"
```

所有命令无报错即为重构成功。

---

## 注意事项

1. `claude_call = deepseek_call` 这个别名也要保留在 `utils/helpers.py` 里
2. `fetch_paper_detail()` 函数放在 `fetchers/arxiv_fetcher.py`
3. `get_score_badge()` 函数放在 `render/html_builder.py`
4. 原始 `fetch_and_send.py` 保留，不要删除（作为备份对比）
5. `sent.json` 不要动
