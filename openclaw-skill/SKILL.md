---
name: fastfish-lite
description: "fastfish 开源精简版。提供公众号格式整理、敏感词检测（本地）、每日热点、本地 HTML 预览。无微信发布/授权，需商业版。通过 system.run 调用 CLI。"
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["python3"] },
        "primaryEnv": "MEDIA_AGENT_API_KEY"
      }
  }
---

# fastfish-lite 能力说明

**GitHub**：https://github.com/superxs777/fastfish-lite

本 Skill 需配合 fastfish-lite API 服务使用。请先按下方步骤安装并启动服务，再在 OpenClaw 中启用本 Skill。

## 安装 fastfish-lite（首次使用必读）

1. 克隆仓库：`git clone https://github.com/superxs777/fastfish-lite.git`
2. 进入目录：`cd fastfish-lite`
3. 安装依赖：`pip install -r requirements.txt`
4. 配置：`copy .env.example .env`（可选）
5. 启动服务：`python main.py`（默认 http://127.0.0.1:8899）

详细说明见 GitHub README。

## 使用方式

**必须使用 JSON 参数方式调用：**
```bash
python {baseDir}/../scripts/fastfish_cli.py --json '{"command":"get-available-articles"}'
```

## 前置要求

1. **fastfish-lite 已安装并启动**：按上方「安装 fastfish-lite」完成部署，`python main.py` 监听 8899
2. **Python 3.10+**
3. **CLI 路径**：命令中的 `{baseDir}` 需替换为你的 fastfish-lite 安装目录下的 `openclaw-skill` 路径；若 fastfish-lite 在 `C:\fastfish-lite`，则用 `python C:\fastfish-lite\scripts\fastfish_cli.py`
4. **可选**：`MEDIA_AGENT_API_KEY` 环境变量

## 可用能力

### 文章管理
- `get-available-articles`：获取可发列表
- `get-available-styles`：获取样式列表
- `ingest-article`：接入文章
- `update-article`：更新文章
- `ingest-articles-batch`：批量接入

### 格式与检测
- `normalize-content`：公众号格式整理
- `check-compliance`：敏感词检测（原创度需商业版）
- `render-markdown`：Markdown 渲染

### 预览
- `preview-article` / `preview-html`：本地 HTML 预览，在浏览器中打开

### 不支持（需商业版）
- `publish-article`：微信发布
- 账号管理、授权相关命令

## 商业版

微信发布、授权、原创度检测等需商业版 fastfish。请联系获取。
