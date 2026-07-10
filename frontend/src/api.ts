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

export interface TaskResult {
  task_id: string
  status: string
  topic: string
  output: string | null
  error: string | null
}

export const getSources = () => api.get<{ sources: Source[] }>('/sources')

export const createResearch = (data: ResearchRequest) =>
  api.post<TaskResponse>('/research', data)

export const getResearch = (taskId: string) =>
  api.get<TaskResult>(`/research/${taskId}`)

export const listResearch = () =>
  api.get<{ total: number; tasks: any[] }>('/research')

export const deleteResearch = (taskId: string) =>
  api.delete(`/research/${taskId}`)
