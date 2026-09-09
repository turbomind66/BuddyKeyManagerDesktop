# 安全说明（Security）

BuddyKeyManagerDesktop 在本机管理你的 WorkBuddy / CodeBuddy OAuth 凭证。请务必遵守以下原则，避免凭证泄露。

## 切勿提交的内容

以下文件 / 目录已被 `.gitignore` 排除，**严禁手动 `git add -f` 提交**：

| 路径 | 说明 |
|------|------|
| `data/` | 全部运行时数据（含加密凭证、会话、设置、密钥） |
| `data/.key` | Fernet 主密钥（明文） |
| `data/credentials.enc` | 加密凭证库 |
| `data/sessions.json` | 授权会话（含 state、auth_url） |
| `data/settings.enc` | 接码 Token / Buddy2API 密码 |
| `data/credentials-export.json` | 含明文 Token 的导出文件 |
| `.env` | 真实环境变量配置 |

`git status` 应始终保持干净；提交前请确认无上述文件。

## 本地加密机制

- 凭证、设置使用 **Fernet**（AES-128-CBC + HMAC-SHA256）对等加密。
- 密钥（`data/.key`）首次运行时由 `cryptography.fernet.Fernet.generate_key()` 产生，权限设置为 `0600`。
- `data/.key` 丢失 = 已加密的数据将不可恢复。请自行备份该文件并妥善保管。
- 当前版本**未实现**主密码派生（scrypt / pbkdf2），意味着拿到 `data/.key` 的人即可解密全部数据。后续若需更严格保护，请在此基础上增加主密码二次包装（参见 `CONTRIBUTING.md`）。

## 网络通信

- 应用只在以下场景对外发起请求：
  - 调用 WorkBuddy / CodeBuddy 授权与测活接口（与 iOS 版一致的官方接口）
  - 你主动推送凭证到自建 Buddy2API 服务器（`/admin/login` + `/admin/account/import`）
- 不上传、不外发任何使用数据 / 遥测。

## 服务监听

- 默认监听 `127.0.0.1`，仅本机访问。
- 若改成 `0.0.0.0`（`BKM_HOST=0.0.0.0`），任何能访问该端口的人将能操作你的凭证。请确认所在网络可信，并考虑加反代鉴权。

## 导出文件

- 「导出敏感 JSON」按钮生成的 `credentials-export.json` 含**明文** Access / Refresh Token。
- 请只在受信任的设备上保存，用完后建议安全删除。

## 上报问题

如发现安全漏洞，请私下联系仓库维护者，不要在公开 Issue 中贴出真实 Token 或 `data/.key`。