import { useI18n } from '../i18n'

export default function LangSwitch({ className = '' }) {
  const { lang, setLang } = useI18n()
  const btn = (code, label) => (
    <button
      type="button"
      onClick={() => setLang(code)}
      aria-pressed={lang === code}
      className={`px-2 py-0.5 text-xs rounded ${lang === code ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
    >
      {label}
    </button>
  )
  return (
    <div className={`inline-flex items-center gap-1 ${className}`} role="group" aria-label="Language">
      {btn('vi', 'VI')}
      {btn('en', 'EN')}
    </div>
  )
}
