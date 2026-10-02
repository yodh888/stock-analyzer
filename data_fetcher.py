"""
数据获取模块 - 使用AKShare获取A股数据
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta


def get_stock_name(code: str) -> str:
    """根据股票代码获取股票名称"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            return row.iloc[0]["名称"]
        return code
    except Exception as e:
        print(f"获取股票名称失败: {e}")
        return code


def get_kline_data(code: str, days: int = 120) -> pd.DataFrame:
    """
    获取日K线数据
    返回DataFrame包含: 日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率
    """
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        if df.empty:
            return pd.DataFrame()
        # 统一列名
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover"
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"获取K线数据失败: {e}")
        return pd.DataFrame()


def get_realtime_quote(code: str) -> dict:
    """获取实时行情"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            return {}
        r = row.iloc[0]
        return {
            "name": r.get("名称", ""),
            "price": float(r.get("最新价", 0)),
            "change_pct": float(r.get("涨跌幅", 0)),
            "change": float(r.get("涨跌额", 0)),
            "volume": float(r.get("成交量", 0)),
            "amount": float(r.get("成交额", 0)),
            "high": float(r.get("最高", 0)),
            "low": float(r.get("最低", 0)),
            "open": float(r.get("今开", 0)),
            "prev_close": float(r.get("昨收", 0)),
            "turnover": float(r.get("换手率", 0)),
            "pe": float(r.get("市盈率-动态", 0)) if r.get("市盈率-动态") else 0,
            "pb": float(r.get("市净率", 0)) if r.get("市净率") else 0,
            "total_mv": float(r.get("总市值", 0)),
            "circ_mv": float(r.get("流通市值", 0)),
        }
    except Exception as e:
        print(f"获取实时行情失败: {e}")
        return {}


def get_financial_basic(code: str) -> dict:
    """
    获取基本面关键指标（轻量版，适合短线参考）
    """
    result = {
        "pe": 0, "pb": 0, "roe": 0, "revenue_yoy": 0,
        "profit_yoy": 0, "gross_margin": 0, "debt_ratio": 0
    }
    try:
        # 实时行情里已经有PE/PB
        quote = get_realtime_quote(code)
        result["pe"] = quote.get("pe", 0)
        result["pb"] = quote.get("pb", 0)

        # 尝试获取财务指标
        try:
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[0]
                # 不同列名兼容
                for col in df.columns:
                    if "净资产收益率" in str(col):
                        result["roe"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "营业总收入" in str(col) and "同比" in str(col):
                        result["revenue_yoy"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "净利润" in str(col) and "同比" in str(col):
                        result["profit_yoy"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "毛利率" in str(col):
                        result["gross_margin"] = float(latest[col]) if pd.notna(latest[col]) else 0
                    elif "资产负债率" in str(col):
                        result["debt_ratio"] = float(latest[col]) if pd.notna(latest[col]) else 0
        except Exception:
            pass

    except Exception as e:
        print(f"获取基本面数据失败: {e}")

    return result


def get_hot_stocks() -> pd.DataFrame:
    """获取热门股票列表（涨幅榜前50）"""
    try:
        df = ak.stock_zh_a_spot_em()
        df = df.sort_values("涨跌幅", ascending=False).head(50)
        return df[["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]].reset_index(drop=True)
    except Exception as e:
        print(f"获取热门股票失败: {e}")
        return pd.DataFrame()
