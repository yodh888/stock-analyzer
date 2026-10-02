"""消息推送模块。"""

import logging
import time

import requests

LOGGER = logging.getLogger(__name__)
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _post_json(url: str, *, json_data: dict) -> dict:
    """发送 JSON 请求并对暂时性错误进行有限重试。"""
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                url,
                json=json_data,
                timeout=(5, 10),
            )
            if response.status_code in RETRY_STATUSES and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_error or RuntimeError("推送请求失败")


def _post_form(url: str, *, form_data: dict) -> dict:
    """发送表单请求并对暂时性错误进行有限重试。"""
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                url,
                data=form_data,
                timeout=(5, 10),
            )
            if response.status_code in RETRY_STATUSES and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_error or RuntimeError("推送请求失败")


def push_to_wecom(webhook: str, title: str, content: str) -> bool:
    """推送到企业微信群机器人。"""
    if not webhook:
        return False
    try:
        result = _post_json(
            webhook,
            json_data={
                "msgtype": "markdown",
                "markdown": {"content": f"### {title}\n{content}"},
            },
        )
        return result.get("errcode", -1) == 0
    except Exception as exc:
        LOGGER.warning("企业微信推送失败: %s", type(exc).__name__)
        return False


def push_to_serverchan(sendkey: str, title: str, content: str) -> bool:
    """推送到 Server酱。"""
    if not sendkey:
        return False
    try:
        result = _post_form(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            form_data={"title": title, "desp": content},
        )
        return result.get("code", -1) == 0
    except Exception as exc:
        # 不能记录原始异常，requests 的异常文本可能包含完整请求 URL。
        LOGGER.warning("Server酱推送失败: %s", type(exc).__name__)
        return False


def push_to_pushplus(token: str, title: str, content: str) -> bool:
    """推送到 PushPlus。"""
    if not token:
        return False
    try:
        result = _post_form(
            "https://www.pushplus.plus/send",
            form_data={"token": token, "title": title, "content": content},
        )
        return result.get("code", -1) == 200
    except Exception as exc:
        LOGGER.warning("PushPlus推送失败: %s", type(exc).__name__)
        return False


def push_result(
    push_type: str,
    token: str,
    stock_name: str,
    stock_code: str,
    signal_result: dict,
    ai_text: str = "",
) -> bool:
    """统一推送入口。"""
    title = (
        f"{signal_result['emoji']} {stock_name}({stock_code}) "
        f"{signal_result['suggestion']}"
    )

    content = f"""
**最新价**: {signal_result['latest_price']}  涨跌幅: {signal_result['pct_change']}%
**操作建议**: {signal_result['action']}
**综合得分**: {signal_result['total_score']}

---
**各维度信号**:
"""
    for detail in signal_result["details"]:
        content += f"- {detail['维度']}：{detail['信号']}\n"

    content += f"\n**支撑阻力**: {signal_result['support_resistance']['desc']}\n"

    if ai_text:
        content += f"\n---\n**AI分析**:\n{ai_text}\n"

    content += "\n---\n⚠️ 以上分析仅供参考，不构成投资建议。"

    if push_type == "wecom":
        return push_to_wecom(token, title, content)
    if push_type == "serverchan":
        return push_to_serverchan(token, title, content)
    if push_type == "pushplus":
        return push_to_pushplus(token, title, content)
    return False
