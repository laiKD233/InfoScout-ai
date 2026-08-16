import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,
})

export interface Source {
  id: string
  name: string
  free: boolean
  needs_key: boolean
  note?: string
  engines?: string[]
}

export interface ResearchRequest {
  topic: string
  emit?: string
  quick?: boolean
  deep?: boolean
  days?: number
  sources?: string
  mock?: boolean
}

export interface TaskResponse {
  task_id: string
  status: string
  message: string
}

export interface Subtask {
  id: string
  query: string
  angle: string
}

export interface Opinion {
  id: string
  statement: string
  stance: 'positive' | 'negative' | 'neutral' | string
  evidence_urls: string[]
  weight: number
}

export interface ProgressEvent {
  node: string
  status: string
  detail: string
  ts: string
}

export interface TaskResult {
  task_id: string
  status: string
  topic: string
  output: string | null
  error: string | null
  engine?: string
  subtasks?: Subtask[]
  opinions?: Opinion[]
  progress_events?: ProgressEvent[]
}

export const getSources = () => api.get<{ sources: Source[] }>('/sources')

export const createResearch = (data: ResearchRequest) =>
  api.post<TaskResponse>('/research', data)

// 多 Agent 图引擎（planner + 检索/清洗并行 + 分析/写作串行）
export const createGraphResearch = (data: ResearchRequest) =>
  api.post<TaskResponse>('/research/graph', data)

export const getResearch = (taskId: string) =>
  api.get<TaskResult>(`/research/${taskId}`)

export const listResearch = () =>
  api.get<{ total: number; tasks: any[] }>('/research')

export const deleteResearch = (taskId: string) =>
  api.delete(`/research/${taskId}`)

// SSE 进度流地址（EventSource 使用）
export const researchStreamUrl = (taskId: string) =>
  `/api/v1/research/${taskId}/stream`
