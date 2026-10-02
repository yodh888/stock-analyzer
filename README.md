# 📈 A股智能分析工具

技术面 + 轻量基本面 + AI辅助解读 的股票分析工具
支持：电脑网页、手机浏览器、微信每日推送

---

## 🚀 三种使用方式

### 方式一：电脑/手机网页（本地运行）

**适合**：在电脑上运行，手机同WiFi访问

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（Windows双击run.bat，Mac/Linux运行 bash run.sh）
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

- 电脑访问：`http://localhost:8501`
- 手机访问：同一WiFi下，访问终端显示的 `Network URL`

---

### 方式二：微信每日推送（零成本，不用开电脑）⭐推荐

**适合**：每天自动收到自选股分析，不用开电脑

**原理**：GitHub Actions 每天定时运行分析脚本，通过 Server酱 推送到你的微信。

#### 部署步骤

**1. 注册 Server酱（获取推送Key）**
- 打开 https://sct.ftqq.com
- 微信扫码登录
- 复制你的 `SendKey`（形如 `SCTxxxxx`）

**2. 创建 GitHub 仓库**
- 注册/登录 GitHub
- 新建一个仓库（比如叫 `stock-analyzer`）
- 把本项目所有文件上传到仓库

**3. 配置密钥（Secrets）**
在仓库页面：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

添加以下密钥：

| 名称 | 值 | 必填 |
|------|-----|------|
| `SERVERCHAN_KEY` | 你的 Server酱 SendKey | ✅ 必填 |
| `AI_API_KEY` | DeepSeek/Kimi的API Key | ❌ 可选 |
| `AI_PROVIDER` | `deepseek` 或 `kimi` | ❌ 可选 |
| `AI_ENABLED` | `true` 或 `false` | ❌ 可选 |

**4. 修改自选股**
编辑 `watchlist.txt`，改成你关注的股票代码（每行一个）：
```
600519 贵州茅台
000001 平安银行
300750 宁德时代
```

**5. 触发运行测试**
- 仓库页面：`Actions` → 点击 `自选股每日分析推送` → `Run workflow`
- 运行成功后，微信会收到分析报告

**6. 定时推送**
已配置为**北京时间周一到周五 15:30**（盘后）自动运行，非交易日会自动跳过。
可在 `.github/workflows/daily_push.yml` 中修改 `cron` 表达式调整时间；手动触发时可勾选 `force_run` 强制执行。

#### 成本
- GitHub Actions：免费（每月2000分钟额度）
- Server酱：免费版每天5条推送
- AI分析：可选，DeepSeek约0.003元/次

---

### 方式三：云服务器（手机随时主动操作）

**适合**：想随时用手机分析任意股票，不止定时推送

买一台云服务器（推荐阿里云/腾讯云轻量应用服务器，新用户约50元/年），部署后手机浏览器随时访问。

```bash
# 上传代码到服务器后
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
nohup streamlit run app.py --server.address 127.0.0.1 --server.port 8501 &
```

> 云服务器不要直接把 Streamlit 暴露到公网。请在前面增加 Nginx/Caddy，配置 HTTPS、登录认证和访问控制；否则任何人访问到地址后都可能消耗你的 AI Key。

手机访问 `http://服务器IP:8501` 即可。

---

## 📊 功能说明

### 技术面分析
- 均线系统（MA5/10/20/60）
- MACD / KDJ / RSI 指标
- 布林带 / 成交量分析
- K线形态识别（早晨之星、吞没、红三兵等10+形态）
- 支撑位 / 阻力位计算
- 综合得分 + 条件式观察建议

### AI 辅助解读（可选）
- 开启后用大模型综合解读所有指标
- 支持 DeepSeek / Kimi / 通义千问 / OpenAI
- 成本约 0.003-0.05 元/次

### 推送到手机
- Server酱（微信推送）
- 企业微信群机器人
- PushPlus

---

## 🔑 API Key 获取

- **DeepSeek**（推荐，最便宜）：https://platform.deepseek.com
- **Kimi**：https://platform.moonshot.cn
- **通义千问**：https://dashscope.aliyuncs.com

---

## 💰 成本说明

| 项目 | 费用 |
|------|------|
| 数据（AKShare） | 免费 |
| 纯规则分析 | 免费 |
| AI分析（每次） | 约0.003-0.05元 |
| GitHub Actions | 免费 |
| Server酱 | 免费（每天5条） |
| 云服务器（可选） | 约50元/年起 |

---

## ⚠️ 常见问题

**Q: GitHub Actions 获取数据失败怎么办？**
A: 国外服务器访问国内数据源可能不稳定。可在 workflow 里加重试逻辑，或换用国内CI平台（如腾讯云CloudBase、阿里云函数计算）。

**Q: Server酱免费版每天只有5条推送？**
A: 是的。如果自选股多、推送频繁，可以升级付费版（约18元/月，每天1000条），或改用PushPlus（免费版每天200条）。

**Q: 能在手机上主动发股票代码就收到分析吗？**
A: 目前的推送是定时的。要实现主动触发，需要部署到云服务器（方式三），或开发企业微信机器人。

**Q: AI分析准吗？**
A: AI是辅助解读，基于技术指标给出判断。建议结合规则版信号一起看，不要完全依赖AI。

---

## ⚠️ 免责声明

本工具仅供学习研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
