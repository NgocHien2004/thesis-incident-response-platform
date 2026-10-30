import api from './client'
export const getAlerts = (status, extra = {}) => api.get('/alerts/', { params: { status, ...extra } })
export const getAlert = (id) => api.get(`/alerts/${id}`)
export const createAlert = (data) => api.post('/alerts/', data)
export const triageAlert = (id, data) => api.patch(`/alerts/${id}/triage`, data)
export const markFalsePositive = (id) => api.patch(`/alerts/${id}/false-positive`)
export const uploadCSV = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/alerts/upload/csv', form)
}
export const suggestAI = (data) => api.post('/ai/alert/suggest', data)
export const scoreAlert = (id) => api.post(`/alerts/${id}/score`)
export const closeAlert = (id, note) => api.patch(`/alerts/${id}/close`, { note })
export const reopenAlert = (id, note) => api.patch(`/alerts/${id}/reopen`, { note })