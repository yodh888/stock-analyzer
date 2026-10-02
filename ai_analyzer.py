"""
AI 解读模块。

AI 只负责解释程序已经计算好的指标，不参与行情和指标计算。
所有请求都经过统一的 OpenAI-compatible 客户端，错误日志不记录 API Key、
Authorization 请求头或原始异常文本。
"""

import logging
import time

import requests

from config import (
    AI_CONNECT_TIMEOUT,
    AI_MAX_RETRIES,
    AI_MODEL,
    AI_PROVIDER,
    AI_READ_TIMEOUT,
    API_BASES,
    DEFAULT_AI_PROVIDER,
    DEFAULT_MODELS,
    MAX_OUTPUT_TOKENS,
)

LOGGER = logging.getLogger(__name__)
RETRY_STATUSES = {429, 500, 502, 503, 504}


def resolve_provider(provider: str | None = None) -> str:
    """解析并校验AI服务商。"""
    candidate = (provider or AI_PROVIDER or DEFAULT_AI_PROVIDER).strip().lower()
    if candidate not in API_BASES:
        raise ValueError("unsupported_provider")
    return candidate


def resolve_model(provider: str, model: str | None = None) -> str:
    """解析模型名称，未指定时使用服务商默认模型。"""
    candidate = (model or AI_MODEL or "").strip()
    return candidate or DEFAULT_MODELS[provider]


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。"""
    cn_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    other = len(text) - cn_chars
    return int(cn_chars / 1.5 + other / 4)


def calculate_cost(input_tokens: int, output_tokens: int, provider: str) -> dict:
    """估算调用成本，价格仅供参考。"""
    prices = {
        "deepseek": {"input": 0.001, "output": 0.002},
        "kimi": {"input": 0.012, "output": 0.012},
        "qwen": {"input": 0.008, "output": 0.008},
        # OpenAI 官方价格按 7.2 汇率粗略换算为人民币。
        "openai": {"input": 0.15 * 7.2, "output": 0.6 * 7.2},
    }
    price = prices.get(provider, {"input": 0.01, "output": 0.02})
    cost = (input_tokens * price["input"] + output_tokens * price["output"]) / 1000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_yuan": round(cost, 4),
        "currency": "CNY",
        "provider": provider,
    }

def build_prompt(stock_name: str, stock_code: str, signal_result: dict, financial: dict) -> tuple:
    """构建 AI 分析 Prompt。"""
    indicator_values = signal_result.get("indicator_values", {})
    support_resistance = signal_result.get("support_resistance", {})

    indicator_summary = (
        f"价格{signal_result['latest_price']}元，涨跌幅{signal_result['pct_change']}%，"
        f"换手率{signal_result['turnover']}%\n"
        f"均线：MA5={indicator_values.get('ma5')} MA10={indicator_values.get('ma10')} "
        f"MA20={indicator_values.get('ma20')} MA60={indicator_values.get('ma60')}\n"
        f"MACD：DIF={indicator_values.get('macd')} DEA={indicator_values.get('macd_signal')} "
        f"柱={indicator_values.get('macd_hist')}\n"
        f"KDJ：K={indicator_values.get('k')} D={indicator_values.get('d')} "
        f"J={indicator_values.get('j')}\n"
        f"RSI6={indicator_values.get('rsi6')} RSI12={indicator_values.get('rsi12')}\n"
        f"布林带：上轨={indicator_values.get('boll_upper')} "
        f"中轨={indicator_values.get('boll_mid')} 下轨={indicator_values.get('boll_lower')}\n"
        f"量比={indicator_values.get('vol_ratio')}\n"
        f"支撑位={support_resistance.get('support')} "
        f"阻力位={support_resistance.get('resistance')}\n"
    )

    signal_lines = [
        f"- {detail['维度']}：{detail['信号']}，{detail['说明']}"
        for detail in signal_result.get("details", [])
    ]
    pattern_lines = [
        f"- {pattern['name']}（{pattern['signal']}）：{pattern['desc']}"
        for pattern in signal_result.get("patterns", [])
    ]

    financial_text = ""
    if financial:
        financial_text = (
            f"PE={financial.get('pe', 'N/A')} PB={financial.get('pb', 'N/A')} "
            f"ROE={financial.get('roe', 'N/A')}% "
            f"营收同比={financial.get('revenue_yoy', 'N/A')}% "
            f"净利同比={financial.get('profit_yoy', 'N/A')}%"
        )

    system_prompt = """你是一位谨慎的A股技术分析助手。
请根据提供的技术指标数据，给出简洁、专业、可解释的分析。
要求：
1. 先给出一句话核心结论（看多/看空/震荡）
2. 分析各指标的共振、背离和数据缺口
3. 给出条件式观察建议和风险失效位，不承诺收益，不替用户决定仓位
4. 提醒主要风险
5. 控制在300字以内，语言精练"""

    user_prompt = f"""股票：{stock_name}({stock_code})

【行情与指标】
{indicator_summary}

【各维度信号】
{chr(10).join(signal_lines)}

【K线形态】
{chr(10).join(pattern_lines)}

【基本面参考】
{financial_text if financial_text else '无'}

【规则系统判断】
{signal_result['suggestion']}（综合得分{signal_result['total_score']}）
操作建议：{signal_result['action']}

请基于以上数据，给出你的分析判断。"""
    return system_prompt, user_prompt


def _build_payload(provider: str, model: str, messages: list[dict], max_tokens: int, temperature: float) -> dict:
    payload = {
        "model": model,
        "messages": messages,
    }
    if provider == "openai" and model.startswith(("o1", "o3", "o4", "gpt-5")):
        payload["max_completion_tokens"] = max_tokens
    else:
        payload["max_tokens"] = max_tokens
        payload["temperature"] = temperature
    return payload


def _request_chat_completion(
    api_key: str,
    provider: str,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
) -> dict:
    """统一请求 OpenAI-compatible Chat Completions 接口。"""
    provider = resolve_provider(provider)
    model = resolve_model(provider, model)
    if not api_key:
        raise ValueError("missing_api_key")

    last_status = None
    for attempt in range(AI_MAX_RETRIES):
        response = None
        try:
            response = requests.post(
                f"{API_BASES[provider]}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=_build_payload(provider, model, messages, max_tokens, temperature),
                timeout=(AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT),
            )
            if response.status_code in RETRY_STATUSES and attempt < AI_MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not data.get("choices"):
                raise ValueError("invalid_response")
            return data
        except requests.RequestException as exc:
            if exc.response is not None:
                last_status = exc.response.status_code
            elif response is not None:
                last_status = response.status_code
            else:
                last_status = None
            retryable = last_status in RETRY_STATUSES or last_status is None
            if retryable and attempt < AI_MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            LOGGER.warning(
                "AI请求失败 provider=%s model=%s error=%s status=%s",
                provider,
                model,
                type(exc).__name__,
                last_status,
            )
            raise
        except ValueError as exc:
            if attempt < AI_MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            LOGGER.warning(
                "AI请求失败 provider=%s model=%s error=%s status=%s",
                provider,
                model,
                type(exc).__name__,
                response.status_code if response is not None else None,
            )
            raise
    raise RuntimeError("ai_request_failed")

def ai_analyze(
    stock_name: str,
    stock_code: str,
    signal_result: dict,
    financial: dict,
    api_key: str,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """调用大模型分析单只股票。"""
    if not api_key:
        return {
            "text": "未配置API Key，无法使用AI分析。",
            "cost": 0,
            "tokens": 0,
            "error": "missing_api_key",
        }

    try:
        provider = resolve_provider(provider)
        model = resolve_model(provider, model)
    except ValueError as exc:
        return {
            "text": "AI服务商配置无效。",
            "cost": 0,
            "tokens": 0,
            "error": type(exc).__name__,
        }

    system_prompt, user_prompt = build_prompt(
        stock_name,
        stock_code,
        signal_result,
        financial,
    )
    input_tokens = estimate_tokens(system_prompt + user_prompt)

    try:
        data = _request_chat_completion(
            api_key,
            provider,
            model,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.3,
        )
        text = data["choices"][0]["message"]["content"]
        actual_output_tokens = data.get("usage", {}).get(
            "completion_tokens",
            MAX_OUTPUT_TOKENS,
        )
        actual_input_tokens = data.get("usage", {}).get("prompt_tokens", input_tokens)
        actual_cost = calculate_cost(actual_input_tokens, actual_output_tokens, provider)

        return {
            "text": text,
            "cost": actual_cost["cost_yuan"],
            "input_tokens": actual_input_tokens,
            "output_tokens": actual_output_tokens,
            "model": model,
            "provider": provider,
        }
    except Exception as exc:
        return {
            "text": "AI调用失败，请查看运行日志。",
            "cost": 0,
            "tokens": 0,
            "error": type(exc).__name__,
        }


def test_ai_connection(
    api_key: str,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """发送最小请求测试AI配置，不打印任何密钥或原始错误文本。"""
    started_at = time.perf_counter()
    try:
        provider = resolve_provider(provider)
        model = resolve_model(provider, model)
    except ValueError as exc:
        return {
            "ok": False,
            "provider": provider or AI_PROVIDER,
            "model": model or "",
            "latency_ms": 0,
            "error": type(exc).__name__,
            "message": "AI服务商配置无效",
        }

    if not api_key:
        return {
            "ok": False,
            "provider": provider,
            "model": model,
            "latency_ms": 0,
            "error": "missing_api_key",
            "message": "未配置AI_API_KEY",
        }

    try:
        data = _request_chat_completion(
            api_key,
            provider,
            model,
            [{"role": "user", "content": "只回复 OK"}],
            max_tokens=8,
            temperature=0,
        )
        content = data["choices"][0]["message"].get("content", "")
        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
            "response_chars": len(content or ""),
            "message": "AI连接成功",
        }
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return {
            "ok": False,
            "provider": provider,
            "model": model,
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
            "error": type(exc).__name__,
            "status_code": status_code,
            "message": "AI连接失败，请检查服务商、模型、Key和额度",
        }
