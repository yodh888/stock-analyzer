"""
数据获取与标准化模块。

对上层提供统一列结构的日 K 线和行情数据。数据源按
东方财富 -> 新浪 -> 腾讯 -> Yahoo Finance 顺序降级，但每次返回前都会
执行相同的数据质量校验，避免不同数据源字段差异泄漏到信号模块。
"""

import json
import math
from datetime import datetime, timedelta
from functools import lru_cache

import akshare as ak
import pandas as pd
import requests

from config import SHANGHAI_TZ

KLINE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
OPTIONAL_KLINE_COLUMNS = ["amount", "pct_change", "change", "turnover"]


def _now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _to_float(value):
    """把可能带百分号、逗号或空值的字段转换成 float/None。"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None

    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value or value in {"-", "--", "N/A", "None", "nan"}:
            return None
        if value.endswith("%"):
            value = value[:-1]

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _symbol_with_prefix(code: str) -> str:
    """给股票代码加市场前缀。"""
    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _yahoo_symbol(code: str) -> str:
    """转换成 Yahoo Finance 的代码格式。"""
    if code.startswith(("6", "5", "9")):
        return f"{code}.SS"
    return f"{code}.SZ"


def _normalize_kline(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """校验、清洗并统一 K 线数据。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=KLINE_COLUMNS + OPTIONAL_KLINE_COLUMNS)

    normalized = df.copy()
    missing = [column for column in KLINE_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"{source} 缺少K线字段: {', '.join(missing)}")

    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    for column in KLINE_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=KLINE_COLUMNS)
    normalized = normalized[normalized["volume"] >= 0]
    normalized = normalized.sort_values("date").drop_duplicates("date", keep="last")
    normalized = normalized.reset_index(drop=True)

    if "amount" not in normalized.columns:
        normalized["amount"] = float("nan")
    else:
        normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce")

    if "pct_change" not in normalized.columns:
        normalized["pct_change"] = normalized["close"].pct_change() * 100
    else:
        normalized["pct_change"] = pd.to_numeric(normalized["pct_change"], errors="coerce")
        normalized["pct_change"] = normalized["pct_change"].fillna(
            normalized["close"].pct_change() * 100
        )

    if "change" not in normalized.columns:
        normalized["change"] = normalized["close"].diff()
    else:
        normalized["change"] = pd.to_numeric(normalized["change"], errors="coerce")
        normalized["change"] = normalized["change"].fillna(normalized["close"].diff())

    if "turnover" not in normalized.columns:
        normalized["turnover"] = float("nan")
    else:
        normalized["turnover"] = pd.to_numeric(normalized["turnover"], errors="coerce")

    normalized.attrs["source"] = source
    normalized.attrs["fetched_at"] = _now().isoformat()
    return normalized

def get_stock_name(code: str) -> str:
    """根据股票代码获取股票名称。"""
    try:
        df = _get_spot_snapshot()
        row = df[df["代码"].astype(str).str.zfill(6) == code]
        if not row.empty:
            return str(row.iloc[0]["名称"])
    except Exception:
        pass
    return code


def get_kline_data(code: str, days: int = 120) -> pd.DataFrame:
    """
    获取最近 days 个交易日的数据。

    自然日请求量会额外扩大，确保 60/120/250 个交易日的选项都能拿到
    足够样本；数据源通常只按自然日做区间过滤。
    """
    if days <= 0:
        raise ValueError("days 必须大于 0")

    # 2 倍自然日加 30 天缓冲，可覆盖周末和节假日。例如 60 个交易日
    # 约需要 90 个自然日，250 个交易日约需要 380 个自然日。
    calendar_days = max(days * 2 + 30, days + 60)
    end_date = _now().strftime("%Y%m%d")
    start_date = (_now() - timedelta(days=calendar_days)).strftime("%Y%m%d")

    # 数据源1：东方财富
    try:
        raw = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        renamed = raw.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "amount", "涨跌幅": "pct_change",
            "涨跌额": "change", "换手率": "turnover",
        }) if raw is not None else raw
        df = _normalize_kline(renamed, "东方财富")
        if not df.empty:
            result = df.tail(days).reset_index(drop=True)
            result.attrs = df.attrs.copy()
            print(f"[{code}] 东方财富, {len(result)}条")
            return result
    except Exception as exc:
        print(f"[{code}] 东方财富失败: {type(exc).__name__}")

    # 数据源2：新浪财经 HTTP 接口
    try:
        symbol = _symbol_with_prefix(code)
        url = (
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={calendar_days}"
        )
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://finance.sina.com.cn",
            },
            timeout=(5, 15),
        )
        resp.raise_for_status()
        data = json.loads(resp.text)
        raw = pd.DataFrame(data).rename(columns={
            "day": "date", "open": "open", "close": "close",
            "high": "high", "low": "low", "volume": "volume",
        })
        df = _normalize_kline(raw, "新浪HTTP")
        if not df.empty:
            df["amount"] = float("nan")
            result = df.tail(days).reset_index(drop=True)
            result.attrs = df.attrs.copy()
            print(f"[{code}] 新浪HTTP, {len(result)}条")
            return result
    except Exception as exc:
        print(f"[{code}] 新浪HTTP失败: {type(exc).__name__}")

    # 数据源3：腾讯财经
    try:
        symbol = _symbol_with_prefix(code)
        raw = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        df = _normalize_kline(raw, "腾讯财经")
        if not df.empty:
            df["turnover"] = float("nan")
            result = df.tail(days).reset_index(drop=True)
            result.attrs = df.attrs.copy()
            print(f"[{code}] 腾讯财经, {len(result)}条")
            return result
    except Exception as exc:
        print(f"[{code}] 腾讯财经失败: {type(exc).__name__}")

    # 数据源4：Yahoo Finance
    try:
        import yfinance as yf

        ticker = yf.Ticker(_yahoo_symbol(code))
        raw = ticker.history(
            start=start_date,
            end=(_now() + timedelta(days=1)).strftime("%Y%m%d"),
            auto_adjust=True,
        )
        if raw is not None and not raw.empty:
            raw = raw.reset_index().rename(columns={
                "Date": "date", "Open": "open", "Close": "close",
                "High": "high", "Low": "low", "Volume": "volume",
            })
            raw["amount"] = raw["close"] * raw["volume"]
            raw["turnover"] = float("nan")
            df = _normalize_kline(raw, "Yahoo Finance")
            if not df.empty:
                result = df.tail(days).reset_index(drop=True)
                result.attrs = df.attrs.copy()
                print(f"[{code}] Yahoo Finance, {len(result)}条")
                return result
    except Exception as exc:
        print(f"[{code}] Yahoo Finance失败: {type(exc).__name__}")

    print(f"[{code}] 所有数据源均失败")
    return pd.DataFrame(columns=KLINE_COLUMNS + OPTIONAL_KLINE_COLUMNS)


@lru_cache(maxsize=1)
def _get_spot_snapshot() -> pd.DataFrame:
    """获取全市场快照并在进程内复用，减少数据源限流。"""
    last_error = None
    for fetcher in (ak.stock_zh_a_spot_em, ak.stock_zh_a_spot):
        try:
            df = fetcher()
            if df is not None and not df.empty:
                return df.copy()
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("行情快照为空")


def clear_market_cache() -> None:
    """清空行情快照缓存，主要供测试或长进程刷新使用。"""
    _get_spot_snapshot.cache_clear()


@lru_cache(maxsize=1)
def _get_trade_dates() -> set:
    """获取交易日历；数据源失败时由调用方选择放行。"""
    calendar = ak.tool_trade_date_hist_sina()
    if calendar is None or calendar.empty:
        raise ValueError("交易日历为空")
    column = "trade_date" if "trade_date" in calendar.columns else calendar.columns[0]
    return set(pd.to_datetime(calendar[column], errors="coerce").dropna().dt.date)


def is_trade_day(day=None) -> bool:
    """判断指定日期是否为交易日，无法获取日历时默认放行。"""
    target = day or _now().date()
    try:
        return target in _get_trade_dates()
    except Exception:
        return True


def _quote_from_row(row: pd.Series) -> dict:
    price = _to_float(row.get("最新价"))
    previous_close = _to_float(row.get("昨收"))
    change_pct = _to_float(row.get("涨跌幅"))
    if change_pct is None and price is not None and previous_close:
        change_pct = (price - previous_close) / previous_close * 100

    return {
        "name": str(row.get("名称", "")),
        "price": price,
        "change_pct": change_pct,
        "change": _to_float(row.get("涨跌额")),
        "volume": _to_float(row.get("成交量")),
        "amount": _to_float(row.get("成交额")),
        "high": _to_float(row.get("最高")),
        "low": _to_float(row.get("最低")),
        "open": _to_float(row.get("今开")),
        "prev_close": previous_close,
        "turnover": _to_float(row.get("换手率")),
        "pe": _to_float(row.get("市盈率-动态")),
        "pb": _to_float(row.get("市净率")),
        "total_mv": _to_float(row.get("总市值")),
        "circ_mv": _to_float(row.get("流通市值")),
    }

def get_realtime_quote(code: str) -> dict:
    """获取实时行情，缺失字段返回 None。"""
    try:
        df = _get_spot_snapshot()
        row = df[df["代码"].astype(str).str.zfill(6) == code]
        if not row.empty:
            return _quote_from_row(row.iloc[0])
    except Exception:
        pass

    # 新浪实时行情备份
    try:
        symbol = _symbol_with_prefix(code)
        resp = requests.get(
            f"https://hq.sinajs.cn/list={symbol}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn",
            },
            timeout=(5, 10),
        )
        resp.raise_for_status()
        start = resp.text.find('"')
        end = resp.text.rfind('"')
        if start > 0 and end > start:
            fields = resp.text[start + 1:end].split(",")
            if len(fields) >= 32:
                price = _to_float(fields[3])
                previous_close = _to_float(fields[2])
                change = None
                change_pct = None
                if price is not None and previous_close:
                    change = price - previous_close
                    change_pct = change / previous_close * 100
                return {
                    "name": fields[0],
                    "open": _to_float(fields[1]),
                    "prev_close": previous_close,
                    "price": price,
                    "high": _to_float(fields[4]),
                    "low": _to_float(fields[5]),
                    "volume": _to_float(fields[8]),
                    "amount": _to_float(fields[9]),
                    "change_pct": change_pct,
                    "change": change,
                    "turnover": None,
                    "pe": None,
                    "pb": None,
                    "total_mv": None,
                    "circ_mv": None,
                }
    except Exception:
        pass

    return {}


def get_financial_basic(code: str) -> dict:
    """获取基本面关键指标，无法获取的字段保持 None。"""
    result = {
        "pe": None,
        "pb": None,
        "roe": None,
        "revenue_yoy": None,
        "profit_yoy": None,
        "gross_margin": None,
        "debt_ratio": None,
    }

    try:
        quote = get_realtime_quote(code)
        result["pe"] = quote.get("pe")
        result["pb"] = quote.get("pb")
    except Exception:
        pass

    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is not None and not df.empty:
            latest = df.iloc[0]
            for column in df.columns:
                name = str(column)
                value = _to_float(latest[column])
                if "净资产收益率" in name:
                    result["roe"] = value
                elif "营业总收入" in name and "同比" in name:
                    result["revenue_yoy"] = value
                elif "净利润" in name and "同比" in name:
                    result["profit_yoy"] = value
                elif "毛利率" in name:
                    result["gross_margin"] = value
                elif "资产负债率" in name:
                    result["debt_ratio"] = value
    except Exception:
        pass

    return result


def get_hot_stocks() -> pd.DataFrame:
    """获取涨幅榜前 50 名。"""
    try:
        df = _get_spot_snapshot()
        result = df.copy()
        result["涨跌幅"] = pd.to_numeric(result["涨跌幅"], errors="coerce")
        result = result.sort_values("涨跌幅", ascending=False).head(50)
        columns = ["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]
        return result[columns].reset_index(drop=True)
    except Exception:
        return pd.DataFrame()
