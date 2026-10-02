"""
数据获取模块 - 多数据源自动切换
优先级：东方财富 → 东方财富ETF → 新浪HTTP → 腾讯 → Yahoo Finance
"""
import akshare as ak
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

def _symbol_with_prefix(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    else:
        return f"sz{code}"

def _yahoo_symbol(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"{code}.SS"
    else:
        return f"{code}.SZ"

def get_stock_name(code: str) -> str:
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            return row.iloc[0]["名称"]
    except Exception:
        pass
    try:
        df = ak.stock_zh_a_spot()
        row = df[df["代码"] == code]
        if not row.empty:
            return row.iloc[0]["名称"]
    except Exception:
        pass
    return code

def get_kline_data(code: str, days: int = 120) -> pd.DataFrame:
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    # 数据源1：东方财富（普通股票）
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_change", "涨跌额": "change", "换手率": "turnover"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            print(f"[{code}] 东方财富, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] 东方财富失败: {e}")

    # 数据源2：东方财富ETF接口
    try:
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_change", "涨跌额": "change", "换手率": "turnover"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            print(f"[{code}] 东方财富ETF, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] 东方财富ETF失败: {e}")

    # 数据源3：新浪财经HTTP接口
    try:
        symbol = _symbol_with_prefix(code)
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={days}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200 and resp.text:
            import json
            data = json.loads(resp.text)
            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df = df.rename(columns={"day": "date", "open": "open", "close": "close", "high": "high", "low": "low", "volume": "volume"})
                for col in ["open", "close", "high", "low", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df["date"] = pd.to_datetime(df["date"])
                df["amount"] = 0
                df["pct_change"] = df["close"].pct_change() * 100
                df["change"] = df["close"].diff()
                df["turnover"] = 0
                df = df.sort_values("date").reset_index(drop=True)
                print(f"[{code}] 新浪HTTP, {len(df)}条")
                return df
    except Exception as e:
        print(f"[{code}] 新浪HTTP失败: {e}")

    # 数据源4：腾讯财经
    try:
        symbol = _symbol_with_prefix(code)
        df = ak.stock_zh_a_hist_tx(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"date": "date", "open": "open", "close": "close", "high": "high", "low": "low", "volume": "volume", "amount": "amount"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df["pct_change"] = df["close"].pct_change() * 100
            df["change"] = df["close"].diff()
            df["turnover"] = 0
            df = df.tail(days).reset_index(drop=True)
            print(f"[{code}] 腾讯财经, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] 腾讯财经失败: {e}")

    # 数据源5：Yahoo Finance
    try:
        import yfinance as yf
        yf_symbol = _yahoo_symbol(code)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=f"{days}d", auto_adjust=True)
        if df is not None and not df.empty:
            df = df.reset_index()
            df = df.rename(columns={"Date": "date", "Open": "open", "Close": "close", "High": "high", "Low": "low", "Volume": "volume"})
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            df = df.sort_values("date").reset_index(drop=True)
            df["amount"] = df["close"] * df["volume"]
            df["pct_change"] = df["close"].pct_change() * 100
            df["change"] = df["close"].diff()
            df["turnover"] = 0
            print(f"[{code}] Yahoo Finance, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] Yahoo Finance失败: {e}")

    print(f"[{code}] 所有数据源均失败")
    return pd.DataFrame()

def get_realtime_quote(code: str) -> dict:
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            r = row.iloc[0]
            return {"name": r.get("名称", ""), "price": float(r.get("最新价", 0)), "change_pct": float(r.get("涨跌幅", 0)), "change": float(r.get("涨跌额", 0)), "volume": float(r.get("成交量", 0)), "amount": float(r.get("成交额", 0)), "high": float(r.get("最高", 0)), "low": float(r.get("最低", 0)), "open": float(r.get("今开", 0)), "prev_close": float(r.get("昨收", 0)), "turnover": float(r.get("换手率", 0)), "pe": float(r.get("市盈率-动态", 0)) if r.get("市盈率-动态") else 0, "pb": float(r.get("市净率", 0)) if r.get("市净率") else 0, "total_mv": float(r.get("总市值", 0)), "circ_mv": float(r.get("流通市值", 0))}
    except Exception:
        pass
    try:
        symbol = _symbol_with_prefix(code)
        url = f"https://hq.sinajs.cn/list={symbol}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.text:
            text = resp.text
            start = text.find('"')
            end = text.rfind('"')
            if start > 0 and end > start:
                fields = text[start+1:end].split(",")
                if len(fields) >= 32:
                    return {"name": fields[0], "open": float(fields[1]), "prev_close": float(fields[2]), "price": float(fields[3]), "high": float(fields[4]), "low": float(fields[5]), "volume": float(fields[8]), "amount": float(fields[9]), "change_pct": (float(fields[3]) - float(fields[2])) / float(fields[2]) * 100 if float(fields[2]) > 0 else 0, "change": float(fields[3]) - float(fields[2]), "turnover": 0, "pe": 0, "pb": 0, "total_mv": 0, "circ_mv": 0}
    except Exception:
        pass
    return {}

def get_financial_basic(code: str) -> dict:
    result = {"pe": 0, "pb": 0, "roe": 0, "revenue_yoy": 0, "profit_yoy": 0, "gross_margin": 0, "debt_ratio": 0}
    try:
        quote = get_realtime_quote(code)
        result["pe"] = quote.get("pe", 0)
        result["pb"] = quote.get("pb", 0)
        try:
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[0]
                for col in df.columns:
                    if "净资产收益率" in str(col):
                        result["roe"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "营业总收入" in str(col) and "同比" in str(col):
                        result["revenue_yoy"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "净利润" in str(col) and "同比" in str(col):
                        result["profit_yoy"] = float(latest[col]) if pd.notna(latest[col]) else 0
        except Exception:
            pass
    except Exception as e:
        print(f"获取基本面失败: {e}")
    return result

def get_hot_stocks() -> pd.DataFrame:
    try:
        df = ak.stock_zh_a_spot_em()
        df = df.sort_values("涨跌幅", ascending=False).head(50)
        return df[["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]].reset_index(drop=True)
    except Exception:
        pass
    try:
        df = ak.stock_zh_a_spot()
        df = df.sort_values("涨跌幅", ascending=False).head(50)
        return df[["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]].reset_index(drop=True)
    except Exception as e:
        print(f"获取热门股票失败: {e}")
        return pd.DataFrame()"""
数据获取模块 - 多数据源自动切换
优先级：东方财富 → 东方财富ETF → 新浪HTTP → 腾讯 → Yahoo Finance
"""
import akshare as ak
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

def _symbol_with_prefix(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    else:
        return f"sz{code}"

def _yahoo_symbol(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"{code}.SS"
    else:
        return f"{code}.SZ"

def get_stock_name(code: str) -> str:
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            return row.iloc[0]["名称"]
    except Exception:
        pass
    try:
        df = ak.stock_zh_a_spot()
        row = df[df["代码"] == code]
        if not row.empty:
            return row.iloc[0]["名称"]
    except Exception:
        pass
    return code

def get_kline_data(code: str, days: int = 120) -> pd.DataFrame:
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    # 数据源1：东方财富（普通股票）
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_change", "涨跌额": "change", "换手率": "turnover"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            print(f"[{code}] 东方财富, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] 东方财富失败: {e}")

    # 数据源2：东方财富ETF接口
    try:
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_change", "涨跌额": "change", "换手率": "turnover"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            print(f"[{code}] 东方财富ETF, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] 东方财富ETF失败: {e}")

    # 数据源3：新浪财经HTTP接口
    try:
        symbol = _symbol_with_prefix(code)
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={days}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200 and resp.text:
            import json
            data = json.loads(resp.text)
            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df = df.rename(columns={"day": "date", "open": "open", "close": "close", "high": "high", "low": "low", "volume": "volume"})
                for col in ["open", "close", "high", "low", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df["date"] = pd.to_datetime(df["date"])
                df["amount"] = 0
                df["pct_change"] = df["close"].pct_change() * 100
                df["change"] = df["close"].diff()
                df["turnover"] = 0
                df = df.sort_values("date").reset_index(drop=True)
                print(f"[{code}] 新浪HTTP, {len(df)}条")
                return df
    except Exception as e:
        print(f"[{code}] 新浪HTTP失败: {e}")

    # 数据源4：腾讯财经
    try:
        symbol = _symbol_with_prefix(code)
        df = ak.stock_zh_a_hist_tx(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"date": "date", "open": "open", "close": "close", "high": "high", "low": "low", "volume": "volume", "amount": "amount"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df["pct_change"] = df["close"].pct_change() * 100
            df["change"] = df["close"].diff()
            df["turnover"] = 0
            df = df.tail(days).reset_index(drop=True)
            print(f"[{code}] 腾讯财经, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] 腾讯财经失败: {e}")

    # 数据源5：Yahoo Finance
    try:
        import yfinance as yf
        yf_symbol = _yahoo_symbol(code)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=f"{days}d", auto_adjust=True)
        if df is not None and not df.empty:
            df = df.reset_index()
            df = df.rename(columns={"Date": "date", "Open": "open", "Close": "close", "High": "high", "Low": "low", "Volume": "volume"})
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            df = df.sort_values("date").reset_index(drop=True)
            df["amount"] = df["close"] * df["volume"]
            df["pct_change"] = df["close"].pct_change() * 100
            df["change"] = df["close"].diff()
            df["turnover"] = 0
            print(f"[{code}] Yahoo Finance, {len(df)}条")
            return df
    except Exception as e:
        print(f"[{code}] Yahoo Finance失败: {e}")

    print(f"[{code}] 所有数据源均失败")
    return pd.DataFrame()

def get_realtime_quote(code: str) -> dict:
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            r = row.iloc[0]
            return {"name": r.get("名称", ""), "price": float(r.get("最新价", 0)), "change_pct": float(r.get("涨跌幅", 0)), "change": float(r.get("涨跌额", 0)), "volume": float(r.get("成交量", 0)), "amount": float(r.get("成交额", 0)), "high": float(r.get("最高", 0)), "low": float(r.get("最低", 0)), "open": float(r.get("今开", 0)), "prev_close": float(r.get("昨收", 0)), "turnover": float(r.get("换手率", 0)), "pe": float(r.get("市盈率-动态", 0)) if r.get("市盈率-动态") else 0, "pb": float(r.get("市净率", 0)) if r.get("市净率") else 0, "total_mv": float(r.get("总市值", 0)), "circ_mv": float(r.get("流通市值", 0))}
    except Exception:
        pass
    try:
        symbol = _symbol_with_prefix(code)
        url = f"https://hq.sinajs.cn/list={symbol}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.text:
            text = resp.text
            start = text.find('"')
            end = text.rfind('"')
            if start > 0 and end > start:
                fields = text[start+1:end].split(",")
                if len(fields) >= 32:
                    return {"name": fields[0], "open": float(fields[1]), "prev_close": float(fields[2]), "price": float(fields[3]), "high": float(fields[4]), "low": float(fields[5]), "volume": float(fields[8]), "amount": float(fields[9]), "change_pct": (float(fields[3]) - float(fields[2])) / float(fields[2]) * 100 if float(fields[2]) > 0 else 0, "change": float(fields[3]) - float(fields[2]), "turnover": 0, "pe": 0, "pb": 0, "total_mv": 0, "circ_mv": 0}
    except Exception:
        pass
    return {}

def get_financial_basic(code: str) -> dict:
    result = {"pe": 0, "pb": 0, "roe": 0, "revenue_yoy": 0, "profit_yoy": 0, "gross_margin": 0, "debt_ratio": 0}
    try:
        quote = get_realtime_quote(code)
        result["pe"] = quote.get("pe", 0)
        result["pb"] = quote.get("pb", 0)
        try:
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[0]
                for col in df.columns:
                    if "净资产收益率" in str(col):
                        result["roe"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "营业总收入" in str(col) and "同比" in str(col):
                        result["revenue_yoy"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "净利润" in str(col) and "同比" in str(col):
                        result["profit_yoy"] = float(latest[col]) if pd.notna(latest[col]) else 0
        except Exception:
            pass
    except Exception as e:
        print(f"获取基本面失败: {e}")
    return result

def get_hot_stocks() -> pd.DataFrame:
    try:
        df = ak.stock_zh_a_spot_em()
        df = df.sort_values("涨跌幅", ascending=False).head(50)
        return df[["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]].reset_index(drop=True)
    except Exception:
        pass
    try:
        df = ak.stock_zh_a_spot()
        df = df.sort_values("涨跌幅", ascending=False).head(50)
        return df[["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]].reset_index(drop=True)
    except Exception as e:
        print(f"获取热门股票失败: {e}")
        return pd.DataFrame()
