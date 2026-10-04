import api from './client'
export const getAlerts = (status) => api.get('/alerts/', { params: { status } })
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