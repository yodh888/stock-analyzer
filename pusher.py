"""
推送模块 - 将分析结果推送到手机
支持：企业微信机器人（最简单）、Server酱、PushPlus
"""
import requests
import json


def push_to_wecom(webhook: str, title: str, content: str) -> bool:
    """推送到企业微信群机器人"""
    if not webhook:
        return False
    try:
        data = {
            "msgtype": "markdown",
            "markdown": {"content": f"### {title}\n{content}"}
        }
        resp = requests.post(webhook, json=data, timeout=10)
        return resp.json().get("errcode", -1) == 0
    except Exception as e:
        print(f"企业微信推送失败: {e}")
        return False


def push_to_serverchan(sendkey: str, title: str, content: str) -> bool:
    """推送到Server酱（微信公众号推送）"""
    if not sendkey:
        return False
    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            data={"title": title, "desp": content},
            timeout=10
        )
        return resp.json().get("code", -1) == 0
    except Exception as e:
        print(f"Server酱推送失败: {e}")
        return False


def push_to_pushplus(token: str, title: str, content: str) -> bool:
    """推送到PushPlus（微信推送）"""
    if not token:
        return False
    try:
        resp = requests.post(
            "http://www.pushplus.plus/send",
            data={"token": token, "title": title, "content": content},
            timeout=10
        )
        return resp.json().get("code", -1) == 200
    except Exception as e:
        print(f"PushPlus推送失败: {e}")
        return False


def push_result(push_type: str, token: str, stock_name: str, stock_code: str,
                signal_result: dict, ai_text: str = "") -> bool:
    """统一推送入口"""
    title = f"{signal_result['emoji']} {stock_name}({stock_code}) {signal_result['suggestion']}"

    content = f"""
**最新价**: {signal_result['latest_price']}  涨跌幅: {signal_result['pct_change']}%
**操作建议**: {signal_result['action']}
**综合得分**: {signal_result['total_score']}

---
**各维度信号**:
"""
    for d in signal_result["details"]:
        content += f"- {d['维度']}：{d['信号']}\n"

    content += f"\n**支撑阻力**: {signal_result['support_resistance']['desc']}\n"

    if ai_text:
        content += f"\n---\n**AI分析**:\n{ai_text}\n"

    content += "\n---\n⚠️ 以上分析仅供参考，不构成投资建议。"

    if push_type == "wecom":
        return push_to_wecom(token, title, content)
    elif push_type == "serverchan":
        return push_to_serverchan(token, title, content)
    elif push_type == "pushplus":
        return push_to_pushplus(token, title, content)
    return False
