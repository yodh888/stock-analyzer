"""
配置文件 - A股智能分析工具
所有敏感信息建议在界面上输入，不要硬编码在这里
"""
import os

# ============ AI 大模型配置 ============
# 支持的服务商: deepseek / kimi / qwen / openai
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")

# 各服务商API地址
API_BASES = {
    "deepseek": "https://api.deepseek.com/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
}

# 各服务商默认模型
DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "kimi": "moonshot-v1-8k",
    "qwen": "qwen-turbo",
    "openai": "gpt-4o-mini",
}

# API Key（建议在界面输入，也可设环境变量）
AI_API_KEY = os.getenv("AI_API_KEY", "")

# ============ 成本控制 ============
# 每次AI分析最大token数（控制成本，默认1500足够输出精炼分析）
MAX_OUTPUT_TOKENS = 1500
# 是否启用AI分析（界面可切换）
AI_ENABLED = False

# ============ 数据配置 ============
# K线数据获取天数
KLINE_DAYS = 120
# 实时数据刷新间隔（秒）
REFRESH_INTERVAL = 60

# ============ 推送配置（可选）============
# 企业微信机器人webhook（留空则不推送）
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK", "")
