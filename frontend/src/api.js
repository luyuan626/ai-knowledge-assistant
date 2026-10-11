const hasLocalApi = () => ['localhost', '127.0.0.1'].includes(location.hostname)
const base = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${base}${path}`, options)
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || '服务暂不可用')
  return response.json()
}

const now = () => new Date().toISOString()
const seededDocs = [{ id: 'sample-001', name: '工业视觉质检知识库示例', source_type: 'seed', chunks: 3, created_at: now() }]
const sampleEvidence = [
  { chunk_id: 'demo-1', document_name: '工业视觉质检知识库示例', page: 2, score: 0.8421, content: '当前演示采用本地 SQLite 保存文档片段与来源元数据，并依据问题词项与片段内容的重叠程度进行候选排序。' },
  { chunk_id: 'demo-2', document_name: '工业视觉质检知识库示例', page: 3, score: 0.7189, content: '知识库入库应保存文档名称、页码、版本、设备型号和缺陷类别等元数据。回答中返回证据片段和页码，能够帮助使用者核验结论来源。' }
]

export async function listDocuments() {
  try { return await request('/api/documents') } catch { return seededDocs }
}

export async function uploadDocument(file) {
  const body = new FormData(); body.append('file', file)
  return request('/api/documents', { method: 'POST', body })
}

export async function chat(question, history = [], responseMode = 'knowledge') {
  try {
    return await request('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, top_k: 5, history, response_mode: responseMode }) })
  } catch {
    return { answer: responseMode === 'general' ? `当前无法连接模型服务，因此无法生成“${question}”的通用回答。` : `这是前端演示回答：已围绕“${question}”从本地知识库匹配候选片段，并返回可追溯的引用。实际运行后端后，系统会先保存解析后的片段及其页码，再按词项相关度与确定性代理分数完成排序。`, citations: sampleEvidence, trace_id: 'demo_trace_001', mode: 'demo', answer_scope: responseMode, elapsed_ms: 46 }
  }
}

export async function retrieve(query) {
  try { return await request('/api/retrieval', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, top_k: 5 }) }) }
  catch { return sampleEvidence.map((item, index) => ({ ...item, document_id: 'sample-001', keyword_score: 0.68 - index * 0.09, vector_score: 0.84 - index * 0.1, rrf_score: 0.031 - index * 0.001, rerank_score: item.score })) }
}

export async function evaluation() {
  try { return await request('/api/evaluation/summary') }
  catch { return { retrieval_recall_at_5: null, mrr: null, citation_precision: null, message: '本地演示未加载人工标注评测集，不展示虚构指标。', updated_at: now() } }
}

export async function runEvaluation() { return request('/api/evaluation/run', { method: 'POST' }) }

export async function inferVision(file, confidence = 0.25) {
  const body = new FormData(); body.append('file', file); body.append('confidence', String(confidence))
  return request('/api/vision/infer', { method: 'POST', body })
}

export { hasLocalApi }
