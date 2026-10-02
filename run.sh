#!/usr/bin/env bash
# A股智能分析工具 - 启动脚本 (Linux/Mac)
set -euo pipefail

cd "$(dirname "$0")"

echo "========================================="
echo "  A股智能分析工具 启动中..."
echo "========================================="

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "📦 首次运行，创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "📦 检查依赖..."
python -m pip install -q -r requirements.txt

echo ""
echo "✅ 启动成功！"
echo "📱 手机访问时请确保手机和电脑在同一WiFi下"
echo "   已启用 CORS/XSRF 防护，公网部署必须额外配置 TLS 和鉴权。"
echo ""

streamlit run app.py --server.address 0.0.0.0 --server.port 8501
