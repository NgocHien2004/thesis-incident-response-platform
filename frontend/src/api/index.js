import api from './client'

const clean = (p = {}) =>
  Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== ''))

export const login = (data) => api.post('/auth/login', data)
export const getMe = () => api.get('/auth/me')

export const listIncidents = (params) => api.get('/incidents', { params: clean(params) })
export const getIncident = (id) => api.get(`/incidents/${id}`)
export const createIncident = (data) => api.post('/incidents', data)
export const updateIncident = (id, data) => api.put(`/incidents/${id}`, data)
export const changeStatus = (id, data) => api.patch(`/incidents/${id}/status`, data)
export const getHistory = (id) => api.get(`/incidents/${id}/history`)
export const deleteIncident = (id) => api.delete(`/incidents/${id}`)

export const listUploads = (incidentId) => api.get(`/incidents/${incidentId}/uploads`)
export const createUpload = (incidentId, dataType, file) => {
  const form = new FormData()
  form.append('data_type', dataType)
  form.append('file', file)
  return api.post(`/incidents/${incidentId}/uploads`, form)
}
export const deleteUpload = (id) => api.delete(`/uploads/${id}`)

export const listAlerts = (params) => api.get('/alerts', { params: clean(params) })
export const listIncidentAlerts = (incidentId, params) =>
  api.get(`/incidents/${incidentId}/alerts`, { params: clean(params) })
export const getAlert = (id) => api.get(`/alerts/${id}`)
export const getAlertMoves = (id) => api.get(`/alerts/${id}/moves`)
export const verifyAlert = (id, data) => api.patch(`/alerts/${id}/verify`, data)
export const bulkVerify = (data) => api.post('/alerts/bulk-verify', data)
export const moveAlerts = (data) => api.post('/alerts/move', data)

export const getDashboard = () => api.get('/dashboard')
export const getAttackTypes = () => api.get('/attack-types')
export const getLabels = (dataType) => api.get('/labels', { params: clean({ data_type: dataType }) })
export const updateLabel = (id, data) => api.put(`/labels/${id}`, data)
export const getSettings = () => api.get('/settings')
export const updateSetting = (key, value) => api.put(`/settings/${key}`, { value: String(value) })
export const getModels = () => api.get('/models')
export const syncModels = () => api.post('/models/sync')
export const getAiHealth = () => api.get('/ai/health')