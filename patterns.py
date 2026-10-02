"""
K线形态识别模块
识别经典K线形态，给出信号
"""
import pandas as pd


def _is_bullish(row):
    """阳线"""
    return row["close"] > row["open"]


def _is_bearish(row):
    """阴线"""
    return row["close"] < row["open"]


def _body(row):
    return abs(row["close"] - row["open"])


def _upper_shadow(row):
    return row["high"] - max(row["close"], row["open"])


def _lower_shadow(row):
    return min(row["close"], row["open"]) - row["low"]


def _is_doji(row, threshold=0.1):
    """十字星：实体很小"""
    body = _body(row)
    total_range = row["high"] - row["low"]
    if total_range == 0:
        return True
    return body / total_range < threshold


def detect_patterns(df: pd.DataFrame) -> list:
    """
    识别最近几天的K线形态
    返回形态列表，每个元素包含: name, signal, desc
    signal: 看多 / 看空 / 中性
    """
    if df.empty or len(df) < 5:
        return [{"name": "数据不足", "signal": "中性", "desc": "K线数据不足，无法识别形态"}]

    patterns = []
    # 取最近3根K线
    recent = df.tail(3).reset_index(drop=True)
    d0 = recent.iloc[-1]  # 最新
    d1 = recent.iloc[-2]  # 前一天
    d2 = recent.iloc[-3] if len(recent) >= 3 else None  # 前两天

    avg_body = df.tail(20)["close"].sub(df.tail(20)["open"]).abs().mean()

    # ============ 单根K线形态 ============

    # 大阳线
    if _is_bullish(d0) and _body(d0) > avg_body * 2:
        patterns.append({
            "name": "大阳线",
            "signal": "看多",
            "desc": f"实体涨幅{(d0['close']-d0['open'])/d0['open']*100:.1f}%，多头力量强劲"
        })

    # 大阴线
    if _is_bearish(d0) and _body(d0) > avg_body * 2:
        patterns.append({
            "name": "大阴线",
            "signal": "看空",
            "desc": f"实体跌幅{(d0['open']-d0['close'])/d0['open']*100:.1f}%，空头力量强劲"
        })

    # 锤子线（下影线长，实体小，在低位）
    lower = _lower_shadow(d0)
    body = _body(d0)
    has_ma20 = "ma20" in df.columns and not pd.isna(d0.get("ma20"))
    is_low_position = not has_ma20 or d0["close"] < d0["ma20"]
    if lower > body * 2 and _upper_shadow(d0) < body * 0.5 and is_low_position:
        patterns.append({
            "name": "锤子线",
            "signal": "看多",
            "desc": "下影线较长，实体较小，可能见底反转"
        })

    # 上吊线（下影线长，实体小，在高位）
    if lower > body * 2 and _upper_shadow(d0) < body * 0.5 and "ma20" in df.columns and not pd.isna(d0.get("ma20")) and d0["close"] > d0["ma20"]:
        patterns.append({
            "name": "上吊线",
            "signal": "看空",
            "desc": "高位出现下影线长的小实体，可能见顶"
        })

    # 射击之星（上影线长，实体小）
    upper = _upper_shadow(d0)
    if upper > body * 2 and lower < body * 0.5:
        patterns.append({
            "name": "射击之星",
            "signal": "看空",
            "desc": "上影线较长，实体较小，上方抛压较重"
        })

    # 十字星
    if _is_doji(d0):
        patterns.append({
            "name": "十字星",
            "signal": "中性",
            "desc": "多空分歧加大，趋势可能变盘"
        })

    # ============ 两根K线组合 ============

    # 看涨吞没
    if _is_bearish(d1) and _is_bullish(d0) and d0["close"] >= d1["open"] and d0["open"] <= d1["close"] and _body(d0) > _body(d1):
        patterns.append({
            "name": "看涨吞没",
            "signal": "看多",
            "desc": "阳线实体完全吞没前阴线实体，强势反转信号"
        })

    # 看跌吞没
    if _is_bullish(d1) and _is_bearish(d0) and d0["open"] >= d1["close"] and d0["close"] <= d1["open"] and _body(d0) > _body(d1):
        patterns.append({
            "name": "看跌吞没",
            "signal": "看空",
            "desc": "阴线实体完全吞没前阳线实体，强势反转信号"
        })

    # 曙光初现
    if _is_bearish(d1) and _is_bullish(d0) and d0["open"] < d1["low"] and d0["close"] > d1["close"] and d0["close"] < (d1["open"] + d1["close"]) / 2:
        patterns.append({
            "name": "曙光初现",
            "signal": "看多",
            "desc": "低开高走，收盘价超过阴线实体中点，见底信号"
        })

    # 乌云盖顶
    if _is_bullish(d1) and _is_bearish(d0) and d0["open"] > d1["high"] and d0["close"] < d1["close"] and d0["close"] > (d1["open"] + d1["close"]) / 2:
        patterns.append({
            "name": "乌云盖顶",
            "signal": "看空",
            "desc": "高开低走，收盘价跌破阳线实体中点，见顶信号"
        })

    # ============ 三根K线组合 ============
    if d2 is not None:
        # 早晨之星
        if (_is_bearish(d2) and _body(d2) > avg_body and
                _is_doji(d1) and
                _is_bullish(d0) and d0["close"] > (d2["open"] + d2["close"]) / 2):
            patterns.append({
                "name": "早晨之星",
                "signal": "看多",
                "desc": "三根K线组合，见底反转信号"
            })

        # 黄昏之星
        if (_is_bullish(d2) and _body(d2) > avg_body and
                _is_doji(d1) and
                _is_bearish(d0) and d0["close"] < (d2["open"] + d2["close"]) / 2):
            patterns.append({
                "name": "黄昏之星",
                "signal": "看空",
                "desc": "三根K线组合，见顶反转信号"
            })

        # 红三兵
        if _is_bullish(d2) and _is_bullish(d1) and _is_bullish(d0) and \
           d0["close"] > d1["close"] > d2["close"] and \
           d0["open"] > d2["open"]:
            patterns.append({
                "name": "红三兵",
                "signal": "看多",
                "desc": "连续三根阳线，收盘价逐步抬高，强势上涨信号"
            })

        # 黑三鸦
        if _is_bearish(d2) and _is_bearish(d1) and _is_bearish(d0) and \
           d0["close"] < d1["close"] < d2["close"]:
            patterns.append({
                "name": "黑三鸦",
                "signal": "看空",
                "desc": "连续三根阴线，收盘价逐步走低，弱势下跌信号"
            })

    if not patterns:
        patterns.append({
            "name": "无明显形态",
            "signal": "中性",
            "desc": "近期未出现典型K线形态"
        })

    return patterns
