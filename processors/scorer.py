import re
import json
import time

from config.settings import MY_FOCUS, DEEPSEEK_KEY
from utils.helpers import deepseek_call


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
