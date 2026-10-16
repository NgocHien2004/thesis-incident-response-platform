import api from './client'

export const getAudit = (params) => api.get('/audit/', { params })
export const verifyAudit = () => api.get('/audit/verify')

export const downloadAuditCsv = async (params) => {
  const res = await api.get('/audit/export.csv', { params, responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = 'audit_log.csv'
  a.click()
  URL.revokeObjectURL(url)
}
