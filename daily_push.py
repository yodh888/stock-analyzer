"""
自选股每日分析推送脚本。

环境变量:
    SERVERCHAN_KEY  Server酱 SendKey（与飞书二选一）
    FEISHU_WEBHOOK  飞书自定义机器人 Webhook（与Server酱二选一）
    FEISHU_SECRET   飞书机器人签名 Secret（可选）
    AI_API_KEY      AI API Key（可选）
    AI_PROVIDER     deepseek/kimi/qwen/openai
    AI_MODEL        可选，服务商模型名称
    AI_ENABLED      true/false
"""

import os
import re
import sys
import time
from datetime import datetime

from ai_analyzer import ai_analyze
from config import AI_MODEL, AI_PROVIDER, SHANGHAI_TZ, normalize_provider
from data_fetcher import (
    get_financial_basic,
    get_kline_data,
    get_stock_name,
    is_trade_day,
)
from pusher import push_to_feishu, push_to_serverchan
from signals import generate_comprehensive_signal


def load_watchlist(filepath: str = "watchlist.txt") -> list[str]:
    """读取自选股列表，支持空格、制表和逗号分隔。"""
    stocks = []
    if not os.path.exists(filepath):
        print(f"自选股文件不存在: {filepath}")
        return stocks

    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            code = re.split(r"[\s,]+", line, maxsplit=1)[0]
            if code.isdigit() and len(code) == 6 and code not in stocks:
                stocks.append(code)
    return stocks


def analyze_stock(
    code: str,
    ai_enabled: bool = False,
    api_key: str = "",
    provider: str = "deepseek",
    model: str = "",
) -> dict:
    """分析单只股票，网络异常时重试，数据不足时不重复请求。"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = get_kline_data(code, days=120)
            if df.empty:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {"code": code, "name": code, "error": "数据获取失败"}

            result = generate_comprehensive_signal(df)
            if "error" in result:
                return {
                    "code": code,
                    "name": get_stock_name(code),
                    "error": result["error"],
                }

            name = get_stock_name(code)
            financial = {}
            ai_text = ""
            if ai_enabled and api_key:
                financial = get_financial_basic(code)
                ai_result = ai_analyze(
                    name,
                    code,
                    result,
                    financial,
                    api_key,
                    provider,
                    model,
                )
                if ai_result.get("error"):
                    print(f"AI分析失败: {ai_result.get('error')}")
                    ai_text = "AI分析失败，请查看运行日志。"
                else:
                    ai_text = ai_result.get("text", "")

            return {
                "code": code,
                "name": name,
                "result": result,
                "ai_text": ai_text,
                "financial": financial,
            }
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"code": code, "name": code, "error": type(exc).__name__}
    return {"code": code, "name": code, "error": "重试次数耗尽"}

def _format_value(value, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value}{suffix}"


def format_push_report(results: list, now: datetime | None = None) -> str:
    """格式化Server酱日报。"""
    current = now or datetime.now(SHANGHAI_TZ)
    lines = [f"## 📈 自选股分析日报（{current:%Y-%m-%d %H:%M}）", ""]
    succeeded = sum(1 for item in results if "error" not in item)
    lines.append(f"成功 {succeeded}/{len(results)} 只")
    lines.append("")
    lines.append("### 🔍 一览")
    lines.append("")
    lines.append("| 股票 | 价格 | 涨跌 | 信号 | 得分 | 建议 |")
    lines.append("|------|------|------|------|------|------|")

    for item in results:
        if "error" in item:
            lines.append(f"| {item['name']}({item['code']}) | - | - | ❌获取失败 | - | - |")
            continue
        result = item["result"]
        lines.append(
            f"| {item['name']}({item['code']}) | {_format_value(result['latest_price'])} | "
            f"{_format_value(result['pct_change'], '%')} | "
            f"{result['emoji']}{result['suggestion']} | {result['total_score']} | "
            f"{result['action']} |"
        )

    lines.append("")
    for item in results:
        if "error" in item:
            lines.extend([
                f"### {item['name']}({item['code']})",
                f"❌ {item['error']}",
                "",
            ])
            continue

        result = item["result"]
        lines.append(
            f"### {item['name']}({item['code']}) {result['emoji']} {result['suggestion']}"
        )
        lines.append(
            f"- 最新价: {_format_value(result['latest_price'])} | "
            f"涨跌: {_format_value(result['pct_change'], '%')} | "
            f"换手: {_format_value(result['turnover'], '%')}"
        )
        lines.append(f"- 综合得分: {result['total_score']} | 操作建议: {result['action']}")
        lines.append(f"- {result['support_resistance']['desc']}")
        lines.append("")
        lines.append("**各维度信号:**")
        for detail in result["details"]:
            lines.append(f"- {detail['维度']}：{detail['信号']}（{detail['说明']}）")
        lines.append("")

        if item.get("ai_text"):
            lines.extend(["**🤖 AI解读:**", item["ai_text"], ""])

    lines.extend([
        "---",
        "⚠️ 以上分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。",
    ])
    return "\n".join(lines)

def main() -> int:
    print("=" * 50)
    print("自选股分析推送启动")
    print("=" * 50)

    force_run = os.getenv("FORCE_RUN", "false").strip().lower() == "true"
    if not force_run and not is_trade_day():
        print("今天是A股非交易日，跳过分析推送")
        return 0

    sendkey = os.getenv("SERVERCHAN_KEY", "").strip()
    feishu_webhook = os.getenv("FEISHU_WEBHOOK", "").strip()
    feishu_secret = os.getenv("FEISHU_SECRET", "").strip()
    ai_key = os.getenv("AI_API_KEY", "").strip()
    ai_provider = normalize_provider(os.getenv("AI_PROVIDER", "") or AI_PROVIDER)
    ai_model = (os.getenv("AI_MODEL", "") or AI_MODEL).strip()
    ai_enabled = os.getenv("AI_ENABLED", "false").strip().lower() == "true"

    if ai_enabled and not ai_key:
        print("⚠️ 已启用AI但未设置 AI_API_KEY，将使用纯规则版")
        ai_enabled = False

    channels = []
    if feishu_webhook:
        channels.append("飞书")
    if sendkey:
        channels.append("Server酱")
    print(
        f"配置: AI={'开启(' + ai_provider + '/' + (ai_model or '默认模型') + ')' if ai_enabled else '关闭'}, "
        f"推送={','.join(channels) if channels else '关闭'}"
    )

    stocks = load_watchlist()
    if not stocks:
        print("自选股列表为空，请在 watchlist.txt 中添加股票代码")
        return 1

    print(f"待分析股票: {len(stocks)} 只 - {stocks}")
    results = []
    for index, code in enumerate(stocks, 1):
        print(f"[{index}/{len(stocks)}] 分析 {code}...")
        result = analyze_stock(code, ai_enabled, ai_key, ai_provider, ai_model)
        results.append(result)
        if "error" not in result:
            print(f"  ✓ {result['name']}: {result['result']['emoji']} {result['result']['suggestion']}")
        else:
            print(f"  ✗ 失败: {result['error']}")
        time.sleep(1)

    report = format_push_report(results)
    print("\n" + "=" * 50)
    print("分析报告:")
    print("=" * 50)
    print(report)

    successful = sum(1 for item in results if "error" not in item)
    if successful == 0:
        print("❌ 所有股票均分析失败，任务返回非零状态")
        return 1

    title = f"自选股日报 {datetime.now(SHANGHAI_TZ):%m-%d}"
    push_failed = False
    if feishu_webhook:
        if push_to_feishu(feishu_webhook, title, report, feishu_secret):
            print("✓ 飞书推送成功")
        else:
            print("❌ 飞书推送失败")
            push_failed = True
    if sendkey:
        if push_to_serverchan(sendkey, title, report):
            print("✓ Server酱推送成功")
        else:
            print("❌ Server酱推送失败")
            push_failed = True
    if push_failed:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
