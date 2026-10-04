import api from './client'
export const getDashboard = () => api.get('/dashboard/')
export const getSLA = () => api.get('/dashboard/sla')