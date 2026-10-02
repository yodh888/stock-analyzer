"""
AI解读模块 - 使用大模型对技术指标进行自然语言解读
成本控制：使用短prompt、限制输出token、可切换开关
"""
import json
import requests
from config import AI_PROVIDER, API_BASES, DEFAULT_MODELS, MAX_OUTPUT_TOKENS


def estimate_tokens(text: str) -> int:
    """粗略估算token数（中文约1.5字/token，英文约4字符/token）"""
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - cn_chars
    return int(cn_chars / 1.5 + other / 4)


def calculate_cost(input_tokens: int, output_tokens: int, provider: str) -> dict:
    """
    估算本次调用成本（元）
    价格为各模型2024年大致价格，仅作参考
    """
    prices = {
        "deepseek": {"input": 0.001, "output": 0.002},      # deepseek-chat: 1元/百万输入, 2元/百万输出
        "kimi": {"input": 0.012, "output": 0.012},           # moonshot-v1-8k: 12元/百万
        "qwen": {"input": 0.008, "output": 0.008},           # qwen-turbo: 8元/百万
        "openai": {"input": 0.15, "output": 0.6},            # gpt-4o-mini: $0.15/$0.6 per 1M
    }
    p = prices.get(provider, {"input": 0.01, "output": 0.02})
    cost = (input_tokens * p["input"] + output_tokens * p["output"]) / 1000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_yuan": round(cost, 4),
        "provider": provider
    }


def build_prompt(stock_name: str, stock_code: str, signal_result: dict, financial: dict) -> tuple:
    """
    构建AI分析prompt
    返回 (system_prompt, user_prompt)
    优化：精简输入，只传关键数据，控制token成本
    """
    iv = signal_result.get("indicator_values", {})
    sr = signal_result.get("support_resistance", {})

    # 精简版指标摘要（控制token）
    indicator_summary = (
        f"价格{signal_result['latest_price']}元，涨跌幅{signal_result['pct_change']}%，换手率{signal_result['turnover']}%\n"
        f"均线：MA5={iv.get('ma5')} MA10={iv.get('ma10')} MA20={iv.get('ma20')} MA60={iv.get('ma60')}\n"
        f"MACD：DIF={iv.get('macd')} DEA={iv.get('macd_signal')} 柱={iv.get('macd_hist')}\n"
        f"KDJ：K={iv.get('k')} D={iv.get('d')} J={iv.get('j')}\n"
        f"RSI6={iv.get('rsi6')} RSI12={iv.get('rsi12')}\n"
        f"布林带：上轨={iv.get('boll_upper')} 中轨={iv.get('boll_mid')} 下轨={iv.get('boll_lower')}\n"
        f"量比={iv.get('vol_ratio')}\n"
        f"支撑位={sr.get('support')} 阻力位={sr.get('resistance')}\n"
    )

    # 各维度信号
    signal_lines = []
    for d in signal_result.get("details", []):
        signal_lines.append(f"- {d['维度']}：{d['信号']}，{d['说明']}")

    # K线形态
    pattern_lines = []
    for p in signal_result.get("patterns", []):
        pattern_lines.append(f"- {p['name']}（{p['signal']}）：{p['desc']}")

    # 基本面（轻量）
    fin_text = ""
    if financial:
        fin_text = (
            f"PE={financial.get('pe', 'N/A')} PB={financial.get('pb', 'N/A')} "
            f"ROE={financial.get('roe', 'N/A')}% "
            f"营收同比={financial.get('revenue_yoy', 'N/A')}% "
            f"净利同比={financial.get('profit_yoy', 'N/A')}%"
        )

    system_prompt = """你是一位资深A股短线分析师，擅长技术面分析。
请根据提供的技术指标数据，给出简洁、专业、可操作的分析。
要求：
1. 先给出一句话核心结论（看多/看空/震荡）
2. 分析各指标的共振或背离情况
3. 给出具体操作建议（是否买入、仓位、止损位）
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
{fin_text if fin_text else '无'}

【规则系统判断】
{signal_result['suggestion']}（综合得分{signal_result['total_score']}）
操作建议：{signal_result['action']}

请基于以上数据，给出你的分析判断。"""

    return system_prompt, user_prompt


def ai_analyze(stock_name: str, stock_code: str, signal_result: dict,
               financial: dict, api_key: str, provider: str = None,
               model: str = None) -> dict:
    """
    调用AI大模型进行分析
    返回: {text, cost, tokens}
    """
    if not api_key:
        return {"text": "未配置API Key，无法使用AI分析。", "cost": 0, "tokens": 0}

    provider = provider or AI_PROVIDER
    model = model or DEFAULT_MODELS.get(provider, "deepseek-chat")
    base_url = API_BASES.get(provider)

    if not base_url:
        return {"text": f"不支持的服务商: {provider}", "cost": 0, "tokens": 0}

    system_prompt, user_prompt = build_prompt(stock_name, stock_code, signal_result, financial)

    # 估算成本
    input_tokens = estimate_tokens(system_prompt + user_prompt)
    cost_info = calculate_cost(input_tokens, MAX_OUTPUT_TOKENS, provider)

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": MAX_OUTPUT_TOKENS,
                "temperature": 0.3,
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        actual_output_tokens = data.get("usage", {}).get("completion_tokens", MAX_OUTPUT_TOKENS)
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
    except Exception as e:
        return {
            "text": f"AI调用失败：{str(e)}",
            "cost": cost_info["cost_yuan"],
            "tokens": input_tokens,
            "error": str(e)
        }
