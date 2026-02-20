# fastfish-lite

fastfish 开源精简版。提供公众号格式整理、敏感词检测（本地 DFA）、每日热点推送、本地 HTML 预览等功能。

## 功能列表

| 功能 | fastfish-lite | 商业版 fastfish |
|------|---------------|-----------------|
| 公众号格式整理 | ✅ | ✅ |
| Markdown 渲染与多套样式 | ✅ | ✅ |
| 文章接入、更新 | ✅ | ✅ |
| 敏感词检测（本地词库） | ✅ | ✅ |
| 原创度检测 | ❌ 需商业版 | ✅ |
| 每日热点拉取与推送 | ✅ | ✅ |
| 本地 HTML 预览 | ✅ | ✅ |
| 微信公众号发布 | ❌ 需商业版 | ✅ |
| 微信授权、多账号管理 | ❌ 需商业版 | ✅ |
| 百度内容审核 | ❌ 需商业版 | ✅ |

## 安装（Windows）

1. **克隆仓库**
   ```bash
   git clone https://github.com/superxs777/fastfish-lite.git
   cd fastfish-lite
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境**
   ```bash
   copy .env.example .env
   # 编辑 .env，按需修改端口等
   ```

5. **敏感词库（可选）**
   将 [Sensitive-lexicon](https://github.com/fighting41love/sensitive) 的 Vocabulary 目录拷到 `data/sensitive_lexicon/Vocabulary/`，或通过 `MEDIA_AGENT_SENSITIVE_LEXICON_DIR` 指定路径。

6. **启动服务**
   ```bash
   python main.py
   ```
   默认监听 `http://127.0.0.1:8899`

7. **验证**
   ```bash
   curl http://127.0.0.1:8899/health
   ```

## 快速开始

- 获取可发列表：`python scripts/fastfish_cli.py get-available-articles`
- 接入文章：`python scripts/fastfish_cli.py ingest-article --title "标题" --content-file article.md --is-markdown --format-style minimal`
- 本地预览：`python scripts/fastfish_cli.py preview-html --article-id 1`

## 商业版 fastfish

如需以下能力，请使用商业版：

- 微信公众号发布、预览、授权
- 多账号管理
- 原创度检测（千帆 API）
- 百度内容审核

## 打赏与支持

一个人维护开源项目不易，深夜改 bug、周末写文档是常态。若 fastfish-lite 曾帮您省下一点时间、少踩一个坑，欢迎请我喝杯咖啡——您的每一份心意，都是支撑我继续把这件事做下去的理由。感谢。

**支付宝打赏**（扫码转账，金额随意，心意无价）：

![打赏二维码](assets/donate.png)

---

## 联系方式

商业版咨询、技术交流、合作洽谈，欢迎添加微信（半日 · 山东济南）：

![微信二维码](assets/contact.png)

> 扫一扫上面的二维码图案，加我为朋友。

## 开源协议

MIT License
