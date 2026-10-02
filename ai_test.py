"""AI 连接测试脚本，只发送一个最小请求，不读取行情或发送微信。"""

import logging
import os
import sys

from ai_analyzer import test_ai_connection
from config import AI_MODEL, AI_PROVIDER

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)


def main() -> int:
    api_key = os.getenv("AI_API_KEY", "").strip()
    provider = os.getenv("AI_PROVIDER", "").strip() or AI_PROVIDER
    model = os.getenv("AI_MODEL", "").strip() or AI_MODEL

    print("=" * 50)
    print("AI 连接测试")
    print("=" * 50)
    print(f"服务商: {provider}")
    print(f"模型: {model or '使用服务商默认模型'}")

    result = test_ai_connection(api_key, provider=provider, model=model or None)
    print(f"状态: {'成功' if result.get('ok') else '失败'}")
    print(f"耗时: {result.get('latency_ms', 0)} ms")
    print(f"信息: {result.get('message', '')}")

    if not result.get("ok"):
        error = result.get("error") or "unknown_error"
        status_code = result.get("status_code")
        print(f"错误类型: {error}")
        if status_code is not None:
            print(f"HTTP状态码: {status_code}")
        return 1

    print("AI_API_KEY、服务商和模型配置有效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
