"""
A股智能分析工具 - 主界面
运行: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

import config
from data_fetcher import get_kline_data, get_realtime_quote, get_financial_basic, get_stock_name, get_hot_stocks
from indicators import calculate_all_indicators
from signals import generate_comprehensive_signal, format_signal_text
from ai_analyzer import ai_analyze, calculate_cost, estimate_tokens
from pusher import push_result

# ============ 页面配置 ============
st.set_page_config(
    page_title="A股智能分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ 侧边栏：配置 ============
with st.sidebar:
    st.header("⚙️ 设置")

    # AI配置
    st.subheader("AI 分析设置")
    ai_enabled = st.toggle("启用 AI 辅助解读", value=False,
                          help="开启后每次分析会调用大模型，约0.01-0.05元/次")

    api_key = st.text_input("API Key", type="password",
                           value=st.session_state.get("api_key", config.AI_API_KEY),
                           help="DeepSeek/Kimi/通义千问的API Key")

    provider = st.selectbox("AI服务商", ["deepseek", "kimi", "qwen", "openai"],
                           index=["deepseek", "kimi", "qwen", "openai"].index(config.AI_PROVIDER))

    if ai_enabled:
        # 显示成本预估
        st.caption(f"预计单次成本: 约0.01-0.03元（{provider}）")

    st.divider()

    # 推送配置
    st.subheader("推送设置（可选）")
    push_enabled = st.toggle("启用推送", value=False)
    if push_enabled:
        push_type = st.selectbox("推送方式", ["wecom", "serverchan", "pushplus"])
        push_token = st.text_input("推送 Token/Webhook", type="password")

# ============ 主区域 ============
st.title("📈 A股智能分析工具")
st.caption("技术面 + 轻量基本面 + AI辅助解读 | 仅供参考，不构成投资建议")

# ============ 输入区 ============
col1, col2 = st.columns([2, 1])
with col1:
    stock_code = st.text_input("输入股票代码（如 600519、000001、300750）",
                              value="", placeholder="例如：600519")
with col2:
    kline_days = st.selectbox("K线周期", [60, 120, 250], index=1,
                             format_func=lambda x: f"{x}个交易日")

analyze_btn = st.button("🔍 开始分析", type="primary", use_container_width=True)

# 热门股票快捷入口
with st.expander("🔥 热门股票（涨幅榜）", expanded=False):
    try:
        hot = get_hot_stocks()
        if not hot.empty:
            st.dataframe(hot, use_container_width=True, hide_index=True)
        else:
            st.write("暂无数据")
    except Exception as e:
        st.error(f"获取热门股票失败: {e}")

st.divider()

# ============ 分析逻辑 ============
if analyze_btn and stock_code:
    stock_code = stock_code.strip()
    if not stock_code.isdigit() or len(stock_code) != 6:
        st.error("请输入正确的6位股票代码")
        st.stop()

    with st.spinner("正在获取数据并分析..."):
        # 1. 获取数据
        try:
            df = get_kline_data(stock_code, days=kline_days)
        except Exception as e:
            st.error(f"获取K线数据失败: {e}")
            st.stop()

        if df.empty:
            st.error("未获取到数据，请检查股票代码或网络")
            st.stop()

        try:
            stock_name = get_stock_name(stock_code)
            realtime = get_realtime_quote(stock_code)
        except Exception as e:
            stock_name = stock_code
            realtime = {}

        # 2. 计算指标并生成信号
        result = generate_comprehensive_signal(df)

        # 3. 获取基本面
        try:
            financial = get_financial_basic(stock_code)
        except Exception:
            financial = {}

    # ============ 显示结果 ============

    # 顶部：核心结论
    st.subheader(f"{result['emoji']} {stock_name}({stock_code})")
    col_price, col_suggest, col_action = st.columns(3)
    with col_price:
        st.metric("最新价", f"{result['latest_price']}",
                 f"{result['pct_change']}%")
    with col_suggest:
        st.metric("综合判断", f"{result['suggestion']}",
                 f"得分 {result['total_score']}")
    with col_action:
        st.metric("操作建议", result['action'])

    # 实时行情补充
    if realtime:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("今开", f"{realtime.get('open', 0)}")
        col2.metric("最高/最低", f"{realtime.get('high', 0)} / {realtime.get('low', 0)}")
        col3.metric("换手率", f"{realtime.get('turnover', 0)}%")
        col4.metric("成交额(亿)", f"{realtime.get('amount', 0)/1e8:.1f}")

    st.divider()

    # K线图
    st.subheader("📊 K线图与技术指标")
    df_ind = calculate_all_indicators(df)
    plot_df = df_ind.tail(60).copy()

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                       vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])

    # K线
    fig.add_trace(go.Candlestick(
        x=plot_df["date"], open=plot_df["open"], high=plot_df["high"],
        low=plot_df["low"], close=plot_df["close"], name="K线"
    ), row=1, col=1)

    # 均线
    for ma, color in [("ma5", "#FF6B6B"), ("ma10", "#4ECDC4"), ("ma20", "#45B7D1"), ("ma60", "#96CEB4")]:
        if ma in plot_df.columns:
            fig.add_trace(go.Scatter(
                x=plot_df["date"], y=plot_df[ma], name=ma.upper(),
                line=dict(width=1, color=color)
            ), row=1, col=1)

    # 成交量
    colors = ["#EF5350" if c >= o else "#26A69A"
              for c, o in zip(plot_df["close"], plot_df["open"])]
    fig.add_trace(go.Bar(
        x=plot_df["date"], y=plot_df["volume"], name="成交量",
        marker_color=colors
    ), row=2, col=1)

    # MACD
    if "macd" in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df["date"], y=plot_df["macd"], name="MACD",
            line=dict(color="#4ECDC4")
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=plot_df["date"], y=plot_df["macd_signal"], name="Signal",
            line=dict(color="#FF6B6B")
        ), row=3, col=1)
        fig.add_trace(go.Bar(
            x=plot_df["date"], y=plot_df["macd_hist"], name="MACD柱",
            marker_color=["#EF5350" if v >= 0 else "#26A69A" for v in plot_df["macd_hist"]]
        ), row=3, col=1)

    fig.update_layout(
        height=600, xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ============ 各维度信号详情 ============
    st.subheader("📋 各维度信号")
    details_df = pd.DataFrame(result["details"])
    st.dataframe(details_df, use_container_width=True, hide_index=True)

    # 支撑阻力
    st.info(f"📍 {result['support_resistance']['desc']}")

    # K线形态
    with st.expander("🕯️ K线形态识别", expanded=True):
        for p in result["patterns"]:
            emoji = "🟢" if p["signal"] == "看多" else ("🔴" if p["signal"] == "看空" else "🟡")
            st.markdown(f"**{emoji} {p['name']}**：{p['desc']}")

    # ============ AI 分析 ============
    if ai_enabled and api_key:
        st.divider()
        st.subheader("🤖 AI 智能解读")
        with st.spinner("AI正在分析中..."):
            ai_result = ai_analyze(stock_name, stock_code, result, financial,
                                  api_key, provider)
        st.markdown(ai_result["text"])
        st.caption(f"模型: {ai_result.get('model', '')} | "
                  f"输入token: {ai_result.get('input_tokens', 0)} | "
                  f"输出token: {ai_result.get('output_tokens', 0)} | "
                  f"本次成本: 约{ai_result.get('cost', 0)}元")
    elif ai_enabled and not api_key:
        st.warning("已开启AI分析，但未填写API Key")

    # ============ 推送 ============
    if push_enabled and push_type and push_token:
        st.divider()
        if st.button("📱 推送分析结果到手机"):
            ai_text = ""
            if ai_enabled and api_key:
                ai_text = ai_result.get("text", "")
            success = push_result(push_type, push_token, stock_name, stock_code,
                                 result, ai_text)
            if success:
                st.success("推送成功！请查看手机")
            else:
                st.error("推送失败，请检查Token配置")

    # ============ 文本报告 ============
    st.divider()
    with st.expander("📄 完整文本报告（可复制）", expanded=False):
        report = format_signal_text(result, stock_name, stock_code)
        if ai_enabled and api_key:
            report += f"\n\n【AI解读】\n{ai_result.get('text', '')}"
        st.text_area("分析报告", report, height=400)

elif not analyze_btn:
    # 首页提示
    st.info("👆 请输入股票代码并点击「开始分析」")

    # 功能说明
    st.subheader("功能说明")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **技术面分析**
        - 均线系统（MA5/10/20/60）
        - MACD / KDJ / RSI
        - 布林带 / 成交量
        - K线形态识别
        - 支撑阻力位
        """)
    with col2:
        st.markdown("""
        **AI 辅助解读**
        - 综合多维度信号
        - 自然语言分析
        - 可操作的买卖建议
        - 成本可控（约0.01-0.03元/次）

        **推送（可选）**
        - 企业微信 / Server酱 / PushPlus
        """)

    st.caption("⚠️ 本工具仅供学习研究，不构成任何投资建议。股市有风险，投资需谨慎。")
