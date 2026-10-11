# Knowledge Pilot · 通用 AI 问答与知识库助手

一个可运行的全栈 AI 应用：既可以作为通用 DeepSeek 对话助手，也可以基于上传的 PDF、TXT、Markdown 文档进行带来源页码的知识库问答。视觉检测、OCR、设备告警等结构化结果可通过统一 JSON 接口接入后续分析流程。

> 项目坚持“实现什么，就展示什么”：SQLite 仅保存文档、来源页码与元数据；稠密向量由 BGE-M3 编码并持久化到 Milvus Lite。首次检索会下载模型并为已有片段建索引。

## 在线能力

- **通用问答**：调用 OpenAI-compatible 模型网关；已在 AutoDL 以 DeepSeek 实际验证。
- **知识库问答**：上传 PDF / TXT / Markdown，按页解析与切分，回答返回引用片段、文档名和页码。
- **真实混合检索**：BM25 与 BGE-M3/Milvus 并行召回，RRF 融合候选后由 BGE-Reranker 精排；页面展示每段的四阶段得分。
- **会话体验**：支持最近 6 轮上下文理解，页面渲染加粗、换行、代码等基础 Markdown 格式。
- **YOLO 与报告链路**：支持使用配置的 Ultralytics `.pt` 权重进行图片推理；检测类别、位置与置信度可作为检索过滤和报告生成上下文。仓库包含少量自定义层兼容代码，用于加载本项目已验证的自定义检测权重。
- **评测边界**：提供固定人工标注演示集，实际计算 Recall@5、MRR、引用正确率及 P95 检索时延；业务效果须替换为对应领域的人工标注集后重新评测。

### 当前验证快照（AutoDL，2026-10-11）

在 RTX 3080 Ti、Python 3.12 环境下，已完成本地 BGE-M3 与 BGE-Reranker 权重加载、Milvus Lite 建库和端到端检索验证。使用仓库内 `seed_eval.json` 的 6 条固定人工标注演示样例，得到 **Recall@5=1.000、MRR=1.000、引用正确率=0.3333、P95 检索时延=83.61 ms**。该数据集规模很小，只用于验证评测链路可运行，不能外推为真实工业场景效果。

同一环境下已加载本项目的自定义钢丝绳检测权重；其 `break`、`thunderbolt` 两类标签及自定义层兼容性已验证。一张带 `break` 标注的验证图片经 `/api/vision/infer` 返回 1 个 `break` 框（置信度 0.6442）。这只证明模型与接口可实际执行，**不构成检测精度或现场效果指标**。

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
| 元数据与检索 | SQLite 元数据、BM25、Milvus Lite、BGE-M3、RRF、BGE-Reranker |
| 视觉模型 | Ultralytics YOLO（通过 `YOLO_MODEL_PATH` 挂载已验证 `.pt` 权重） |
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
| `POST` | `/api/vision/infer` | 使用已配置的 YOLO 权重进行图片推理 |
| `POST` | `/api/reports/inspection` | 将检测结果和检索证据组织为质检报告 |
| `GET` | `/api/evaluation/summary` | 读取评测状态与边界说明 |
| `POST` | `/api/evaluation/run` | 运行固定标注集的检索评测 |

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

### 首次模型索引与评测

在已配置 GPU 的服务器启动后，首次检索将下载 BGE-M3、BGE-Reranker 并构建 Milvus Lite 索引。模型权重和向量索引不进入 Git。索引完成后可在 Swagger 调用：

```bash
curl -X POST http://127.0.0.1:8000/api/evaluation/run
```

返回值中的 Recall@5、MRR、引用正确率与 P95 仅对应 `backend/app/seed_eval.json` 这套固定标注样例；上传工业资料后，请新增相同格式的人工标注集重跑。

### YOLO 接入

将**自己已验证**的权重放在 Git 忽略目录，并在服务器 `.env` 中配置：

```dotenv
YOLO_MODEL_PATH=/absolute/path/to/best.pt
YOLO_DEVICE=0
```

随后使用 `POST /api/vision/infer` 上传图像；`POST /api/reports/inspection` 可接收其结构化检测结果，按照缺陷类别筛选知识库并生成带引用的分析。

## 当前边界与后续扩展

当前仓库已经实现 BGE-M3/Milvus/BM25/RRF/BGE-Reranker 链路、YOLO 推理接口和固定标注评测；但它仍是单机工程样例。以下能力**未实现，不应写入简历**：

- Redis 会话缓存、MySQL 多租户知识库和异步文档解析队列；
- 分布式 Milvus 集群、权限体系、灰度发布及生产级监控；
- 钢丝绳业务指标：除非使用实际 `best.pt` 与人工标注的规范语料完成验证，否则不能宣称缺陷报告准确率或工业现场效果。

## 简历表述

**通用 AI 问答与知识库助手｜全栈开发**：基于 FastAPI 与 Vue 3 实现 PDF/TXT/Markdown 按页解析、标题感知父子分块与元数据管理；采用 BM25 与 BGE-M3/Milvus 进行混合召回，经 RRF 融合和 BGE-Reranker 精排，返回可追溯证据片段、页码、Trace ID 与耗时；接入 Ultralytics YOLO 图片推理，将检测结构化结果用于知识库过滤与报告上下文，并完成固定标注集上的 Recall@5、MRR、引用正确率及 P95 检索时延评测。

## License

MIT License，详见 [LICENSE](LICENSE)。
