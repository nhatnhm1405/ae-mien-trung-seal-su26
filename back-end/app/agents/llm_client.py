"""
Wrapper OpenAI-compatible function-calling dùng chung cho Coordinator & Action Agent —
đây là NƠI DUY NHẤT trong toàn bộ đội gọi LLM thật, để dễ kiểm soát chi phí/quota.

Trỏ mặc định vào DeepSeek (API tương thích OpenAI SDK, chỉ khác base_url + tên model).
Đổi provider (Gemini/OpenAI thật/...) chỉ cần sửa OPENAI_BASE_URL + OPENAI_MODEL trong .env,
không cần sửa code ở đây.
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger("llm_client")

_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"
MAX_TOOL_ROUNDS = 6  # chặn loop vô hạn nếu model cứ gọi tool mãi không trả lời cuối


def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY chưa được cấu hình trong llm-test/.env — "
            "Coordinator & Action Agent cần key này để gọi LLM."
        )
    return OpenAI(api_key=api_key, base_url=base_url)


def _model() -> str:
    return os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)


def run_tool_calling_loop(
    system_prompt: str,
    user_message: str,
    tool_schemas: list[dict],
    tool_impls: dict,
) -> dict:
    """Vòng lặp function-calling chuẩn OpenAI Chat Completions API.

    tool_impls: {tên_tool: callable(**kwargs) -> dict}. Mỗi tool được LLM gọi sẽ
    được thực thi thật bằng hàm Python tương ứng, kết quả feed ngược lại cho model
    tới khi model trả về câu trả lời cuối (không còn tool_calls) hoặc hết MAX_TOOL_ROUNDS.

    Trả {"final_text": str, "trace": [{"tool":..., "args":..., "result":...}, ...]}.
    `trace` chính là bằng chứng "dữ liệu IoT nào đã ảnh hưởng quyết định" cho UX.
    """
    client = _client()
    model = _model()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    trace: list[dict] = []

    for round_i in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            return {"final_text": msg.content or "", "trace": trace}

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in tool_calls],
            }
        )

        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                logger.warning("Tool call args không phải JSON hợp lệ: %r", tc.function.arguments)
                args = {}

            impl = tool_impls.get(fn_name)
            if impl is None:
                result = {"error": f"Không có tool tên {fn_name}"}
            else:
                try:
                    result = impl(**args)
                except Exception as e:  # GuardrailRejected, ValueError, v.v. — trả về cho LLM tự xử lý
                    result = {"error": str(e)}

            trace.append({"tool": fn_name, "args": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str, ensure_ascii=False),
                }
            )

    logger.warning("Đạt MAX_TOOL_ROUNDS=%d mà chưa có câu trả lời cuối.", MAX_TOOL_ROUNDS)
    return {
        "final_text": "Đã đạt giới hạn số vòng gọi tool — dừng để tránh loop vô hạn.",
        "trace": trace,
    }
