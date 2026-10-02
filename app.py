"""A股智能分析工具 - Streamlit 主界面。"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from ai_analyzer import ai_analyze, test_ai_connection
from data_fetcher import (
    get_financial_basic,
    get_hot_stocks,
    get_kline_data,
    get_realtime_quote,
    get_stock_name,
)
from indicators import calculate_all_indicators
from pusher import push_result
from signals import format_signal_text, generate_comprehensive_signal

st.set_page_config(
    page_title="A股智能分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=300, show_spinner=False)
def load_kline_data(code: str, days: int) -> pd.DataFrame:
    return get_kline_data(code, days=days)


@st.cache_data(ttl=300, show_spinner=False)
def load_stock_name(code: str) -> str:
    return get_stock_name(code)


@st.cache_data(ttl=60, show_spinner=False)
def load_realtime_quote(code: str) -> dict:
    return get_realtime_quote(code)


@st.cache_data(ttl=1800, show_spinner=False)
def load_financial_basic(code: str) -> dict:
    return get_financial_basic(code)


@st.cache_data(ttl=300, show_spinner=False)
def load_hot_stocks() -> pd.DataFrame:
    return get_hot_stocks()


def _display_value(value, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"

# ============ 侧边栏配置 ============
with st.sidebar:
    st.header("⚙️ 设置")
    st.subheader("AI 分析设置")
    ai_enabled = st.toggle(
        "启用 AI 辅助解读",
        value=config.AI_ENABLED,
        help="开启后每次分析会调用大模型，约0.01-0.05元/次",
    )
    api_key = st.text_input(
        "API Key",
        type="password",
        value=config.AI_API_KEY,
        help="DeepSeek/Kimi/通义千问/OpenAI的API Key",
    )

    providers = list(config.API_BASES)
    default_provider = (
        config.AI_PROVIDER if config.AI_PROVIDER in providers else config.DEFAULT_AI_PROVIDER
    )
    provider = st.selectbox("AI服务商", providers, index=providers.index(default_provider))
    default_model = config.AI_MODEL or config.DEFAULT_MODELS[provider]
    model = st.text_input(
        "模型名称",
        value=default_model,
        key=f"ai_model_{provider}",
        help="可以填写服务商支持的模型名称",
    )

    if ai_enabled and api_key and st.button("测试 AI 连接", width="stretch"):
        with st.spinner("正在测试 AI 连接..."):
            connection = test_ai_connection(api_key, provider=provider, model=model)
        if connection.get("ok"):
            st.success(
                f"连接成功：{connection['provider']} / {connection['model']} "
                f"({connection['latency_ms']} ms)"
            )
        else:
            status_code = connection.get("status_code")
            detail = f"，HTTP {status_code}" if status_code else ""
            st.error(f"{connection.get('message', '连接失败')}{detail}")

    st.divider()
    st.subheader("推送设置（可选）")
    push_enabled = st.toggle("启用推送", value=False)
    push_type = None
    push_token = ""
    push_secret = ""
    push_endpoint = ""
    if push_enabled:
        push_type = st.selectbox(
            "推送方式",
            ["feishu", "pushdeer", "wecom", "serverchan", "pushplus"],
        )
        token_label = {
            "feishu": "飞书 Webhook",
            "pushdeer": "PushDeer PushKey",
        }.get(push_type, "推送 Token/Webhook")
        push_token = st.text_input(token_label, type="password")
        if push_type == "feishu":
            push_secret = st.text_input(
                "飞书签名 Secret（可选）",
                type="password",
                value=config.FEISHU_SECRET,
            )
        if push_type == "pushdeer":
            push_endpoint = st.text_input(
                "PushDeer API地址",
                value=config.PUSHDEER_API_URL,
            )


# ============ 主界面 ============
st.title("📈 A股智能分析工具")
st.caption("技术面 + 轻量基本面 + AI辅助解读 | 仅供参考，不构成投资建议")

input_column, period_column = st.columns([2, 1])
with input_column:
    stock_code = st.text_input(
        "输入股票代码（如 600519、000001、300750）",
        value="",
        placeholder="例如：600519",
    )
with period_column:
    kline_days = st.selectbox(
        "K线周期",
        [60, 120, 250],
        index=1,
        format_func=lambda value: f"{value}个交易日",
    )

analyze_btn = st.button("🔍 开始分析", type="primary", width="stretch")

with st.expander("🔥 热门股票（涨幅榜）", expanded=False):
    hot = load_hot_stocks()
    if not hot.empty:
        st.dataframe(hot, width="stretch", hide_index=True)
    else:
        st.write("暂无数据")

st.divider()

if analyze_btn:
    stock_code = stock_code.strip()
    if not stock_code.isdigit() or len(stock_code) != 6:
        st.error("请输入正确的6位股票代码")
        st.stop()

    with st.spinner("正在获取数据并分析..."):
        try:
            df = load_kline_data(stock_code, kline_days)
        except Exception as exc:
            st.error(f"获取K线数据失败: {type(exc).__name__}")
            st.stop()

        if df.empty:
            st.error("未获取到数据，请检查股票代码或网络")
            st.stop()

        result = generate_comprehensive_signal(df)
        if result.get("error"):
            st.error(result["error"])
            st.stop()

        try:
            stock_name = load_stock_name(stock_code)
            realtime = load_realtime_quote(stock_code)
        except Exception:
            stock_name = stock_code
            realtime = {}

        financial = {}
        ai_text = ""
        ai_error = ""
        if ai_enabled and api_key:
            try:
                financial = load_financial_basic(stock_code)
            except Exception:
                financial = {}
            ai_result = ai_analyze(
                stock_name,
                stock_code,
                result,
                financial,
                api_key,
                provider,
                model,
            )
            ai_text = ai_result.get("text", "")
            ai_error = ai_result.get("error", "")

    st.session_state["analysis"] = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "kline_days": kline_days,
        "df": df,
        "realtime": realtime,
        "result": result,
        "ai_text": ai_text,
        "ai_error": ai_error,
        "ai_provider": provider,
        "ai_model": model,
    }

analysis = st.session_state.get("analysis")

if analysis:
    state_code = analysis["stock_code"]
    state_name = analysis["stock_name"]
    df = analysis["df"]
    realtime = analysis["realtime"]
    result = analysis["result"]
    ai_text = analysis["ai_text"]
    ai_error = analysis["ai_error"]
    ai_provider = analysis.get("ai_provider", provider)
    ai_model = analysis.get("ai_model", model)

    st.subheader(f"{result['emoji']} {state_name}({state_code})")
    price_column, suggest_column, action_column = st.columns(3)
    with price_column:
        st.metric(
            "最新价",
            _display_value(result["latest_price"]),
            _display_value(result["pct_change"], suffix="%"),
        )
    with suggest_column:
        st.metric("综合判断", result["suggestion"], f"得分 {result['total_score']}")
    with action_column:
        st.metric("操作建议", result["action"])

    if realtime:
        metrics = st.columns(4)
        metrics[0].metric("今开", _display_value(realtime.get("open")))
        metrics[1].metric(
            "最高/最低",
            f"{_display_value(realtime.get('high'))} / {_display_value(realtime.get('low'))}",
        )
        metrics[2].metric("换手率", _display_value(realtime.get("turnover"), suffix="%"))
        amount = realtime.get("amount")
        metrics[3].metric(
            "成交额(亿)",
            "N/A" if amount is None else f"{amount / 1e8:.1f}",
        )

    st.divider()
    st.subheader("📊 K线图与技术指标")
    indicator_df = calculate_all_indicators(df)
    plot_df = indicator_df.tail(60).copy()

    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.25, 0.25],
    )
    figure.add_trace(
        go.Candlestick(
            x=plot_df["date"],
            open=plot_df["open"],
            high=plot_df["high"],
            low=plot_df["low"],
            close=plot_df["close"],
            name="K线",
        ),
        row=1,
        col=1,
    )

    for moving_average, color in [
        ("ma5", "#FF6B6B"),
        ("ma10", "#4ECDC4"),
        ("ma20", "#45B7D1"),
        ("ma60", "#96CEB4"),
    ]:
        figure.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df[moving_average],
                name=moving_average.upper(),
                line={"width": 1, "color": color},
            ),
            row=1,
            col=1,
        )

    colors = [
        "#EF5350" if close >= open_ else "#26A69A"
        for close, open_ in zip(plot_df["close"], plot_df["open"])
    ]
    figure.add_trace(
        go.Bar(
            x=plot_df["date"],
            y=plot_df["volume"],
            name="成交量",
            marker_color=colors,
        ),
        row=2,
        col=1,
    )

    for column, name, color in [
        ("macd", "MACD", "#4ECDC4"),
        ("macd_signal", "Signal", "#FF6B6B"),
    ]:
        figure.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df[column],
                name=name,
                line={"color": color},
            ),
            row=3,
            col=1,
        )
    figure.add_trace(
        go.Bar(
            x=plot_df["date"],
            y=plot_df["macd_hist"],
            name="MACD柱",
            marker_color=["#EF5350" if value >= 0 else "#26A69A" for value in plot_df["macd_hist"]],
        ),
        row=3,
        col=1,
    )

    figure.update_layout(
        height=600,
        xaxis_rangeslider_visible=False,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(figure, width="stretch")

    st.subheader("📋 各维度信号")
    st.dataframe(
        pd.DataFrame(result["details"]),
        width="stretch",
        hide_index=True,
    )
    st.info(f"📍 {result['support_resistance']['desc']}")

    with st.expander("🕯️ K线形态识别", expanded=True):
        for pattern in result["patterns"]:
            emoji = (
                "🟢"
                if pattern["signal"] == "看多"
                else ("🔴" if pattern["signal"] == "看空" else "🟡")
            )
            st.markdown(f"**{emoji} {pattern['name']}**：{pattern['desc']}")

    if ai_text:
        st.divider()
        st.subheader("🤖 AI 智能解读")
        st.caption(f"服务商: {ai_provider} | 模型: {ai_model}")
        st.markdown(ai_text)
    elif ai_error:
        st.warning("AI分析失败，规则信号不受影响。")
    elif ai_enabled and not api_key:
        st.warning("已开启AI分析，但未填写API Key")

    if push_enabled and push_type and push_token:
        st.divider()
        if st.button("📱 推送分析结果到手机"):
            success = push_result(
                push_type,
                push_token,
                state_name,
                state_code,
                result,
                ai_text,
                push_secret=push_secret,
                push_endpoint=push_endpoint,
            )
            if success:
                st.success("推送成功，请查看手机")
            else:
                st.error("推送失败，请检查Token配置或查看服务日志")

    st.divider()
    with st.expander("📄 完整文本报告（可复制）", expanded=False):
        report = format_signal_text(result, state_name, state_code)
        if ai_text:
            report += f"\n\n【AI解读】\n{ai_text}"
        st.text_area("分析报告", report, height=400)

    if st.button("清除当前分析"):
        del st.session_state["analysis"]
        st.rerun()

elif not analyze_btn:
    st.info("👆 请输入股票代码并点击「开始分析」")
    st.subheader("功能说明")
    left, right = st.columns(2)
    with left:
        st.markdown("""
        **技术面分析**
        - 均线系统（MA5/10/20/60）
        - MACD / KDJ / RSI
        - 布林带 / 成交量
        - K线形态识别
        - 支撑阻力位
        """)
    with right:
        st.markdown("""
        **AI 辅助解读**
        - 综合多维度信号
        - 自然语言分析
        - 条件式观察建议
        - 成本可控

        **推送（可选）**
        - 飞书 / PushDeer / 企业微信 / Server酱 / PushPlus
        """)
    st.caption("⚠️ 本工具仅供学习研究，不构成任何投资建议。股市有风险，投资需谨慎。")
