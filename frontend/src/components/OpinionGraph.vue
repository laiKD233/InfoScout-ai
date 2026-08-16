<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { Opinion } from '../api'

const props = defineProps<{
  topic: string
  opinions: Opinion[]
}>()

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const STANCE_CATEGORY: Record<string, number> = {
  positive: 1,
  negative: 2,
  neutral: 3,
}

function truncate(text: string, n = 22): string {
  return text.length > n ? text.slice(0, n) + '…' : text
}

function buildOption(): echarts.EChartsOption {
  const opinions = props.opinions || []

  const nodes: any[] = [
    {
      id: 'topic',
      name: props.topic,
      symbolSize: 60,
      category: 0,
      itemStyle: { color: '#3b82f6' },
      label: { fontWeight: 'bold' as const },
    },
  ]
  const links: any[] = []

  opinions.forEach((o, i) => {
    nodes.push({
      id: o.id || `o${i}`,
      name: truncate(o.statement),
      symbolSize: 18 + (o.weight || 0.5) * 32,
      category: STANCE_CATEGORY[o.stance] ?? 3,
      tooltip: { formatter: () => o.statement },
    })
    links.push({ source: 'topic', target: o.id || `o${i}` })
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {},
    legend: {
      data: ['主题', '正面', '负面', '中立'],
      textStyle: { color: '#94a3b8' },
      top: 0,
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        data: nodes,
        links,
        categories: [
          { name: '主题', itemStyle: { color: '#3b82f6' } },
          { name: '正面', itemStyle: { color: '#10b981' } },
          { name: '负面', itemStyle: { color: '#ef4444' } },
          { name: '中立', itemStyle: { color: '#94a3b8' } },
        ],
        label: {
          show: true,
          position: 'right',
          color: '#e2e8f0',
          fontSize: 11,
        },
        emphasis: { focus: 'adjacency' },
        force: {
          repulsion: 320,
          edgeLength: [90, 160],
          gravity: 0.08,
        },
        lineStyle: { color: 'source', opacity: 0.4, curveness: 0.1 },
      },
    ],
  }
}

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  chart.setOption(buildOption(), true)
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})

watch(() => [props.topic, props.opinions], () => nextTick(render), { deep: true })
</script>

<template>
  <div class="opinion-graph">
    <div v-if="!opinions.length" class="graph-placeholder">暂无观点数据（等待分析 Agent 产出）</div>
    <div v-else ref="el" class="graph-canvas"></div>
  </div>
</template>

<style scoped>
.opinion-graph {
  width: 100%;
  min-height: 320px;
}

.graph-canvas {
  width: 100%;
  height: 340px;
}

.graph-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 340px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
