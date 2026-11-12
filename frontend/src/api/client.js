import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Backend lưu thời gian UTC không kèm múi giờ: thêm Z để trình duyệt đổi sang giờ máy
const NAIVE_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/

const markUtc = (v) => {
  if (typeof v === 'string') return NAIVE_ISO.test(v) ? v + 'Z' : v
  if (Array.isArray(v)) return v.map(markUtc)
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, markUtc(x)]))
  }
  return v
}

api.interceptors.response.use(
  res => {
    res.data = markUtc(res.data)
    return res
  },
  err => {
    const isLogin = err.config?.url?.includes('/auth/login')
    if (err.response?.status === 401 && !isLogin) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
