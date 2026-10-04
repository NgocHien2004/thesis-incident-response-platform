import api from './client'
export const getAssets = () => api.get('/assets/')
export const createAsset = (data) => api.post('/assets/', data)
export const updateAsset = (id, data) => api.put(`/assets/${id}`, data)
export const deleteAsset = (id) => api.delete(`/assets/${id}`)