# BuddyKeyManagerDesktop

> 桌面端 WorkBuddy / CodeBuddy 凭证管理器（Python + FastAPI）：本机启动一个 Web 服务，
> 在浏览器里完成 OAuth 授权、凭证测活、余额查询、筛选标注、导出与推送入库。
>
> 与移动端 [BuddyKeyManager](https://github.com/Admin6016/BuddyKeyManager)（iOS）配套，共享同一套 Buddy2API 服务协议。

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://github.com/turbomind66/BuddyKeyManagerDesktop)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

当前版本：**v1.0.0**

---

## ✨ 功能特性

| 模块 | 能力 |
|------|------|
| 🔐 OAuth 授权 | 创建设备授权链接、自动打开系统浏览器登录、后台轮询等待授权结果并自动入库 |
| 💳 凭证管理 | 凭证列表：测活状态（有效 / 风控 / 失效 / 未测）、积分余额、有效期、入库时间 |
| 🔍 批量操作 | 批量测活、批量推送、按健康度筛选、备注标注、单条删除 |
| 📤 导出 / 推送 | 导出含 Token 的 JSON 备份；一键推送凭证到自建 Buddy2API 服务器（`/admin/account/import`） |
| 📱 接码平台 | ejiema 接码：取号 / 取码（自动提取验证码）/ 释放 / 拉黑 |
| 🌐 多区域 | 中国区（copilot.tencent.com）/ 国际区（www.codebuddy.ai） |
| 🔒 本机加密 | 凭证、设置以 Fernet 对称加密落盘，密钥存于 `data/.key`（仅本机） |

> 说明：桌面端采用「本地 Web 服务 + 浏览器 UI」形态（非原生窗口、非无痕浏览器）。
> 登录在**你自己的默认浏览器**中完成，成功后服务端轮询换取 Token，不接触你的账号密码。

## 📦 技术栈

| 层 | 技术 |
|----|------|
| 服务框架 | FastAPI + Uvicorn |
| 网络客户端 | httpx（AsyncClient） |
| 本地加密 | cryptography（Fernet，AES-128-CBC + HMAC） |
| 前端 UI | 原生 HTML / CSS / JavaScript（无构建步骤） |
| 测试 | pytest + FastAPI TestClient |

## 🚀 快速开始

### 环境要求

- Python ≥ 3.10（推荐 3.11+）
- 可用的网络环境（需访问 WorkBuddy / CodeBuddy 授权接口）

### 安装与运行

```bash
git clone https://github.com/turbomind66/BuddyKeyManagerDesktop.git
cd BuddyKeyManagerDesktop

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

启动后浏览器访问：<http://127.0.0.1:8765>

**Windows 用户**：直接双击 `start.bat`，脚本会自动创建虚拟环境、安装依赖并启动服务。

### 开发模式

```bash
pip install -r requirements-dev.txt
pytest -q
```

## 🛠️ 使用说明

> ⚠️ 仅供管理你本人或已获授权的账号，请遵守各平台服务条款。

1. **授权**：选择区域 → 点击「创建授权并打开浏览器」→ 在浏览器中完成登录 → 页面自动轮询并入库凭证。
2. **接码（可选）**：填入 ejiema Token → 取号 → 取码（自动提取验证码）→ 释放 / 拉黑。
3. **凭证**：批量测活查看健康度 → 按状态筛选 → 备注 / 删除 / 导出。
4. **推送**：填写 Buddy2API 服务器地址与管理密码 → 单条或批量推送入库。

## ⚙️ 环境变量

复制 `.env.example` 为 `.env` 后按需修改（也可直接用系统环境变量）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BKM_HOST` | `127.0.0.1` | 监听地址 |
| `BKM_PORT` | `8765` | 监听端口 |
| `BKM_OPEN_BROWSER` | `true` | 创建授权会话后是否自动打开浏览器 |
| `BKM_DATA_DIR` | `./data` | 数据目录（凭证 / 会话 / 设置 / 密钥） |

## 🔐 隐私与安全

- 凭证、接码 Token、Buddy2API 密码均以 Fernet 加密存于本机 `data/`，密钥文件 `data/.key` 权限收紧为 `600`。
- `data/`、`*.enc`、`.key`、`.env` 均已被 `.gitignore` 排除，**不会**随代码上传。
- 除你主动「推送」到自建服务器外，凭证数据不与任何第三方通信。
- 导出文件（`data/credentials-export.json`）包含明文 Token，请妥善保存、用完即删。
- 服务默认只监听 `127.0.0.1`；若改为 `0.0.0.0`，请确保处于可信网络。

详见 [SECURITY.md](SECURITY.md)。

## 📁 目录结构

```
BuddyKeyManagerDesktop/
├── app/
│   ├── main.py                 # FastAPI 应用（路由 / 会话轮询 / 凭证操作）
│   ├── config.py               # 配置与路径（读取 BKM_* 环境变量）
│   ├── models.py               # 数据模型（Credential / AuthSession）
│   ├── services/
│   │   ├── oauth.py            # WorkBuddy OAuth 网络层（授权 / 轮询 / 测活 / 余额）
│   │   ├── push.py             # 推送凭证到 Buddy2API
│   │   ├── sms.py              # ejiema 接码平台
│   │   └── secure_store.py     # Fernet 加密的本地 JSON 存储
│   ├── static/                 # app.js / style.css
│   └── templates/index.html    # 单页 UI
├── tests/                      # pytest 冒烟测试
├── .github/workflows/ci.yml    # GitHub Actions（编译检查 + 测试）
├── data/                       # 运行期生成（git 忽略，含加密凭证）
├── run.py                      # 启动入口
├── start.bat                   # Windows 一键启动
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

## 🙏 致谢

- 上游项目：[Admin6016/BuddyKeyManager](https://github.com/Admin6016/BuddyKeyManager)（iOS 版）

## 📄 License

[MIT](LICENSE) © 2026 turbomind66
