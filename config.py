"""A股智能分析工具配置。"""

import os
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MIN_ANALYSIS_BARS = 60

# ============ AI 大模型配置 ============
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek").strip().lower()
API_BASES = {
    "deepseek": "https://api.deepseek.com/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
}
DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "kimi": "moonshot-v1-8k",
    "qwen": "qwen-turbo",
    "openai": "gpt-4o-mini",
}
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_ENABLED = os.getenv("AI_ENABLED", "false").strip().lower() == "true"
MAX_OUTPUT_TOKENS = 1500


# ============ 数据配置 ============
KLINE_DAYS = 120
REFRESH_INTERVAL = 60


# ============ 推送配置（可选）============
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK", "")
