#!/bin/bash
# A股智能分析工具 - 启动脚本 (Linux/Mac)
# 用法: bash run.sh

cd "$(dirname "$0")"

echo "========================================="
echo "  A股智能分析工具 启动中..."
echo "========================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 安装依赖（如果requirements.txt有更新）
if [ ! -d "venv" ]; then
    echo "📦 首次运行，创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "📦 检查依赖..."
pip install -q -r requirements.txt

echo ""
echo "✅ 启动成功！"
echo "📱 在手机上使用：请确保手机和电脑在同一WiFi下"
echo "   然后在手机浏览器访问下方显示的 Network URL"
echo ""

# 启动，允许局域网访问
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 \
  --server.enableCORS false --server.enableXsrfProtection false
