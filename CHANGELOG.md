# 变更日志（Changelog）

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-09-09

### ✨ 新增
- Python 桌面端首版发布：FastAPI + Uvicorn 本机服务，原生 HTML/CSS/JS 单页 UI
- OAuth 设备授权流：创建授权链接、自动打开系统浏览器、后台轮询入库
- 凭证管理：列表、批量测活 / 推送、状态筛选、备注、单条删除
- 余额查询：调用 `p_tcaca` 资源接口聚合剩余积分
- 接码平台：内置 ejiema（取号 / 取码（自动提取验证码）/ 释放 / 拉黑）
- 推送 Buddy2API：单条 / 批量 `/admin/account/import`
- Fernet 本地加密（`data/credentials.enc`、`data/settings.enc`、密钥 `data/.key`）
- GitHub Actions CI：Python 3.11 / 3.12 矩阵，跑 pytest
- pytest 冒烟测试：路由、加密、验证码提取

### 🐛 修复
- 与原 iOS 仓库[Admin6016/BuddyKeyManager](https://github.com/Admin6016/BuddyKeyManager) 配套，共享同一 Buddy2API 服务协议

### 🔒 安全
- `data/`、`.env`、`*.enc`、`.key` 全部 git 忽略；密钥权限收紧为 `0600`

### 📝 文档
- README、SECURITY、CONTRIBUTING、CHANGELOG 齐备