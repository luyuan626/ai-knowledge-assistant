# Knowledge Pilot · 通用 AI 问答与知识库助手

一个可运行的全栈 AI 应用：既可以作为通用 DeepSeek 对话助手，也可以基于上传的 PDF、TXT、Markdown 文档进行带来源页码的知识库问答。视觉检测、OCR、设备告警等结构化结果可通过统一 JSON 接口接入后续分析流程。

> 项目坚持“实现什么，就展示什么”：当前版本使用 SQLite 本地检索实现开箱可运行；Milvus、BGE-M3、Reranker 等不属于当前已落地依赖，见文末扩展方向。

## 在线能力

- **通用问答**：调用 OpenAI-compatible 模型网关；已在 AutoDL 以 DeepSeek 实际验证。
- **知识库问答**：上传 PDF / TXT / Markdown，按页解析与切分，回答返回引用片段、文档名和页码。
- **可解释检索**：展示词项相关度、确定性语义代理分数与最终排序分，便于排查“为什么命中这段内容”。
- **会话体验**：支持最近 6 轮上下文理解，页面渲染加粗、换行、代码等基础 Markdown 格式。
- **通用结构化输入**：提供视觉检测结果接入接口，可用于目标检测、OCR、设备告警或业务表单结果校验。
- **工程化边界**：敏感配置仅通过 `.env` 注入；每次问答返回 `trace_id` 和耗时；没有人工标注评测集时不展示虚构 Recall@K / MRR。

## 架构

```text
                    ┌──────────────────────┐
                    │ Vue 3 + Vite Web UI  │
                    │ 通用 / 知识库问答切换 │
                    └──────────┬───────────┘
                               │ HTTP
                    ┌──────────▼───────────┐
                    │ FastAPI API Service  │
                    ├──────────┬───────────┤
                    │          │           │
          文档上传 ──►│解析/切分 │ SQLite    │◄── 检索与引用
                    │ PyMuPDF  │ 文档/片段 │
                    │          │           │
                    └──────────┼───────────┘
                               │ OpenAI-compatible API
                    ┌──────────▼───────────┐
                    │ DeepSeek / LLM 网关  │
                    └──────────────────────┘
```

## 技术栈

| 层级 | 当前实现 |
| --- | --- |
| 前端 | Vue 3、Vite、原生 Fetch API |
| 后端 | Python 3.10+、FastAPI、Uvicorn、Pydantic |
| 文档处理 | PyMuPDF（PDF）、TXT / Markdown 文本读取 |
| 本地存储与检索 | SQLite、词项重叠评分、可解释排序分数 |
| 大模型 | OpenAI-compatible Chat Completions；已验证 DeepSeek |
| 部署 | Docker Compose；AutoDL 上以 `nohup + Uvicorn` 运行 |

## 两种问答模式

| 模式 | 适用场景 | 回答规则 |
| --- | --- | --- |
| 知识库问答 | 手册、报告、规范、项目资料 | 仅依据本轮检索材料回答；关键结论标注 `[序号]`；资料不足时明确说明。 |
| 通用问答 | 写作、面试准备、编码思路、开放问题 | 直接调用大模型；不把普通回答伪装成知识库结论。 |

## 本地运行

### 后端

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

### 前端

新开终端：

```bash
cd frontend
npm install
npm run dev
```

访问 <http://127.0.0.1:5174>。Vite 会将 `/api` 代理到 FastAPI。

### 配置 DeepSeek（可选）

在项目根目录创建 `.env`，该文件已被 Git 忽略：

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的密钥
LLM_MODEL=deepseek-flash
```

未配置模型时，知识库界面仍可演示检索与引用，但后端会返回明确标记的 `demo` 回答；不会冒充模型生成。

### Docker Compose

如已安装 Docker Desktop：

```bash
docker compose up --build
```

- 页面：<http://127.0.0.1:8088>
- Swagger：<http://127.0.0.1:8000/docs>

## 主要 API

| 方法 | 接口 | 说明 |
| --- | --- | --- |
| `POST` | `/api/documents` | 上传 PDF / TXT / Markdown 文档 |
| `GET` | `/api/documents` | 查询已入库文档 |
| `POST` | `/api/chat` | 通用或知识库问答 |
| `POST` | `/api/retrieval` | 查看当前检索与排序结果 |
| `POST` | `/api/vision/analyze` | 校验视觉模型结构化结果 |
| `GET` | `/api/evaluation/summary` | 读取评测状态与边界说明 |

`/api/chat` 请求示例：

```json
{
  "question": "如何让回答具备可追溯性？",
  "response_mode": "knowledge",
  "top_k": 5,
  "history": []
}
```

## AutoDL 部署

项目构建后的 `frontend/dist` 由 FastAPI 直接托管，服务器不需要安装 Node.js。由于 `dist` 不进入 Git，请先在本机或 CI 构建，再把生成的 `frontend/dist` 随部署文件上传到服务器：

```bash
cd frontend
npm ci
npm run build
```

服务器端执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
chmod +x deploy/*.sh
./deploy/start.sh
```

- 页面：`http://服务器地址:8000`
- 日志：`run/uvicorn.log`
- 停止：`./deploy/stop.sh`

## 当前边界与后续扩展

当前仓库优先保证轻量、可运行、可解释。以下方向**尚未作为当前实现或项目成果宣称**：

- 用 BGE-M3 替换本地确定性语义代理；
- 使用 Milvus / pgvector 存储大规模向量；
- 接入 BM25 倒排召回、RRF 融合与 BGE-Reranker；
- 基于人工标注问题集计算 Recall@K、MRR、引用正确率；
- 引入 Redis 会话缓存、MySQL 多租户知识库和异步文档解析队列。

这些方向已经保留了 API 与页面扩展位置，但应在真正实现、部署与评测后再写入简历。

## 简历表述

**通用 AI 问答与知识库助手｜全栈开发**：基于 FastAPI 与 Vue 3 实现 PDF/TXT/Markdown 解析、按页文本切分、SQLite 本地检索和可追溯问答链路；接入 DeepSeek 兼容模型接口，设计“通用问答 / 知识库问答”双模式与结构化视觉结果适配接口，返回引用片段、页码、Trace ID 与响应耗时；完成 Docker 与 AutoDL 部署。

## License

MIT License，详见 [LICENSE](LICENSE)。
