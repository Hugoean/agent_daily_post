import re
import json
import time

from config.settings import DEEPSEEK_KEY
from utils.helpers import deepseek_call


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
