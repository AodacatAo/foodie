"""LLM 提炼服务（DeepSeek，OpenAI 兼容协议）。

输入：小红书笔记原文（正文 + OCR 文本）
输出：RefinedRecipe（Pydantic 校验），任何失败返回 None（由管线降级为规则提取）。
"""
import json

import httpx

from ..config import settings
from ..schemas import RefinedRecipe

SYSTEM_PROMPT = """你是专业的菜谱结构化助手。用户会给你一段小红书菜谱笔记的原文，可能包含图片OCR识别出的文字（格式为"[图片N]"标记块，图片顺序即步骤顺序），请把它提炼为严格的JSON对象，字段如下：
{
  "title": "菜名",
  "ingredients": [{"name": "食材名", "amount": "用量，如300g/两勺", "note": "备注，如：提前腌30分钟；没有则null"}],
  "steps": [{"order": 1, "title": "步骤小标题，没有则null", "description": "该步骤的详细做法"}],
  "cooking_time_min": 烹饪总时长（分钟，数字），原文没有则null,
  "servings": "几人份，如：2人份；没有则null",
  "tags": ["1-3个标签，如：家常菜/快手菜/川菜"],
  "notes": "原文中有但无法归入以上字段的关键信息（小贴士、注意事项等），没有则为空字符串"
}
要求：
1. 只输出JSON，不要输出任何其他文字（不要markdown代码块）。
2. 步骤尽量保留原文的调味料用量和操作细节，不要丢失关键信息。
3. 原文没有的信息一律用null或空值，绝对不要编造。
4. 若原文是图片菜谱，OCR文字可能不连贯，请尽量根据常识整理步骤顺序。
5. 如果某一步骤明确对应某张图片（例如该步骤做法主要来自"[图片N]"的内容），请在该步骤description末尾追加标注"[图N]"，一个步骤最多标注一张图；不确定就不要标注。"""


async def refine_recipe(text: str) -> RefinedRecipe | None:
    """调用 DeepSeek 提炼菜谱结构；失败返回 None。"""
    if not settings.llm_ready:
        return None
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text[:12000]},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 3000,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            refined = RefinedRecipe.model_validate(data)
            if not refined.steps:
                return None
            return refined
    except Exception:
        return None
