import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
})

// Tự động thêm token vào header
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

const NAIVE_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/

const markUtc = (v) => {
  if (typeof v === 'string') return NAIVE_ISO.test(v) ? v + 'Z' : v
  if (Array.isArray(v)) return v.map(markUtc)
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, markUtc(x)]))
  }
  return v
}

// Tự động redirect về login nếu token hết hạn
api.interceptors.response.use(
  res => {
    if (res.config?.responseType !== 'blob') res.data = markUtc(res.data)
    return res
  },
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api