@echo off
chcp 65001 >nul
REM A股智能分析工具 - 启动脚本 (Windows)
REM 用法: 双击 run.bat

cd /d "%~dp0"

echo =========================================
echo   A股智能分析工具 启动中...
echo =========================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 python，请先安装 Python 3.8+
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 创建虚拟环境
if not exist venv (
    echo 📦 首次运行，创建虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate

echo 📦 检查依赖...
pip install -q -r requirements.txt

echo.
echo ✅ 启动成功！
echo 📱 在手机上使用：请确保手机和电脑在同一WiFi下
echo    然后在手机浏览器访问下方显示的 Network URL
echo.

REM 启动，允许局域网访问
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false

pause
