<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import {
  getSources,
  createResearch,
  getResearch,
  type Source,
  type TaskResult,
} from './api'

// ===== 状态 =====
const topic = ref('')
const days = ref(30)
const emit = ref('md')
const mockMode = ref(true)
const quickMode = ref(false)
const selectedSources = ref<string[]>([])
const sources = ref<Source[]>([])

const loading = ref(false)
const currentTaskId = ref<string | null>(null)
const result = ref<TaskResult | null>(null)
const errorMsg = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

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
  if (pollTimer) clearInterval(pollTimer)
})

// ===== 方法 =====
async function startResearch() {
  if (!topic.value.trim()) {
    errorMsg.value = '请输入调研主题'
    return
  }
  errorMsg.value = ''
  result.value = null
  loading.value = true

  try {
    const res = await createResearch({
      topic: topic.value,
      emit: emit.value,
      days: days.value,
      quick: quickMode.value,
      mock: mockMode.value,
      sources: selectedSources.value.length ? selectedSources.value.join(',') : undefined,
    })

    currentTaskId.value = res.data.task_id
    pollResult(res.data.task_id)
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || e.message
    loading.value = false
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
        loading.value = false
        if (res.data.status === 'failed') {
          errorMsg.value = res.data.error || '调研失败'
        }
      }
    } catch (e: any) {
      console.error(e)
      if (pollTimer) clearInterval(pollTimer)
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
</script>

<template>
  <div class="container">
    <!-- 头部 -->
    <header class="header">
      <h1>🔍 InfoScout AI</h1>
      <p>全网智能调研 Agent — 输入主题，自动检索多平台，生成带引用的研究简报</p>
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
          {{ loading ? '调研中...' : '开始调研' }}
        </button>
      </div>

      <div class="options">
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
      <div class="sources" v-if="sources.length">
        <label class="sources-label">数据源（不选则全部）</label>
        <div class="sources-grid">
          <div
            v-for="s in sources"
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

    <!-- 任务状态 -->
    <div v-if="currentTaskId && loading" class="card status-card">
      <div class="status-spinner"></div>
      <div>
        <strong>任务 ID：{{ currentTaskId }}</strong>
        <p>正在检索多平台数据，通常需要 30-90 秒...</p>
      </div>
    </div>

    <!-- 结果展示 -->
    <div v-if="result && result.status === 'done'" class="card result-card">
      <div class="result-header">
        <h2>📋 调研报告：{{ result.topic }}</h2>
        <span class="badge success">完成</span>
      </div>
      <div
        v-if="emit === 'md' || emit === 'compact'"
        class="result-content markdown-body"
        v-html="renderMarkdown(result.output)"
      ></div>
      <pre v-else class="result-content raw">{{ result.output }}</pre>
    </div>

    <!-- 页脚 -->
    <footer class="footer">
      <p>InfoScout AI v1.0.0 · 基于 last30days-skill · <a href="https://github.com/laiKD233/InfoScout-ai" target="_blank">GitHub</a></p>
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
  width: 120px;
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

.status-card {
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

.result-card {
  margin-bottom: 24px;
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
