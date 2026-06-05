import axios from 'axios'

// ── 端点超时分级 ──
// 快 (≤15s): 查询/列表/简单操作
// 中 (≤40s): 大多数 CRUD
// 慢 (≤90s): LLM 生成题目/报告/对话/纠错
const FASTER = 15000
const TIMEOUT = 40000
const SLOWER = 90000

const api = axios.create({
  baseURL: '/api/v1',
  timeout: TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('lawa_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('lawa_token')
      localStorage.removeItem('lawa_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── 端点路由：按需覆盖超时 ──
// 在调用时传入 { timeout: xxx } 即可覆盖默认值
//
// 使用示例：
//   api.get('/tasks', { timeout: FASTER })           // 快端点
//   api.post('/assessment/question', {}, { timeout: SLOWER })  // LLM端点

export { FASTER, SLOWER }
export default api

// ── LLM 配置 ──
export const llmConfigAPI = {
  list: () => api.get('/llm-config/list'),
  status: () => api.get('/llm-config/status'),
  add: (data: any) => api.post('/llm-config/add', data),
  test: (data: any) => api.post('/llm-config/test', data),
  remove: (name: string) => api.delete(`/llm-config/remove?name=${encodeURIComponent(name)}`),
  setDefault: (name: string) => api.post('/llm-config/set-default', { name }),
}
