import api from './client'
export const getPlaybooks = (params) => api.get('/playbooks/', { params })
export const getPlaybook = (id) => api.get(`/playbooks/${id}`)
export const createPlaybook = (data) => api.post('/playbooks/', data)
export const updatePlaybook = (id, data) => api.put(`/playbooks/${id}`, data)
