# 贡献指南（Contributing）

感谢你愿意改进 BuddyKeyManagerDesktop 🙌

## 开发准备

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python run.py                   # http://127.0.0.1:8765
```

## 提交前自检

```bash
pytest -q                       # 全部通过
python -m compileall -q app     # 无语法错误
```

## 分支与提交

- 分支命名：`feat/xxx`、`fix/xxx`、`docs/xxx`
- 提交信息建议遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：`feat: 新增批量导出 CSV`、`fix: 修复轮询超时未置为失败`

## 安全红线（不接受）

- ❌ 任何真实 Token、密码、服务器地址、`data/` 目录下的文件、`.env`
- ❌ 绕过或自动化绕过平台风控 / 反爬机制的功能
- ❌ 把凭证上传到第三方服务（除用户自行配置的 Buddy2API）

提交前请确认 `git status` 中没有上述文件。

## 问题反馈

提 Issue 时请附上：系统版本、Python 版本、复现步骤、以及**脱敏后**的日志。
