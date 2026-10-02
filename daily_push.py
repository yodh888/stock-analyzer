"""
自选股每日分析推送脚本
- 读取 watchlist.txt 中的自选股
- 对每只股票进行技术面分析
- 通过 Server酱 推送到微信
- 支持可选 AI 辅助解读

使用方式：
    python daily_push.py

环境变量配置：
    SERVERCHAN_KEY  - Server酱的SendKey（必填，用于推送）
    AI_API_KEY      - AI大模型API Key（可选，不填则只用规则版）
    AI_PROVIDER     - AI服务商（deepseek/kimi/qwen/openai，默认deepseek）
    AI_ENABLED      - 是否启用AI（true/false，默认false）
"""
import os
import sys
import time
import datetime
import requests

# 将当前目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_kline_data, get_stock_name, get_financial_basic
from signals import generate_comprehensive_signal, format_signal_text
from ai_analyzer import ai_analyze


def load_watchlist(filepath: str = "watchlist.txt") -> list:
    """读取自选股列表"""
    stocks = []
    if not os.path.exists(filepath):
        print(f"自选股文件不存在: {filepath}")
        return stocks
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 取第一个空格前的代码
            code = line.split()[0] if " " in line else line.split(",")[0]
            if code.isdigit() and len(code) == 6:
                stocks.append(code)
    return stocks


def analyze_stock(code: str, ai_enabled: bool = False, api_key: str = "",
                  provider: str = "deepseek") -> dict:
    """分析单只股票（含重试机制）"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = get_kline_data(code, days=120)
            if df.empty:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {"code": code, "name": code, "error": "数据获取失败"}

            name = get_stock_name(code)
            result = generate_comprehensive_signal(df)

            # 基本面
            try:
                financial = get_financial_basic(code)
            except Exception:
                financial = {}

            # AI分析（可选）
            ai_text = ""
            if ai_enabled and api_key:
                try:
                    ai_result = ai_analyze(name, code, result, financial, api_key, provider)
                    ai_text = ai_result.get("text", "")
                except Exception as e:
                    ai_text = f"AI分析失败: {e}"

            return {
                "code": code,
                "name": name,
                "result": result,
                "ai_text": ai_text,
                "financial": financial,
            }
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"code": code, "name": code, "error": str(e)}
    return {"code": code, "name": code, "error": "重试次数耗尽"}


def format_push_report(results: list, ai_enabled: bool) -> str:
    """格式化推送报告（Markdown格式，适配Server酱）"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## 📈 自选股分析日报（{now}）", ""]

    # 汇总表
    lines.append("### 🔍 一览")
    lines.append("")
    lines.append("| 股票 | 价格 | 涨跌 | 信号 | 得分 | 建议 |")
    lines.append("|------|------|------|------|------|------|")

    for r in results:
        if "error" in r:
            lines.append(f"| {r['name']}({r['code']}) | - | - | ❌获取失败 | - | - |")
            continue
        res = r["result"]
        emoji = res["emoji"]
        lines.append(
            f"| {r['name']}({r['code']}) | {res['latest_price']} | "
            f"{res['pct_change']}% | {emoji}{res['suggestion']} | "
            f"{res['total_score']} | {res['action']} |"
        )

    lines.append("")

    # 详细分析
    for r in results:
        if "error" in r:
            lines.append(f"### {r['name']}({r['code']})")
            lines.append(f"❌ {r['error']}")
            lines.append("")
            continue

        res = r["result"]
        lines.append(f"### {r['name']}({r['code']}) {res['emoji']} {res['suggestion']}")
        lines.append(f"- 最新价: {res['latest_price']} | 涨跌: {res['pct_change']}% | 换手: {res['turnover']}%")
        lines.append(f"- 综合得分: {res['total_score']} | 操作建议: {res['action']}")
        lines.append(f"- {res['support_resistance']['desc']}")
        lines.append("")
        lines.append("**各维度信号:**")
        for d in res["details"]:
            lines.append(f"- {d['维度']}：{d['信号']}（{d['说明']}）")
        lines.append("")

        if r.get("ai_text"):
            lines.append("**🤖 AI解读:**")
            lines.append(r["ai_text"])
            lines.append("")

    lines.append("---")
    lines.append("⚠️ 以上分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。")

    return "\n".join(lines)


def push_to_serverchan(sendkey: str, title: str, content: str) -> bool:
    """推送到Server酱"""
    if not sendkey:
        print("未配置 SERVERCHAN_KEY，跳过推送")
        return False
    try:
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=15)
        result = resp.json()
        if result.get("code") == 0:
            print(f"推送成功: {title}")
            return True
        else:
            print(f"推送失败: {result}")
            return False
    except Exception as e:
        print(f"推送异常: {e}")
        return False


def main():
    print("=" * 50)
    print("自选股分析推送启动")
    print("=" * 50)

    # 读取配置
    sendkey = os.getenv("SERVERCHAN_KEY", "")
    ai_key = os.getenv("AI_API_KEY", "")
    ai_provider = os.getenv("AI_PROVIDER", "deepseek")
    ai_enabled = os.getenv("AI_ENABLED", "false").lower() == "true"

    if not sendkey:
        print("⚠️  未设置 SERVERCHAN_KEY，将只输出到控制台不推送")

    if ai_enabled and not ai_key:
        print("⚠️  已启用AI但未设置 AI_API_KEY，将使用纯规则版")
        ai_enabled = False

    print(f"配置: AI={'开启('+ai_provider+')' if ai_enabled else '关闭'}, 推送={'开启' if sendkey else '关闭'}")

    # 读取自选股
    stocks = load_watchlist()
    if not stocks:
        print("自选股列表为空，请在 watchlist.txt 中添加股票代码")
        return

    print(f"待分析股票: {len(stocks)} 只 - {stocks}")

    # 逐只分析
    results = []
    for i, code in enumerate(stocks, 1):
        print(f"[{i}/{len(stocks)}] 分析 {code}...")
        result = analyze_stock(code, ai_enabled, ai_key, ai_provider)
        results.append(result)
        if "error" not in result:
            print(f"  ✓ {result['name']}: {result['result']['emoji']} {result['result']['suggestion']}")
        else:
            print(f"  ✗ 失败: {result['error']}")
        time.sleep(1)  # 避免请求过快

    # 生成报告
    report = format_push_report(results, ai_enabled)

    # 输出到控制台
    print("\n" + "=" * 50)
    print("分析报告:")
    print("=" * 50)
    print(report)

    # 推送
    if sendkey:
        title = f"自选股日报 {datetime.datetime.now().strftime('%m-%d')}"
        push_to_serverchan(sendkey, title, report)


if __name__ == "__main__":
    main()
