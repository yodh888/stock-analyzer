"""A股智能分析工具配置。"""

import os
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MIN_ANALYSIS_BARS = 60

# ============ AI 大模型配置 ============
DEFAULT_AI_PROVIDER = "deepseek"
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


def normalize_provider(value: str | None) -> str:
    """把环境变量中的服务商名称规范化。"""
    provider = (value or "").strip().lower()
    return provider if provider in API_BASES else DEFAULT_AI_PROVIDER


AI_PROVIDER = normalize_provider(os.getenv("AI_PROVIDER"))
AI_MODEL = os.getenv("AI_MODEL", "").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_ENABLED = os.getenv("AI_ENABLED", "false").strip().lower() == "true"
MAX_OUTPUT_TOKENS = 1500
AI_CONNECT_TIMEOUT = 5
AI_READ_TIMEOUT = 30
AI_MAX_RETRIES = 3


# ============ 数据配置 ============
KLINE_DAYS = 120
REFRESH_INTERVAL = 60


# ============ 推送配置（可选）============
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK", "")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
FEISHU_SECRET = os.getenv("FEISHU_SECRET", "")
PUSHDEER_PUSHKEY = os.getenv("PUSHDEER_PUSHKEY", "")
PUSHDEER_API_URL = (
    os.getenv("PUSHDEER_API_URL", "").strip()
    or "https://api2.pushdeer.com/message/push"
)
