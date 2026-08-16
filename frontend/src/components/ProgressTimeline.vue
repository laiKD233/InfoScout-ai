<script setup lang="ts">
import { computed } from 'vue'
import type { ProgressEvent } from '../api'

const props = defineProps<{
  events: ProgressEvent[]
}>()

const PIPELINE = [
  { key: 'planner', label: '规划拆解' },
  { key: 'retriever', label: '检索' },
  { key: 'cleaner', label: '清洗' },
  { key: 'analyst', label: '分析' },
  { key: 'writer', label: '写作' },
]

type NodeState = 'pending' | 'running' | 'done' | 'error'

const states = computed<Record<string, NodeState>>(() => {
  const map: Record<string, NodeState> = {}
  for (const p of PIPELINE) map[p.key] = 'pending'
  for (const ev of props.events) {
    const node = map[ev.node]
    if (node === undefined) continue
    if (ev.status === 'error') map[ev.node] = 'error'
    else if (ev.status === 'done') map[ev.node] = 'done'
    else if (ev.status === 'start' && map[ev.node] !== 'done' && map[ev.node] !== 'error') {
      map[ev.node] = 'running'
    }
  }
  return map
})

const latestDetail = computed(() => {
  const done = [...props.events].reverse().find((e) => e.status === 'done' || e.status === 'error')
  return done?.detail || ''
})
</script>

<template>
  <div class="progress-timeline">
    <div class="steps">
      <div
        v-for="(p, i) in PIPELINE"
        :key="p.key"
        class="step"
        :class="states[p.key]"
      >
        <div class="dot" />
        <div class="step-label">{{ p.label }}</div>
        <div v-if="i < PIPELINE.length - 1" class="connector" />
      </div>
    </div>
    <div v-if="latestDetail" class="latest-detail">{{ latestDetail }}</div>
  </div>
</template>

<style scoped>
.progress-timeline {
  margin-bottom: 16px;
}

.steps {
  display: flex;
  align-items: flex-start;
}

.step {
  position: relative;
  flex: 1;
  text-align: center;
}

.dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--border);
  margin: 0 auto 6px;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.step.done .dot {
  background: var(--success);
}

.step.running .dot {
  background: var(--primary);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.25);
  animation: pulse 1s ease-in-out infinite;
}

.step.error .dot {
  background: var(--error);
}

.step-label {
  font-size: 12px;
  color: var(--text-muted);
}

.step.done .step-label,
.step.running .step-label {
  color: var(--text);
}

.connector {
  position: absolute;
  top: 6px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: var(--border);
}

.latest-detail {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.25); }
}
</style>
