"""
技术指标计算模块（纯pandas/numpy实现，无需pandas-ta）
"""
import pandas as pd
import numpy as np


def _sma(series: pd.Series, length: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=length).mean()


def _ema(series: pd.Series, length: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=length, adjust=False).mean()


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有技术指标，返回带指标列的DataFrame
    """
    if df.empty:
        return df

    df = df.copy()

    # ============ 均线系统 ============
    df["ma5"] = _sma(df["close"], 5)
    df["ma10"] = _sma(df["close"], 10)
    df["ma20"] = _sma(df["close"], 20)
    df["ma60"] = _sma(df["close"], 60)
    df["ma120"] = _sma(df["close"], 120)

    # ============ MACD ============
    ema12 = _ema(df["close"], 12)
    ema26 = _ema(df["close"], 26)
    df["macd"] = ema12 - ema26  # DIF
    df["macd_signal"] = _ema(df["macd"], 9)  # DEA
    df["macd_hist"] = (df["macd"] - df["macd_signal"]) * 2  # MACD柱

    # ============ KDJ ============
    low_min = df["low"].rolling(window=9).min()
    high_max = df["high"].rolling(window=9).max()
    rsv = (df["close"] - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)
    df["k"] = rsv.ewm(com=2, adjust=False).mean()
    df["d"] = df["k"].ewm(com=2, adjust=False).mean()
    df["j"] = 3 * df["k"] - 2 * df["d"]

    # ============ RSI ============
    for period in [6, 12, 24]:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        rs = avg_gain / avg_loss
        df[f"rsi{period}"] = 100 - (100 / (1 + rs))

    # ============ 布林带 ============
    df["boll_mid"] = _sma(df["close"], 20)
    std = df["close"].rolling(window=20).std()
    df["boll_upper"] = df["boll_mid"] + 2 * std
    df["boll_lower"] = df["boll_mid"] - 2 * std

    # ============ 成交量均线 ============
    df["vol_ma5"] = _sma(df["volume"], 5)
    df["vol_ma10"] = _sma(df["volume"], 10)

    # ============ ATR（波动率）============
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(window=14).mean()

    return df


def get_ma_signal(df: pd.DataFrame) -> dict:
    """均线系统信号"""
    if df.empty or len(df) < 60:
        return {"signal": "数据不足", "desc": "K线数据不足，无法分析均线"}

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = latest["close"]

    signals = []
    score = 0

    # 均线多头排列
    if (latest["ma5"] > latest["ma10"] > latest["ma20"] > latest["ma60"]):
        signals.append("均线多头排列（强势）")
        score += 2
    elif (latest["ma5"] < latest["ma10"] < latest["ma20"] < latest["ma60"]):
        signals.append("均线空头排列（弱势）")
        score -= 2

    # 价格位置
    if close > latest["ma5"] > latest["ma10"]:
        signals.append("股价站上5日和10日均线")
        score += 1
    elif close < latest["ma5"] < latest["ma10"]:
        signals.append("股价跌破5日和10日均线")
        score -= 1

    # 均线金叉/死叉
    if prev["ma5"] <= prev["ma10"] and latest["ma5"] > latest["ma10"]:
        signals.append("5日均线上穿10日均线（金叉）")
        score += 1
    elif prev["ma5"] >= prev["ma10"] and latest["ma5"] < latest["ma10"]:
        signals.append("5日均线下穿10日均线（死叉）")
        score -= 1

    # 60日均线支撑/压力
    if close > latest["ma60"] and prev["close"] <= prev["ma60"]:
        signals.append("突破60日均线（中期转强）")
        score += 1
    elif close < latest["ma60"] and prev["close"] >= prev["ma60"]:
        signals.append("跌破60日均线（中期转弱）")
        score -= 1

    if score >= 2:
        signal = "看多"
    elif score <= -2:
        signal = "看空"
    else:
        signal = "中性"

    return {
        "signal": signal,
        "score": score,
        "desc": "；".join(signals) if signals else "均线无明显信号",
        "ma5": round(latest["ma5"], 2),
        "ma10": round(latest["ma10"], 2),
        "ma20": round(latest["ma20"], 2),
        "ma60": round(latest["ma60"], 2),
    }


def get_macd_signal(df: pd.DataFrame) -> dict:
    """MACD信号"""
    if df.empty or "macd" not in df.columns or df["macd"].isna().all():
        return {"signal": "数据不足", "desc": "MACD数据不足"}

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signals = []
    score = 0

    if prev["macd"] <= prev["macd_signal"] and latest["macd"] > latest["macd_signal"]:
        signals.append("MACD金叉")
        score += 2
    elif prev["macd"] >= prev["macd_signal"] and latest["macd"] < latest["macd_signal"]:
        signals.append("MACD死叉")
        score -= 2

    if latest["macd"] > 0 and latest["macd_signal"] > 0:
        signals.append("MACD在零轴上方（多头区域）")
        score += 1
    elif latest["macd"] < 0 and latest["macd_signal"] < 0:
        signals.append("MACD在零轴下方（空头区域）")
        score -= 1

    if latest["macd_hist"] > 0 and latest["macd_hist"] > prev["macd_hist"]:
        signals.append("红柱放大（多头增强）")
        score += 1
    elif latest["macd_hist"] < 0 and latest["macd_hist"] < prev["macd_hist"]:
        signals.append("绿柱放大（空头增强）")
        score -= 1

    if score >= 2:
        signal = "看多"
    elif score <= -2:
        signal = "看空"
    else:
        signal = "中性"

    return {
        "signal": signal,
        "score": score,
        "desc": "；".join(signals) if signals else "MACD无明显信号",
        "macd": round(latest["macd"], 4),
        "signal_line": round(latest["macd_signal"], 4),
        "hist": round(latest["macd_hist"], 4),
    }


def get_kdj_signal(df: pd.DataFrame) -> dict:
    """KDJ信号"""
    if df.empty or "k" not in df.columns or df["k"].isna().all():
        return {"signal": "数据不足", "desc": "KDJ数据不足"}

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signals = []
    score = 0

    if latest["j"] > 100:
        signals.append(f"J值{latest['j']:.1f}超买区域")
        score -= 1
    elif latest["j"] < 0:
        signals.append(f"J值{latest['j']:.1f}超卖区域")
        score += 1

    if prev["k"] <= prev["d"] and latest["k"] > latest["d"]:
        if latest["k"] < 20:
            signals.append("KDJ低位金叉（强买入信号）")
            score += 2
        else:
            signals.append("KDJ金叉")
            score += 1
    elif prev["k"] >= prev["d"] and latest["k"] < latest["d"]:
        if latest["k"] > 80:
            signals.append("KDJ高位死叉（强卖出信号）")
            score -= 2
        else:
            signals.append("KDJ死叉")
            score -= 1

    if score >= 2:
        signal = "看多"
    elif score <= -2:
        signal = "看空"
    else:
        signal = "中性"

    return {
        "signal": signal,
        "score": score,
        "desc": "；".join(signals) if signals else "KDJ无明显信号",
        "k": round(latest["k"], 2),
        "d": round(latest["d"], 2),
        "j": round(latest["j"], 2),
    }


def get_rsi_signal(df: pd.DataFrame) -> dict:
    """RSI信号"""
    if df.empty or "rsi6" not in df.columns or df["rsi6"].isna().all():
        return {"signal": "数据不足", "desc": "RSI数据不足"}

    latest = df.iloc[-1]
    rsi = latest["rsi6"]

    signals = []
    score = 0

    if rsi > 80:
        signals.append(f"RSI6={rsi:.1f}，严重超买")
        score -= 2
    elif rsi > 70:
        signals.append(f"RSI6={rsi:.1f}，超买区域")
        score -= 1
    elif rsi < 20:
        signals.append(f"RSI6={rsi:.1f}，严重超卖")
        score += 2
    elif rsi < 30:
        signals.append(f"RSI6={rsi:.1f}，超卖区域")
        score += 1

    if score >= 2:
        signal = "看多"
    elif score <= -2:
        signal = "看空"
    else:
        signal = "中性"

    return {
        "signal": signal,
        "score": score,
        "desc": "；".join(signals) if signals else f"RSI6={rsi:.1f}，处于正常区域",
        "rsi6": round(latest["rsi6"], 2),
        "rsi12": round(latest["rsi12"], 2),
    }


def get_boll_signal(df: pd.DataFrame) -> dict:
    """布林带信号"""
    if df.empty or "boll_upper" not in df.columns or df["boll_upper"].isna().all():
        return {"signal": "数据不足", "desc": "布林带数据不足"}

    latest = df.iloc[-1]
    close = latest["close"]

    signals = []
    score = 0

    if close >= latest["boll_upper"]:
        signals.append("股价触及布林带上轨（超买/突破）")
        score -= 1
    elif close <= latest["boll_lower"]:
        signals.append("股价触及布林带下轨（超卖/破位）")
        score += 1
    elif close > latest["boll_mid"]:
        signals.append("股价在布林带中轨上方运行")
        score += 0.5
    else:
        signals.append("股价在布林带中轨下方运行")
        score -= 0.5

    if score >= 1:
        signal = "看多"
    elif score <= -1:
        signal = "看空"
    else:
        signal = "中性"

    return {
        "signal": signal,
        "score": score,
        "desc": "；".join(signals),
        "upper": round(latest["boll_upper"], 2),
        "mid": round(latest["boll_mid"], 2),
        "lower": round(latest["boll_lower"], 2),
    }


def get_volume_signal(df: pd.DataFrame) -> dict:
    """量价分析"""
    if df.empty or len(df) < 10:
        return {"signal": "数据不足", "desc": "成交量数据不足"}

    latest = df.iloc[-1]
    vol_ma5 = latest["vol_ma5"]

    signals = []
    score = 0

    vol_ratio = latest["volume"] / vol_ma5 if vol_ma5 and vol_ma5 > 0 else 1
    if vol_ratio > 2:
        signals.append(f"显著放量（量比{vol_ratio:.1f}）")
        if latest["pct_change"] > 0:
            signals.append("放量上涨（资金积极）")
            score += 1
        else:
            signals.append("放量下跌（资金出逃）")
            score -= 1
    elif vol_ratio < 0.5:
        signals.append(f"明显缩量（量比{vol_ratio:.1f}）")
        if latest["pct_change"] < 0:
            signals.append("缩量下跌（抛压减轻）")
            score += 0.5
        else:
            signals.append("缩量上涨（动能不足）")
            score -= 0.5

    if score >= 1:
        signal = "看多"
    elif score <= -1:
        signal = "看空"
    else:
        signal = "中性"

    return {
        "signal": signal,
        "score": score,
        "desc": "；".join(signals) if signals else "成交量正常",
        "volume": int(latest["volume"]),
        "vol_ratio": round(vol_ratio, 2),
    }


def get_support_resistance(df: pd.DataFrame) -> dict:
    """支撑位和阻力位"""
    if df.empty or len(df) < 20:
        return {"support": 0, "resistance": 0, "desc": "数据不足"}

    recent = df.tail(60)
    resistance = round(recent["high"].max(), 2)
    support = round(recent["low"].min(), 2)

    close = df.iloc[-1]["close"]
    dist_to_resist = (resistance - close) / close * 100
    dist_to_support = (close - support) / close * 100

    return {
        "support": support,
        "resistance": resistance,
        "dist_to_resistance": round(dist_to_resist, 1),
        "dist_to_support": round(dist_to_support, 1),
        "desc": f"上方阻力位{resistance}（距离{dist_to_resist:.1f}%），下方支撑位{support}（距离{dist_to_support:.1f}%）"
    }
