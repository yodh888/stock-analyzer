"""
综合信号模块 - 整合所有技术指标和K线形态，给出最终买卖建议
"""
import pandas as pd
from indicators import (
    calculate_all_indicators, get_ma_signal, get_macd_signal,
    get_kdj_signal, get_rsi_signal, get_boll_signal,
    get_volume_signal, get_support_resistance
)
from patterns import detect_patterns


def generate_comprehensive_signal(df: pd.DataFrame) -> dict:
    """
    生成综合分析信号
    返回包含所有维度信号和综合建议的字典
    """
    if df.empty:
        return {"error": "数据为空"}

    # 计算指标
    df = calculate_all_indicators(df)

    # 各维度信号
    ma = get_ma_signal(df)
    macd = get_macd_signal(df)
    kdj = get_kdj_signal(df)
    rsi = get_rsi_signal(df)
    boll = get_boll_signal(df)
    volume = get_volume_signal(df)
    sr = get_support_resistance(df)
    kline_patterns = detect_patterns(df)

    # 计算综合得分
    total_score = 0
    details = []

    # 各指标权重
    weights = {
        "均线": 1.5,
        "MACD": 1.5,
        "KDJ": 1.0,
        "RSI": 1.0,
        "布林带": 0.8,
        "成交量": 1.2,
        "K线形态": 1.3,
    }

    # 均线
    total_score += ma["score"] * weights["均线"]
    details.append({"维度": "均线系统", "信号": ma["signal"], "得分": ma["score"], "说明": ma["desc"]})

    # MACD
    total_score += macd["score"] * weights["MACD"]
    details.append({"维度": "MACD", "信号": macd["signal"], "得分": macd["score"], "说明": macd["desc"]})

    # KDJ
    total_score += kdj["score"] * weights["KDJ"]
    details.append({"维度": "KDJ", "信号": kdj["signal"], "得分": kdj["score"], "说明": kdj["desc"]})

    # RSI
    total_score += rsi["score"] * weights["RSI"]
    details.append({"维度": "RSI", "信号": rsi["signal"], "得分": rsi["score"], "说明": rsi["desc"]})

    # 布林带
    total_score += boll["score"] * weights["布林带"]
    details.append({"维度": "布林带", "信号": boll["signal"], "得分": boll["score"], "说明": boll["desc"]})

    # 成交量
    total_score += volume["score"] * weights["成交量"]
    details.append({"维度": "量价关系", "信号": volume["signal"], "得分": volume["score"], "说明": volume["desc"]})

    # K线形态
    pattern_score = 0
    pattern_signals = []
    for p in kline_patterns:
        pattern_signals.append(f"{p['name']}({p['signal']})")
        if p["signal"] == "看多":
            pattern_score += 1
        elif p["signal"] == "看空":
            pattern_score -= 1
    total_score += pattern_score * weights["K线形态"]
    details.append({
        "维度": "K线形态",
        "信号": "看多" if pattern_score > 0 else ("看空" if pattern_score < 0 else "中性"),
        "得分": pattern_score,
        "说明": "；".join(pattern_signals) if pattern_signals else "无明显形态"
    })

    # 综合建议
    if total_score >= 3:
        suggestion = "强烈看多"
        action = "可考虑买入"
        emoji = "🟢"
    elif total_score >= 1.5:
        suggestion = "偏多"
        action = "可逢低关注"
        emoji = "🟢"
    elif total_score > -1.5:
        suggestion = "中性震荡"
        action = "建议观望"
        emoji = "🟡"
    elif total_score > -3:
        suggestion = "偏空"
        action = "谨慎操作"
        emoji = "🔴"
    else:
        suggestion = "强烈看空"
        action = "建议卖出/回避"
        emoji = "🔴"

    latest = df.iloc[-1]

    return {
        "suggestion": suggestion,
        "action": action,
        "emoji": emoji,
        "total_score": round(total_score, 2),
        "details": details,
        "support_resistance": sr,
        "latest_price": round(latest["close"], 2),
        "pct_change": round(latest["pct_change"], 2),
        "turnover": round(latest["turnover"], 2),
        "patterns": kline_patterns,
        # 具体指标值，供AI解读使用
        "indicator_values": {
            "ma5": ma.get("ma5"), "ma10": ma.get("ma10"),
            "ma20": ma.get("ma20"), "ma60": ma.get("ma60"),
            "macd": macd.get("macd"), "macd_signal": macd.get("signal_line"),
            "macd_hist": macd.get("hist"),
            "k": kdj.get("k"), "d": kdj.get("d"), "j": kdj.get("j"),
            "rsi6": rsi.get("rsi6"), "rsi12": rsi.get("rsi12"),
            "boll_upper": boll.get("upper"), "boll_mid": boll.get("mid"),
            "boll_lower": boll.get("lower"),
            "vol_ratio": volume.get("vol_ratio"),
        }
    }


def format_signal_text(result: dict, stock_name: str, stock_code: str) -> str:
    """将信号结果格式化为纯文本（用于AI输入和推送）"""
    lines = [
        f"【{stock_name}({stock_code}) 综合分析】",
        f"最新价: {result['latest_price']}  涨跌幅: {result['pct_change']}%  换手率: {result['turnover']}%",
        f"综合判断: {result['emoji']} {result['suggestion']}（得分{result['total_score']}）",
        f"操作建议: {result['action']}",
        "",
        "【各维度信号】"
    ]
    for d in result["details"]:
        lines.append(f"  {d['维度']}: {d['信号']}（{d['说明']}）")

    lines.append("")
    lines.append(f"【支撑阻力】{result['support_resistance']['desc']}")

    lines.append("")
    lines.append("【K线形态】")
    for p in result["patterns"]:
        lines.append(f"  {p['name']}: {p['desc']}")

    return "\n".join(lines)
