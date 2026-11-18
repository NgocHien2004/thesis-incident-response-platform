/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from 'react'
import EN, { PATTERNS } from './locales/en'

// Khóa dịch là chính câu tiếng Việt; thiếu bản tiếng Anh thì hiện nguyên tiếng Việt
function readLang() {
  try {
    const saved = localStorage.getItem('lang')
    if (saved === 'vi' || saved === 'en') return saved
  } catch { /* bỏ qua */ }
  return 'vi'
}

let lang = readLang()

const fill = (s, vars) => (vars ? s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m)) : s)

export function tr(key, vars) {
  if (typeof key !== 'string' || lang !== 'en') return fill(String(key ?? ''), vars)
  const hit = vars?.ctx && EN[`${vars.ctx}|${key}`] !== undefined ? EN[`${vars.ctx}|${key}`] : EN[key]
  if (hit !== undefined) return fill(hit, vars)
  for (const [re, tpl] of PATTERNS) {
    const m = key.match(re)
    if (m) return fill(tpl, { ...Object.fromEntries(m.slice(1).map((v, i) => [i + 1, v])), ...vars })
  }
  return fill(key, vars)
}

export const getLang = () => lang
export const locale = () => (lang === 'en' ? 'en-US' : 'vi-VN')
export const num = (n) => Number(n).toLocaleString(locale())

// Chuỗi có thẻ <b>…</b> và <code>…</code> thành phần tử React
export function rich(s) {
  const out = []
  const re = /<(b|code)>(.*?)<\/\1>/g
  let last = 0, m, i = 0
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index))
    out.push(m[1] === 'b' ? <b key={i++}>{m[2]}</b> : <code key={i++}>{m[2]}</code>)
    last = re.lastIndex
  }
  if (last < s.length) out.push(s.slice(last))
  return out
}

const Ctx = createContext({ lang, setLang: () => {}, t: tr })

export function I18nProvider({ children }) {
  const [current, setCurrent] = useState(lang)

  const setLang = (value) => {
    lang = value
    try { localStorage.setItem('lang', value) } catch { /* bỏ qua */ }
    setCurrent(value)
  }

  useEffect(() => {
    document.documentElement.lang = current
    document.title = tr('Quản lý sự cố an ninh mạng')
  }, [current])

  return <Ctx.Provider value={{ lang: current, setLang, t: tr }}>{children}</Ctx.Provider>
}

export const useI18n = () => useContext(Ctx)
