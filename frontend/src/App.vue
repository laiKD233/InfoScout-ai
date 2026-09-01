<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import {
  getSources,
  createResearch,
  createGraphResearch,
  getResearch,
  researchStreamUrl,
  type Source,
  type TaskResult,
  type ProgressEvent,
  type Subtask,
  type Opinion,
} from './api'
import OpinionGraph from './components/OpinionGraph.vue'
import ProgressTimeline from './components/ProgressTimeline.vue'

// ===== 状态 =====
const topic = ref('')
const days = ref(30)
const emit = ref('md')
const mockMode = ref(false)
const quickMode = ref(false)
const engineMode = ref<'graph' | 'cli'>('graph')
const selectedSources = ref<string[]>([])
const sources = ref<Source[]>([])

const loading = ref(false)
const currentTaskId = ref<string | null>(null)
const result = ref<TaskResult | null>(null)
const errorMsg = ref('')
const warningMsg = ref('')
const elapsedSec = ref(0)

const progressEvents = ref<ProgressEvent[]>([])
const subtasks = ref<Subtask[]>([])
const opinions = ref<Opinion[]>([])
const usedMock = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null
let es: EventSource | null = null

// ===== 生命周期 =====
onMounted(async () => {
  try {
    const res = await getSources()
    sources.value = res.data.sources
  } catch (e) {
    console.error('获取数据源失败', e)
  }
})

onUnmounted(() => {
  stopTimers()
  if (es) es.close()
})

function stopTimers() {
  if (pollTimer) clearInterval(pollTimer)
  if (elapsedTimer) clearInterval(elapsedTimer)
  pollTimer = null
  elapsedTimer = null
}

// ===== 方法 =====
async function startResearch() {
  if (!topic.value.trim()) {
    errorMsg.value = '请输入调研主题'
    return
  }
  errorMsg.value = ''
  warningMsg.value = ''
  result.value = null
  progressEvents.value = []
  subtasks.value = []
  opinions.value = []
  usedMock.value = mockMode.value
  loading.value = true
  elapsedSec.value = 0
  stopTimers()
  if (es) { es.close(); es = null }

  elapsedTimer = setInterval(() => { elapsedSec.value++ }, 1000)

  const payload = {
    topic: topic.value,
    emit: emit.value,
    days: days.value,
    quick: quickMode.value,
    mock: mockMode.value,
    sources: selectedSources.value.length ? selectedSources.value.join(',') : undefined,
  }

  try {
    if (engineMode.value === 'graph') {
      const res = await createGraphResearch(payload)
      currentTaskId.value = res.data.task_id
      connectStream(res.data.task_id)
    } else {
      const res = await createResearch(payload)
      currentTaskId.value = res.data.task_id
      pollResult(res.data.task_id)
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || e.message
    loading.value = false
    stopTimers()
  }
}

function connectStream(taskId: string) {
  es = new EventSource(researchStreamUrl(taskId))

  es.onmessage = (e) => {
    if (e.data === '[DONE]') {
      if (es) es.close()
      return
    }
    try {
      const msg = JSON.parse(e.data)
      if (msg.type === 'progress') {
        progressEvents.value = [...progressEvents.value, msg.event]
      } else if (msg.type === 'result') {
        subtasks.value = msg.subtasks || []
        opinions.value = msg.opinions || []
        warningMsg.value = msg.error || ''
        result.value = {
          task_id: taskId,
          status: 'done',
          topic: topic.value,
          output: msg.report || '',
          error: msg.error || null,
          engine: 'graph',
          subtasks: msg.subtasks || [],
          opinions: msg.opinions || [],
        }
        finish()
      } else if (msg.type === 'error') {
        errorMsg.value = msg.detail || '调研失败'
        finish()
      }
    } catch {
      /* 忽略无法解析的消息 */
    }
  }

  es.onerror = () => {
    // 连接异常时兜底查询一次，防止漏掉最终结果
    fallbackCheck(taskId)
  }
}

function finish() {
  if (es) { es.close(); es = null }
  loading.value = false
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

async function fallbackCheck(taskId: string) {
  try {
    const res = await getResearch(taskId)
    if (res.data.status === 'done' || res.data.status === 'failed') {
      result.value = res.data
      subtasks.value = res.data.subtasks || []
      opinions.value = res.data.opinions || []
      if (res.data.status === 'failed') {
        errorMsg.value = res.data.error || '调研失败'
      } else {
        warningMsg.value = res.data.error || ''
      }
      finish()
    }
  } catch {
    /* 忽略 */
  }
}

function pollResult(taskId: string) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const res = await getResearch(taskId)
      result.value = res.data

      if (res.data.status === 'done' || res.data.status === 'failed') {
        if (pollTimer) clearInterval(pollTimer)
        pollTimer = null
        if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
        loading.value = false
        if (res.data.status === 'failed') {
          errorMsg.value = res.data.error || '调研失败'
        }
      }
    } catch (e: any) {
      console.error(e)
      if (pollTimer) clearInterval(pollTimer)
      if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
      loading.value = false
    }
  }, 2000)
}

function renderMarkdown(content: string | null): string {
  if (!content) return ''
  return marked.parse(content, { async: false }) as string
}

function toggleSource(id: string) {
  const idx = selectedSources.value.indexOf(id)
  if (idx >= 0) {
    selectedSources.value.splice(idx, 1)
  } else {
    selectedSources.value.push(id)
  }
}

// 按当前引擎过滤可选数据源（graph 引擎支持 web/reddit/youtube/juejin）
const visibleSources = computed(() =>
  sources.value.filter((s) => !s.engines || s.engines.includes(engineMode.value))
)

// 切换引擎时，清掉新引擎不支持的已选数据源
watch(engineMode, () => {
  const ids = new Set(visibleSources.value.map((s) => s.id))
  selectedSources.value = selectedSources.value.filter((id) => ids.has(id))
})

const stanceText: Record<string, string> = {
  positive: '正面',
  negative: '负面',
  neutral: '中立',
}
</script>

<template>
  <div class="container">
    <!-- 头部 -->
    <header class="header">
      <h1>🔍 InfoScout AI</h1>
      <p>多 Agent 协作调研系统 — 全网检索 → 内容清洗 → 观点提取 → 报告生成</p>
    </header>

    <!-- 输入区 -->
    <section class="card input-section">
      <div class="topic-input">
        <input
          v-model="topic"
          class="input"
          placeholder="输入调研主题，如：Claude Code vs Cursor、AI Agent 框架对比..."
          @keyup.enter="startResearch"
          :disabled="loading"
        />
        <button class="btn btn-primary" @click="startResearch" :disabled="loading || !topic.trim()">
          {{ loading ? `调研中... ${elapsedSec}s` : '开始调研' }}
        </button>
      </div>

      <div class="options">
        <div class="option-group">
          <label>执行引擎</label>
          <select v-model="engineMode" class="input small" :disabled="loading">
            <option value="graph">多 Agent 图引擎</option>
            <option value="cli">CLI 引擎</option>
          </select>
        </div>
        <div class="option-group">
          <label>回溯天数</label>
          <input v-model.number="days" type="number" min="1" max="90" class="input small" />
        </div>
        <div class="option-group">
          <label>输出格式</label>
          <select v-model="emit" class="input small">
            <option value="md">Markdown</option>
            <option value="compact">精简</option>
            <option value="json">JSON</option>
            <option value="html">HTML</option>
          </select>
        </div>
        <div class="option-group checkbox">
          <label><input type="checkbox" v-model="mockMode" /> Mock 模式（免 API Key 演示）</label>
        </div>
        <div class="option-group checkbox">
          <label><input type="checkbox" v-model="quickMode" /> 快速模式</label>
        </div>
      </div>

      <!-- 数据源选择 -->
      <div class="sources" v-if="visibleSources.length">
        <label class="sources-label">
          数据源（不选则全部；随执行引擎自动切换：{{ engineMode === 'graph' ? '图引擎 Web(必应中国)/掘金/B站/思否' : 'CLI 引擎多平台' }}）
        </label>
        <div class="sources-grid">
          <div
            v-for="s in visibleSources"
            :key="s.id"
            class="source-chip"
            :class="{ active: selectedSources.includes(s.id) }"
            @click="toggleSource(s.id)"
          >
            <span class="source-name">{{ s.name }}</span>
            <span class="source-tag" :class="{ free: s.free, paid: !s.free }">
              {{ s.free ? '免费' : '需Key' }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-msg">
      ⚠️ {{ errorMsg }}
    </div>

    <!-- 非致命告警（如某数据源无结果、未配 LLM Key 走降级模板） -->
    <div v-if="warningMsg && !errorMsg" class="warning-msg">
      ℹ️ {{ warningMsg }}
    </div>

    <!-- 任务状态 / 进度 -->
    <div v-if="currentTaskId && loading" class="card status-card">
      <div v-if="engineMode === 'graph'">
        <strong class="status-title">任务 ID：{{ currentTaskId }}（多 Agent 图引擎）</strong>
        <ProgressTimeline :events="progressEvents" />
      </div>
      <div v-else class="status-row">
        <div class="status-spinner"></div>
        <div>
          <strong>任务 ID：{{ currentTaskId }}</strong>
          <p>正在检索多平台数据，通常需要 30-90 秒...</p>
        </div>
      </div>
    </div>

    <!-- 结果展示 -->
    <div v-if="result && result.status === 'done'" class="result-area">
      <!-- 观点图谱 -->
      <div v-if="opinions.length" class="card">
        <h2 class="card-title">🕸 观点图谱</h2>
        <OpinionGraph :topic="result.topic" :opinions="opinions" />
      </div>

      <!-- 子任务拆解 -->
      <div v-if="subtasks.length" class="card">
        <h2 class="card-title">🧩 调研拆解（Plan-and-Execute）</h2>
        <div class="subtask-list">
          <div v-for="t in subtasks" :key="t.id" class="subtask-chip">
            <span class="subtask-angle">{{ t.angle }}</span>
            <span class="subtask-query">{{ t.query }}</span>
          </div>
        </div>
      </div>

      <!-- 观点列表 -->
      <div v-if="opinions.length" class="card">
        <h2 class="card-title">💡 核心观点</h2>
        <ul class="opinion-list">
          <li v-for="o in opinions" :key="o.id" class="opinion-item">
            <span class="stance-tag" :class="o.stance">{{ stanceText[o.stance] || o.stance }}</span>
            <span class="opinion-statement">{{ o.statement }}</span>
            <span class="opinion-weight">权重 {{ (o.weight * 100).toFixed(0) }}%</span>
          </li>
        </ul>
      </div>

      <!-- 报告 -->
      <div class="card result-card">
        <div class="result-header">
          <h2>📋 调研报告：{{ result.topic }}</h2>
          <div class="result-badges">
            <span v-if="usedMock" class="badge mock">Mock 演示数据</span>
            <span class="badge success">完成</span>
          </div>
        </div>
        <div
          v-if="emit === 'md' || emit === 'compact'"
          class="result-content markdown-body"
          v-html="renderMarkdown(result.output)"
        ></div>
        <pre v-else class="result-content raw">{{ result.output }}</pre>
      </div>
    </div>

    <!-- 页脚 -->
    <footer class="footer">
      <p>InfoScout AI v2.0.0 · LangGraph + MCP + Milvus + BGE-Reranker · <a href="https://github.com/laiKD233/InfoScout-ai" target="_blank">GitHub</a></p>
    </footer>
  </div>
</template>

<style scoped>
.container {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.header {
  text-align: center;
  margin-bottom: 32px;
}

.header h1 {
  font-size: 32px;
  margin-bottom: 8px;
}

.header p {
  color: var(--text-muted);
  font-size: 14px;
}

.input-section {
  margin-bottom: 24px;
}

.topic-input {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.options {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.option-group.checkbox {
  flex-direction: row;
  align-items: center;
}

.option-group label {
  font-size: 12px;
  color: var(--text-muted);
}

.input.small {
  width: 130px;
  padding: 8px 12px;
}

.sources {
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

.sources-label {
  font-size: 12px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 8px;
}

.sources-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.source-chip.active {
  background: var(--primary);
  border-color: var(--primary);
}

.source-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}

.source-tag.free {
  background: rgba(16, 185, 129, 0.2);
  color: var(--success);
}

.source-tag.paid {
  background: rgba(245, 158, 11, 0.2);
  color: var(--warning);
}

.error-msg {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--error);
  color: var(--error);
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.warning-msg {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--warning);
  color: var(--warning);
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}

.status-card {
  margin-bottom: 24px;
}

.status-title {
  display: block;
  margin-bottom: 16px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}

.card-title {
  font-size: 16px;
  margin-bottom: 12px;
  color: var(--primary-light);
}

.subtask-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.subtask-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.subtask-angle {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--primary-light);
  background: rgba(59, 130, 246, 0.15);
  padding: 2px 8px;
  border-radius: 12px;
}

.subtask-query {
  font-size: 13px;
  color: var(--text-muted);
}

.opinion-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.opinion-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 14px;
}

.stance-tag {
  flex-shrink: 0;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
}

.stance-tag.positive {
  background: rgba(16, 185, 129, 0.2);
  color: var(--success);
}

.stance-tag.negative {
  background: rgba(239, 68, 68, 0.2);
  color: var(--error);
}

.stance-tag.neutral {
  background: rgba(148, 163, 184, 0.2);
  color: var(--text-muted);
}

.opinion-statement {
  flex: 1;
}

.opinion-weight {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-muted);
}

.result-card {
  margin-bottom: 0;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
}

.badge.success {
  background: rgba(16, 185, 129, 0.2);
  color: var(--success);
}

.badge.mock {
  background: rgba(245, 158, 11, 0.2);
  color: var(--warning);
}

.result-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-content {
  font-size: 14px;
  line-height: 1.8;
}

.result-content.raw {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 16px 0 8px;
  color: var(--primary-light);
}

.markdown-body :deep(p) {
  margin-bottom: 12px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-bottom: 12px;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--primary);
  padding-left: 12px;
  color: var(--text-muted);
  margin: 12px 0;
}

.markdown-body :deep(code) {
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.markdown-body :deep(a) {
  color: var(--primary-light);
}

.footer {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  padding: 24px 0;
}

.footer a {
  color: var(--primary-light);
}
</style>
