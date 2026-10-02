# 📈 A股智能分析工具

技术面 + 轻量基本面 + AI辅助解读 的股票分析工具
支持：电脑网页、手机浏览器、飞书/PushDeer每日推送

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

### 方式二：手机每日推送（微信/飞书，零成本，不用开电脑）⭐推荐

**适合**：每天自动收到自选股分析，不用开电脑

**原理**：GitHub Actions 每天定时运行分析脚本，通过飞书和/或 PushDeer 推送到手机。

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
| `FEISHU_WEBHOOK` | 飞书自定义机器人 Webhook | 与 PushDeer/Server酱二选一 |
| `FEISHU_SECRET` | 飞书机器人签名 Secret | 可选 |
| `PUSHDEER_PUSHKEY` | PushDeer PushKey | 与飞书可同时使用 |
| `PUSHDEER_API_URL` | PushDeer API 地址 | 可选，自建服务使用 |
| `SERVERCHAN_KEY` | 你的 Server酱 SendKey | 旧通道，可选 |
| `AI_API_KEY` | DeepSeek/Kimi/通义千问/OpenAI 的 API Key | ❌ 可选 |
| `AI_PROVIDER` | `deepseek`、`kimi`、`qwen` 或 `openai` | ❌ 可选 |
| `AI_MODEL` | 自定义模型名称；留空使用默认模型 | ❌ 可选 |
| `AI_ENABLED` | `true` 开启 AI，`false` 或留空关闭 | ❌ 可选 |

默认 AI 配置：

| 服务商 | `AI_PROVIDER` | 默认模型 |
|---|---|---|
| DeepSeek | `deepseek` | `deepseek-chat` |
| Kimi | `kimi` | `moonshot-v1-8k` |
| 通义千问 | `qwen` | `qwen-turbo` |
| OpenAI | `openai` | `gpt-4o-mini` |

注意：当前 workflow 从 `secrets` 读取这些配置，因此 `AI_PROVIDER`、`AI_MODEL` 和 `AI_ENABLED` 也应添加到 **Repository secrets**，不能只添加到 Variables。API Key 不会被打印到日志，AI 失败时只会记录服务商、模型、错误类型和 HTTP 状态码。

**4. 修改自选股**
编辑 `watchlist.txt`，改成你关注的股票代码（每行一个）：
```
600519 贵州茅台
000001 平安银行
300750 宁德时代
```

**5. 触发运行测试**
- 仓库页面：`Actions` → 点击 `自选股每日分析推送` → `Run workflow`
- 运行成功后，飞书和/或 PushDeer 会收到分析报告

**5.1 单独测试 AI 连接（推荐）**
- 进入 `Actions` → 点击 `AI 连接测试` → `Run workflow`
- `provider` 选择 `default` 时，使用 `AI_PROVIDER` Secret；也可以临时选择某个服务商
- `model` 留空时使用服务商默认模型
- 这个测试只发送一句 `只回复 OK`，不会读取行情，也不会发送微信
- Workflow 成功代表 API Key、服务商和模型配置有效

**5.2 配置飞书机器人（推荐）**

飞书自定义机器人的基础推送不额外收费，具体额度和企业政策以飞书官方为准。

1. 在飞书创建一个只有自己的群，或使用已有群。
2. 打开群设置 → 群机器人 → 添加机器人 → 自定义机器人。
3. 设置机器人名称，例如“股票日报助手”。
4. 安全设置建议选择“签名校验”，并保存签名密钥；也可以选择“自定义关键词”，关键词设置为“自选股”。
5. 复制 Webhook 地址。
6. 回到 GitHub：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`，添加：
   - `FEISHU_WEBHOOK`：飞书 Webhook 地址
   - `FEISHU_SECRET`：启用签名校验时填写，否则可以不创建
7. 配置飞书后，可以同时配置 PushDeer；两者都存在时，日报会同时发送到飞书和 PushDeer。
8. 运行 `自选股每日分析推送`；非交易日需要勾选 `force_run`。
9. 飞书群里收到“自选股日报”即表示配置成功。

程序支持飞书签名校验，日志不会打印完整 Webhook 或签名 Secret。

**5.3 配置 PushDeer**

PushDeer 可以推送到 PushDeer 官方服务或自建服务。官方项目已经停止维护，但官方 API 服务仍在使用；长期稳定性要求高时建议自建或把飞书作为主通道。

1. 安装并登录 PushDeer 客户端。
2. 在「设备」页面注册当前设备。
3. 在「Key」页面创建一个 Key。
4. 回到 GitHub：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`，添加：
   - `PUSHDEER_PUSHKEY`：PushDeer Key
   - `PUSHDEER_API_URL`：可选；留空使用 `https://api2.pushdeer.com/message/push`
5. 如果使用自建 PushDeer，把完整 API 地址填入 `PUSHDEER_API_URL`。
6. 配置飞书和 PushDeer 后，日报会同时发送到两个通道；其中一个失败时工作流会返回失败状态，但已经成功的通道不会重复发送。

PushDeer 官方在线服务可能存在额度或收费策略，自建服务代码对非商业使用通常免费，但仍需要服务器和证书维护成本。以 PushDeer 官方最新说明为准。

**6. 定时推送**
已配置为**北京时间周一到周五 15:30**（盘后）自动运行，非交易日会自动跳过。
可在 `.github/workflows/daily_push.yml` 中修改 `cron` 表达式调整时间；手动触发时可勾选 `force_run` 强制执行。

#### 成本
- GitHub Actions：免费（每月2000分钟额度）
- 飞书自定义机器人通常不额外收费；PushDeer 官方服务可能有额度/收费，自建服务需服务器成本
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
- 飞书机器人
- PushDeer
- Server酱、企业微信和 PushPlus（兼容保留）

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
