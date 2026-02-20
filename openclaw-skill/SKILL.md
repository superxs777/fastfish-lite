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

## 使用方式

**必须使用 JSON 参数方式调用：**
```bash
python {baseDir}/../scripts/fastfish_cli.py --json '{"command":"get-available-articles"}'
```

## 前置要求

1. **fastfish-lite API 服务已启动**：`python main.py`（默认 8899）
2. **Python 3.10+**
3. **可选**：`MEDIA_AGENT_API_KEY` 环境变量

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
