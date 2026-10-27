// Đoán loại playbook phù hợp từ loại triage hoặc tiêu đề cảnh báo
export function guessPlaybookType(...texts) {
  const t = texts.filter(Boolean).join(' ').toLowerCase()
  if (/phish|lừa đảo|email|mail/.test(t)) return 'phishing'
  if (/credential|brute|login|đăng nhập|account|tài khoản|password|mật khẩu/.test(t)) return 'credential_compromise'
  if (/malware|ransom|virus|trojan|mã độc|encrypt|process/.test(t)) return 'malware'
  if (/web|sql|xss|injection|http|ddos/.test(t)) return 'web_attack'
  return null
}

export const PLAYBOOK_TYPES = {
  phishing: 'Phishing',
  credential_compromise: 'Lạm dụng tài khoản',
  malware: 'Mã độc',
  web_attack: 'Tấn công web',
  other: 'Khác',
}

export const PHASES = [
  ['analysis', 'Xác nhận và phân tích'],
  ['evidence', 'Thu thập bằng chứng'],
  ['containment', 'Ngăn chặn'],
  ['recovery', 'Loại bỏ nguyên nhân và khôi phục'],
  ['communication', 'Thông báo và phối hợp'],
  ['closure', 'Đóng vụ và postmortem'],
]

export const ROLE_LABEL = {
  it_helpdesk: 'IT/Helpdesk',
  analyst_soc: 'Analyst/SOC',
}

// Thời điểm lưu ở backend là UTC không kèm múi giờ
export function parseUtc(s) {
  if (!s) return null
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z')
}
