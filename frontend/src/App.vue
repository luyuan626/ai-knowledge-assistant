<script setup>
import { computed, onMounted, ref } from 'vue'
import { chat, evaluation, hasLocalApi, listDocuments, retrieve, uploadDocument } from './api'

const active = ref('chat')
const question = ref('如何让智能问答的回答更可靠？')
const responseMode = ref('knowledge')
const loading = ref(false)
const answer = ref(null)
const messages = ref([{ role: 'assistant', text: '你好，我是 Knowledge Pilot。上传文档后，我会基于知识库给出带页码证据的回答。' }])
const documents = ref([])
const retrievalQuery = ref('RAG 如何提高检索相关性？')
const retrievalRows = ref([])
const evalData = ref(null)
const uploadMessage = ref('')
const vision = ref({ defect_type: '断丝', confidence: 0.91, position: '第 3 股 / 距端部 1.2 m' })

const menus = [
  { id: 'chat', icon: '◈', title: '智能问答', hint: '检索增强对话' },
  { id: 'knowledge', icon: '▤', title: '知识库管理', hint: '文档与切分' },
  { id: 'retrieval', icon: '⌕', title: '检索调试', hint: '召回与重排' },
  { id: 'vision', icon: '◉', title: '视觉结果接入', hint: '结构化上下文' },
  { id: 'evaluation', icon: '◌', title: '评测中心', hint: '离线评估' },
  { id: 'settings', icon: '⚙', title: '系统配置', hint: '模型与服务' }
]
const pageTitle = computed(() => menus.find(item => item.id === active.value)?.title)

function formatAnswer(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

async function ask() {
  const value = question.value.trim()
  if (!value || loading.value) return
  messages.value.push({ role: 'user', text: value })
  loading.value = true
  const history = messages.value.slice(-6).map(message => ({ role: message.role, content: message.text }))
  const result = await chat(value, history, responseMode.value)
  answer.value = result
  const scope = result.answer_scope === 'general' ? '通用问答' : '知识库问答'
  messages.value.push({ role: 'assistant', text: result.answer, meta: `${scope} · ${result.mode === 'llm' ? 'LLM 生成' : '演示回答'} · ${result.elapsed_ms} ms` })
  loading.value = false
  question.value = ''
}

async function refreshDocuments() { documents.value = await listDocuments() }
async function runRetrieval() { retrievalRows.value = await retrieve(retrievalQuery.value) }
async function loadEvaluation() { evalData.value = await evaluation() }
async function onUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploadMessage.value = `正在解析 ${file.name}…`
  try { const result = await uploadDocument(file); uploadMessage.value = `已入库：${file.name}，生成 ${result.chunks} 个文本片段`; await refreshDocuments() }
  catch (error) { uploadMessage.value = error.message }
  event.target.value = ''
}

onMounted(async () => { await refreshDocuments(); await runRetrieval(); await loadEvaluation() })
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">K</span><span>Knowledge<br><b>Pilot</b></span></div>
      <div class="workspace"><span class="workspace-dot"></span>我的工作区 <span class="chevron">⌄</span></div>
      <nav>
        <button v-for="item in menus" :key="item.id" class="nav-item" :class="{ active: active === item.id }" @click="active = item.id">
          <span class="nav-icon">{{ item.icon }}</span><span><b>{{ item.title }}</b><small>{{ item.hint }}</small></span>
        </button>
      </nav>
      <div class="sidebar-footer"><span class="status-dot"></span> 本地演示模式</div>
    </aside>

    <main class="content">
      <header class="topbar"><div><p class="eyebrow">知识增强工作台</p><h1>{{ pageTitle }}</h1></div><div class="top-actions"><span class="api-state" :class="{ online: hasLocalApi() }">{{ hasLocalApi() ? '本地 API 模式' : '交互演示' }}</span><button class="avatar">CY</button></div></header>

      <section v-if="active === 'chat'" class="chat-layout">
        <div class="chat-panel panel">
          <div class="panel-heading"><div><h2>对话与证据</h2><p>回答仅基于已检索的知识库片段，并附带可追溯引用。</p></div><span class="tag">RAG</span></div>
          <div class="conversation">
            <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role"><span class="message-avatar">{{ message.role === 'user' ? 'CY' : 'K' }}</span><div><p v-if="message.role === 'assistant'" v-html="formatAnswer(message.text)"></p><p v-else>{{ message.text }}</p><small v-if="message.meta">{{ message.meta }}</small></div></div>
            <div v-if="loading" class="message assistant"><span class="message-avatar">K</span><div class="typing"><i></i><i></i><i></i></div></div>
          </div>
          <div class="prompt-box"><textarea v-model="question" rows="2" :placeholder="responseMode === 'knowledge' ? '例如：如何设计可追溯的 RAG 知识库？' : '例如：帮我设计一份后端项目的面试介绍'" @keydown.ctrl.enter="ask"></textarea><div><div class="mode-switch"><button :class="{ selected: responseMode === 'knowledge' }" @click="responseMode = 'knowledge'">知识库问答</button><button :class="{ selected: responseMode === 'general' }" @click="responseMode = 'general'">通用问答</button><span>Ctrl + Enter 发送</span></div><button class="primary" @click="ask">发送 <b>↑</b></button></div></div>
        </div>
        <aside class="evidence-panel panel"><div class="panel-heading"><div><h2>引用证据</h2><p>Top-K 重排序结果</p></div></div><div v-if="answer?.citations?.length" class="evidence-list"><article v-for="citation in answer.citations" :key="citation.chunk_id" class="evidence"><div class="evidence-title"><b>{{ citation.document_name }}</b><span>{{ Math.round(citation.score * 100) }}%</span></div><small>第 {{ citation.page }} 页 · {{ citation.chunk_id }}</small><p>{{ citation.content }}</p></article></div><div v-else class="empty-state">发送问题后，这里将展示用于回答的文档片段、页码与相关度。</div></aside>
      </section>

      <section v-else-if="active === 'knowledge'" class="page-stack">
        <div class="section-intro"><div><h2>知识库管理</h2><p>支持 PDF / TXT / Markdown 文档；后端按页解析、父子分块并保留文档元数据。</p></div><label class="primary upload-button">上传文档<input type="file" accept=".pdf,.txt,.md" @change="onUpload" /></label></div>
        <p v-if="uploadMessage" class="notice">{{ uploadMessage }}</p>
        <div class="pipeline-card"><div><span>01</span><b>解析提取</b><small>PyMuPDF / 文本解析</small></div><i>→</i><div><span>02</span><b>结构化切分</b><small>页码、标题、文本边界</small></div><i>→</i><div><span>03</span><b>本地索引</b><small>SQLite / 片段元数据</small></div><i>→</i><div><span>04</span><b>证据溯源</b><small>片段、页码、版本</small></div></div>
        <div class="panel table-panel"><div class="panel-heading"><h2>已入库文档</h2><button class="text-button" @click="refreshDocuments">刷新</button></div><table><thead><tr><th>文档名称</th><th>来源</th><th>片段数</th><th>入库时间</th><th>状态</th></tr></thead><tbody><tr v-for="doc in documents" :key="doc.id"><td><b>{{ doc.name }}</b></td><td>{{ doc.source_type }}</td><td>{{ doc.chunks }}</td><td>{{ new Date(doc.created_at).toLocaleString() }}</td><td><span class="success-pill">可检索</span></td></tr></tbody></table></div>
      </section>

      <section v-else-if="active === 'retrieval'" class="page-stack">
        <div class="section-intro"><div><h2>检索调试</h2><p>查看词项相关度、确定性语义代理分与最终排序分，定位知识库命中问题。</p></div></div>
        <div class="query-bar panel"><input v-model="retrievalQuery" @keyup.enter="runRetrieval" /><button class="primary" @click="runRetrieval">运行检索</button></div>
        <div class="metric-row"><div class="metric"><span>文本相关度</span><b>词项重叠评分</b><small>轻量可解释的本地实现</small></div><div class="metric"><span>语义代理</span><b>确定性代理分</b><small>便于本地演示与调试</small></div><div class="metric"><span>最终排序</span><b>加权排序分</b><small>生产环境可替换为重排序模型</small></div></div>
        <div class="panel table-panel"><table><thead><tr><th>引用片段</th><th>词项分</th><th>代理分</th><th>候选分</th><th>排序分</th></tr></thead><tbody><tr v-for="row in retrievalRows" :key="row.chunk_id"><td><b>{{ row.document_name }}</b><small class="block">第 {{ row.page }} 页 · {{ row.content }}</small></td><td>{{ row.keyword_score }}</td><td>{{ row.vector_score }}</td><td>{{ row.rrf_score }}</td><td><strong>{{ row.rerank_score }}</strong></td></tr></tbody></table></div>
      </section>

      <section v-else-if="active === 'vision'" class="page-stack">
        <div class="section-intro"><div><h2>视觉结果接入</h2><p>将任意检测模型的结构化结果作为检索条件和大模型上下文，而非绑定某一种 YOLO 输出。</p></div></div>
        <div class="vision-grid"><div class="panel form-card"><h2>结构化推理结果</h2><label>缺陷 / 事件类别<input v-model="vision.defect_type" /></label><label>置信度<input v-model.number="vision.confidence" type="number" min="0" max="1" step="0.01" /></label><label>位置或对象标识<input v-model="vision.position" /></label><button class="primary">写入分析上下文</button></div><div class="panel json-card"><div class="panel-heading"><h2>Context JSON</h2><span class="tag">通用适配器</span></div><pre>{{ JSON.stringify({ source: 'vision-model', category: vision.defect_type, confidence: vision.confidence, location: vision.position, timestamp: 'ISO-8601' }, null, 2) }}</pre><div class="callout"><b>适用范围</b><p>目标检测、OCR、设备告警、表单字段等都可转换为相同的结构化上下文，参与检索过滤与报告生成。</p></div></div></div>
      </section>

      <section v-else-if="active === 'evaluation'" class="page-stack"><div class="section-intro"><div><h2>评测中心</h2><p>指标应基于固定问题集与人工标注的相关文档计算；未运行评测时不展示虚构结果。</p></div><button class="primary" @click="loadEvaluation">刷新状态</button></div><div class="evaluation-grid"><div class="metric panel"><span>Recall@K</span><b>{{ evalData?.retrieval_recall_at_5 ?? '—' }}</b><small>候选集合覆盖率</small></div><div class="metric panel"><span>MRR</span><b>{{ evalData?.mrr ?? '—' }}</b><small>首个正确结果排名</small></div><div class="metric panel"><span>引用正确率</span><b>{{ evalData?.citation_precision ?? '—' }}</b><small>回答证据可核验性</small></div></div><div class="panel evaluation-note"><h2>评测运行说明</h2><p>{{ evalData?.message }}</p><code>backend/app/seed_eval.json</code><span> 提供了可扩展的评测集样例；接入真实标注后再输出 Recall@K、MRR 与引用正确率。</span></div></section>

      <section v-else class="page-stack"><div class="section-intro"><div><h2>系统配置</h2><p>敏感凭据仅写入后端环境变量，前端和仓库不保存 API Key。</p></div></div><div class="settings-grid"><div class="panel setting"><span>文档解析</span><b>PyMuPDF + 文本解析</b><p>PDF 按页提取，分块保留来源页码。</p></div><div class="panel setting"><span>本地检索</span><b>SQLite + 可解释排序</b><p>开箱可运行；可按规模替换向量库与嵌入服务。</p></div><div class="panel setting"><span>模型网关</span><b>OpenAI Compatible API</b><p>使用 <code>LLM_BASE_URL</code>、<code>LLM_API_KEY</code> 和 <code>LLM_MODEL</code> 配置。</p></div><div class="panel setting"><span>可观测性</span><b>Trace ID + 引用证据</b><p>每次问答返回链路标识、耗时和使用的片段。</p></div></div></section>
    </main>
  </div>
</template>
