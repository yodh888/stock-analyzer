@echo off
chcp 65001 >nul
REM A股智能分析工具 - 启动脚本 (Windows)

cd /d "%~dp0"

echo =========================================
echo   A股智能分析工具 启动中...
echo =========================================

python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 python，请先安装 Python 3.11+
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist venv (
    echo 📦 首次运行，创建虚拟环境...
    python -m venv venv
    if errorlevel 1 exit /b 1
)

call venv\Scripts\activate
if errorlevel 1 exit /b 1

echo 📦 检查依赖...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)

echo.
echo ✅ 启动成功！
echo 📱 手机访问时请确保手机和电脑在同一WiFi下
echo    已启用 CORS/XSRF 防护，公网部署必须额外配置 TLS 和鉴权。
echo.

streamlit run app.py --server.address 0.0.0.0 --server.port 8501

pause
