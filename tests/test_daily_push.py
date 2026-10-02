from datetime import datetime
from zoneinfo import ZoneInfo

from daily_push import format_push_report, format_pushdeer_report, load_watchlist


def test_load_watchlist_supports_tabs_commas_and_duplicates(tmp_path):
    path = tmp_path / "watchlist.txt"
    path.write_text(
        "# comment\n600519 贵州茅台\n000001,平安银行\n300750\t宁德时代\n600519\n",
        encoding="utf-8",
    )
    assert load_watchlist(str(path)) == ["600519", "000001", "300750"]


def test_format_push_report_uses_shanghai_time():
    result = {
        "latest_price": 10.0,
        "pct_change": 1.2,
        "turnover": None,
        "emoji": "🟢",
        "suggestion": "偏多",
        "total_score": 2.1,
        "action": "观察",
        "support_resistance": {"desc": "支撑位9.5"},
        "details": [{"维度": "均线", "信号": "看多", "说明": "测试"}],
    }
    report = format_push_report(
        [{"code": "600519", "name": "贵州茅台", "result": result, "ai_text": ""}],
        now=datetime(2026, 10, 2, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert "2026-10-02 15:30" in report
    assert "换手: N/A" in report


def test_format_pushdeer_report_is_mobile_friendly():
    result = {
        "latest_price": 10.0,
        "pct_change": 1.2,
        "turnover": 2.3,
        "emoji": "🟢",
        "suggestion": "偏多",
        "total_score": 2.1,
        "action": "观察",
        "support_resistance": {"desc": "支撑位9.5，阻力位11.0"},
        "details": [
            {"维度": "均线", "信号": "看多", "说明": "解释文字"},
            {"维度": "MACD", "信号": "中性", "说明": "解释文字"},
        ],
    }
    report = format_pushdeer_report(
        [
            {
                "code": "600519",
                "name": "贵州茅台",
                "result": result,
                "ai_text": "仅供观察。",
            }
        ],
        now=datetime(2026, 10, 2, 16, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert "|" not in report
    assert "【1】贵州茅台 600519" in report
    assert "关键信号" in report
    assert "AI解读" in report
    assert "时间：2026-10-02 16:00" in report
