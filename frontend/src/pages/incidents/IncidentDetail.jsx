import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getIncident, updateStatus, getEvidences, addEvidence, lockEvidence,
  getCustody, getContainments, proposeContainment, reviewContainment,
  executeContainment, getRecovery, addRecovery, updateRecoveryStatus,
  confirmRecovery, getCommunications, createCommunication,
  approveCommunication, sendCommunication, getPostmortem,
  createPostmortem, finalizePostmortem, getImpact, createImpact } from '../../api/incidents'
import Badge from '../../components/Badge'
import Card from '../../components/Card'
import Modal from '../../components/Modal'
import LoadingSpinner from '../../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuth } from '../../context/AuthContext'

const TABS = ['Tổng quan','Bằng chứng','Phạm vi','Containment','Recovery','Thông báo','Postmortem']

export default function IncidentDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const [incident, setIncident] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [tab, setTab]           = useState(0)

  const isAnalyst     = user?.role === 'analyst_soc'
  const isIT          = user?.role === 'it_helpdesk'
  const isStakeholder = user?.role === 'stakeholder'
  const canWrite      = isAnalyst || isIT

  const reload = () => getIncident(id).then(r => setIncident(r.data))

  useEffect(() => {
    getIncident(id).then(r => setIncident(r.data)).finally(() => setLoading(false))
  }, [id])

  if (loading) return <LoadingSpinner />
  if (!incident) return <div className="p-6 text-gray-500">Không tìm thấy incident</div>

  const statusFlow = ['open','investigating','contained','recovering','closed']
  const canAdvance = isAnalyst && incident.status !== 'closed'

  const handleAdvanceStatus = async () => {
    const next = statusFlow[statusFlow.indexOf(incident.status) + 1]
    if (!next) return
    try {
      await updateStatus(id, { status: next })
      toast.success(`Chuyển sang ${next}`)
      reload()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Thất bại')
    }
  }

  return (
    <div className="p-6 space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/incidents" className="hover:text-primary-600">Incidents</Link>
        <span>/</span>
        <span className="text-gray-900">#{incident.id}</span>
      </div>

      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Badge label={incident.severity} type={incident.severity}/>
              <Badge label={incident.status}   type={incident.status}/>
            </div>
            <h1 className="text-lg font-semibold text-gray-900">{incident.title}</h1>
            {incident.description && (
              <p className="text-sm text-gray-600 mt-1">{incident.description}</p>
            )}
          </div>
          {canAdvance && (
            <button onClick={handleAdvanceStatus}
              className="text-sm px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg flex-shrink-0">
              → {statusFlow[statusFlow.indexOf(incident.status)+1] || ''}
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
          {[
            {label:'Commander', value: `#${incident.commander_id||'—'}`},
            {label:'Phát hiện', value: incident.detected_at ? new Date(incident.detected_at).toLocaleString('vi-VN'):'—'},
            {label:'Contained', value: incident.contained_at ? new Date(incident.contained_at).toLocaleString('vi-VN'):'—'},
            {label:'Đóng lúc',  value: incident.resolved_at ? new Date(incident.resolved_at).toLocaleString('vi-VN'):'—'},
          ].map(m => (
            <div key={m.label}>
              <div className="text-xs text-gray-400 mb-0.5">{m.label}</div>
              <div className="text-sm text-gray-700">{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((t,i) => (
          <button key={t} onClick={() => setTab(i)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab===i ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>{t}</button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {tab===0 && <OverviewTab incident={incident} incId={id}/>}
        {tab===1 && <EvidenceTab incId={id} canWrite={canWrite} isAnalyst={isAnalyst}/>}
        {tab===2 && <ImpactTab   incId={id} isAnalyst={isAnalyst}/>}
        {tab===3 && <ContainmentTab incId={id} isIT={isIT} isAnalyst={isAnalyst}/>}
        {tab===4 && <RecoveryTab    incId={id} canWrite={canWrite} isAnalyst={isAnalyst} isStakeholder={isStakeholder}/>}
        {tab===5 && <CommunicationTab incId={id} isAnalyst={isAnalyst}/>}
        {tab===6 && <PostmortemTab    incId={id} isAnalyst={isAnalyst} incident={incident} reload={reload}/>}
      </div>
    </div>
  )
}

// ── Tab 0: Tổng quan ──────────────────────────────
function OverviewTab({ incident, incId }) {
  const [alerts, setAlerts] = useState([])
  useEffect(() => {
    import('../../api/incidents').then(m => m.getIncident(incId))
  }, [incId])

  useEffect(() => {
    fetch(`http://localhost:8000/incidents/${incId}/alerts`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` }
    }).then(r => r.json()).then(setAlerts).catch(()=>{})
  }, [incId])

  const checklist = (() => {
    try { return JSON.parse(incident.checklist || '[]') } catch { return [] }
  })()

  return (
    <div className="space-y-4">
      <Card title="Checklist ban đầu">
        {checklist.length === 0 ? (
          <p className="text-sm text-gray-400">Không có checklist</p>
        ) : (
          <ul className="space-y-2">
            {checklist.map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                <span className="w-5 h-5 rounded border border-gray-300 flex-shrink-0"/>
                {item}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {incident.root_cause && (
        <Card title="Root Cause">
          <p className="text-sm text-gray-700">{incident.root_cause}</p>
        </Card>
      )}
      {alerts.length > 0 && (
        <Card title={`Alerts liên quan (${alerts.length})`}>
          <div className="space-y-2">
            {alerts.map(a => (
              <div key={a.id} className="flex items-center justify-between text-sm">
                <span className="text-gray-700">{a.title}</span>
                <Badge label={a.severity} type={a.severity}/>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// ── Tab 1: Bằng chứng ──────────────────────────────
function EvidenceTab({ incId, canWrite, isAnalyst }) {
  const [evidences, setEvidences] = useState([])
  const [custody, setCustody]     = useState(null)
  const [showAdd, setShowAdd]     = useState(false)
  const [adding, setAdding]       = useState(false)
  const [form, setForm] = useState({ title:'', evidence_type:'log', source:'', content:'' })

  const load = () => getEvidences(incId).then(r => setEvidences(r.data))
  useEffect(() => { load() }, [incId])

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await addEvidence(incId, form)
      toast.success('Thêm bằng chứng thành công')
      setShowAdd(false)
      setForm({ title:'', evidence_type:'log', source:'', content:'' })
      load()
    } catch { toast.error('Thất bại') }
    finally { setAdding(false) }
  }

  const handleLock = async (evId) => {
    if (!confirm('Lock bằng chứng? Không thể sửa sau khi lock.')) return
    try {
      await lockEvidence(incId, evId)
      toast.success('Đã lock bằng chứng')
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
  }

  const loadCustody = async (evId) => {
    const res = await getCustody(incId, evId)
    setCustody({ evId, logs: res.data })
  }

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="flex justify-end">
          <button onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Thu thập bằng chứng
          </button>
        </div>
      )}

      {evidences.length === 0 ? (
        <Card><p className="text-sm text-gray-400">Chưa có bằng chứng</p></Card>
      ) : evidences.map(ev => (
        <Card key={ev.id} title={
          <div className="flex items-center gap-2">
            <span>{ev.title}</span>
            {ev.is_locked && <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">🔒 Locked</span>}
            <Badge label={ev.evidence_type} type="info"/>
          </div>
        } action={
          <div className="flex gap-2">
            <button onClick={() => loadCustody(ev.id)}
              className="text-xs text-gray-500 hover:text-primary-600">Chain of custody</button>
            {!ev.is_locked && canWrite && (
              <button onClick={() => handleLock(ev.id)}
                className="text-xs text-red-500 hover:text-red-700">Lock</button>
            )}
          </div>
        }>
          <div className="space-y-2 text-sm">
            {ev.source && <p className="text-gray-500 text-xs">Nguồn: {ev.source}</p>}
            {ev.file_hash && (
              <p className="text-xs font-mono text-gray-500 bg-gray-50 px-2 py-1 rounded">
                SHA-256: {ev.file_hash}
              </p>
            )}
            {ev.content && (
              <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto text-gray-700 max-h-32">
                {ev.content}
              </pre>
            )}
          </div>
        </Card>
      ))}

      {/* Chain of custody modal */}
      <Modal open={!!custody} onClose={() => setCustody(null)} title="Chain of Custody">
        {custody && (
          <div className="space-y-2">
            {custody.logs.map(log => (
              <div key={log.id} className="flex items-start gap-3 text-sm border-b border-gray-100 pb-2">
                <div className="w-20 flex-shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    log.action==='locked'   ? 'bg-red-100 text-red-700' :
                    log.action==='collected'? 'bg-green-100 text-green-700' :
                                              'bg-gray-100 text-gray-600'
                  }`}>{log.action}</span>
                </div>
                <div className="flex-1">
                  <p className="text-gray-600 text-xs">{log.note}</p>
                  <p className="text-gray-400 text-xs mt-0.5">
                    #{log.performed_by} · {new Date(log.performed_at).toLocaleString('vi-VN')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* Modal thêm bằng chứng */}
      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Thu thập bằng chứng">
        <form onSubmit={handleAdd} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tiêu đề *</label>
            <input value={form.title} onChange={e=>setForm({...form,title:e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              required/>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Loại</label>
              <select value={form.evidence_type} onChange={e=>setForm({...form,evidence_type:e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
                {['log','email','file','screenshot','hash','network','other'].map(t=>(
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Nguồn</label>
              <input value={form.source} onChange={e=>setForm({...form,source:e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
                placeholder="server, email..."/>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Nội dung / Log</label>
            <textarea value={form.content} onChange={e=>setForm({...form,content:e.target.value})}
              rows={4} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={()=>setShowAdd(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50">Hủy</button>
            <button type="submit" disabled={adding}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm hover:bg-primary-700 disabled:opacity-50">
              {adding?'Đang lưu...':'Lưu bằng chứng'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// ── Tab 2: Phạm vi ──────────────────────────────
function ImpactTab({ incId, isAnalyst }) {
  const [analyses, setAnalyses] = useState([])
  const [showAdd, setShowAdd]   = useState(false)
  const [adding, setAdding]     = useState(false)
  const [form, setForm] = useState({
    ioc_list:[], affected_assets:[], affected_accounts:[],
    attck_techniques:[], attck_version:'', summary:'', related_events:''
  })
  const [iocInput, setIocInput]   = useState('')
  const [techInput, setTechInput] = useState('')
  const [acctInput, setAcctInput] = useState('')

  const load = () => getImpact(incId).then(r => setAnalyses(r.data))
  useEffect(() => { load() }, [incId])

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await createImpact(incId, form)
      toast.success('Lưu phân tích thành công')
      setShowAdd(false)
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
    finally { setAdding(false) }
  }

  const parseJson = (str) => { try { return JSON.parse(str||'[]') } catch { return [] } }

  return (
    <div className="space-y-4">
      {isAnalyst && (
        <div className="flex justify-end">
          <button onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Thêm phân tích
          </button>
        </div>
      )}
      {analyses.length === 0 ? (
        <Card><p className="text-sm text-gray-400">Chưa có phân tích phạm vi</p></Card>
      ) : analyses.map(a => (
        <Card key={a.id} title={`Phân tích #${a.id}`}>
          <div className="space-y-3 text-sm">
            <div>
              <div className="text-xs text-gray-400 mb-1">IOC</div>
              <div className="flex flex-wrap gap-1">
                {parseJson(a.ioc_list).map(ioc => (
                  <span key={ioc} className="text-xs font-mono bg-red-50 text-red-700 px-2 py-0.5 rounded border border-red-100">{ioc}</span>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">ATT&CK Techniques (v{a.attck_version})</div>
              <div className="flex flex-wrap gap-1">
                {parseJson(a.attck_techniques).map(t => (
                  <a key={t} href={`https://attack.mitre.org/techniques/${t.replace('.','/').replace('.','/').replace('.','/').replace('.','/').replace('.','/')}/`}
                    target="_blank" rel="noreferrer"
                    className="text-xs font-mono bg-purple-50 text-purple-700 px-2 py-0.5 rounded border border-purple-100 hover:underline">{t}</a>
                ))}
              </div>
            </div>
            {parseJson(a.affected_accounts).length > 0 && (
              <div>
                <div className="text-xs text-gray-400 mb-1">Tài khoản bị ảnh hưởng</div>
                <div className="flex flex-wrap gap-1">
                  {parseJson(a.affected_accounts).map(ac => (
                    <span key={ac} className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded border border-orange-100">{ac}</span>
                  ))}
                </div>
              </div>
            )}
            <div>
              <div className="text-xs text-gray-400 mb-1">Tóm tắt</div>
              <p className="text-gray-700">{a.summary}</p>
            </div>
          </div>
        </Card>
      ))}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Phân tích phạm vi ảnh hưởng">
        <form onSubmit={handleAdd} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">IOC (Enter để thêm)</label>
            <input value={iocInput}
              onChange={e => setIocInput(e.target.value)}
              onKeyDown={e => { if(e.key==='Enter'){e.preventDefault(); if(iocInput.trim()){setForm(f=>({...f,ioc_list:[...f.ioc_list,iocInput.trim()]}));setIocInput('')}}}}
              placeholder="1.2.3.4, domain.com..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
            <div className="flex flex-wrap gap-1 mt-1">
              {form.ioc_list.map(ioc => (
                <span key={ioc} className="text-xs bg-red-50 text-red-700 px-2 py-0.5 rounded cursor-pointer"
                  onClick={() => setForm(f=>({...f,ioc_list:f.ioc_list.filter(i=>i!==ioc)}))}>
                  {ioc} ✕
                </span>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">ATT&CK Techniques (Enter để thêm)</label>
            <input value={techInput}
              onChange={e => setTechInput(e.target.value)}
              onKeyDown={e => { if(e.key==='Enter'){e.preventDefault(); if(techInput.trim()){setForm(f=>({...f,attck_techniques:[...f.attck_techniques,techInput.trim()]}));setTechInput('')}}}}
              placeholder="T1110, T1078..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
            <div className="flex flex-wrap gap-1 mt-1">
              {form.attck_techniques.map(t => (
                <span key={t} className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded cursor-pointer"
                  onClick={() => setForm(f=>({...f,attck_techniques:f.attck_techniques.filter(i=>i!==t)}))}>
                  {t} ✕
                </span>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tài khoản bị ảnh hưởng (Enter để thêm)</label>
            <input value={acctInput}
              onChange={e => setAcctInput(e.target.value)}
              onKeyDown={e => { if(e.key==='Enter'){e.preventDefault(); if(acctInput.trim()){setForm(f=>({...f,affected_accounts:[...f.affected_accounts,acctInput.trim()]}));setAcctInput('')}}}}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
            <div className="flex flex-wrap gap-1 mt-1">
              {form.affected_accounts.map(a => (
                <span key={a} className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded cursor-pointer"
                  onClick={() => setForm(f=>({...f,affected_accounts:f.affected_accounts.filter(i=>i!==a)}))}>
                  {a} ✕
                </span>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tóm tắt phân tích *</label>
            <textarea value={form.summary} onChange={e=>setForm({...form,summary:e.target.value})}
              rows={3} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={()=>setShowAdd(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={adding}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {adding?'Đang lưu...':'Lưu phân tích'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// ── Tab 3: Containment ──────────────────────────────
function ContainmentTab({ incId, isIT, isAnalyst }) {
  const [items, setItems] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding]   = useState(false)
  const [form, setForm] = useState({ action_type:'block_ip', target:'', reason:'', risk_level:'medium' })

  const load = () => getContainments(incId).then(r => setItems(r.data))
  useEffect(() => { load() }, [incId])

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await proposeContainment(incId, form)
      toast.success('Đề xuất containment thành công')
      setShowAdd(false)
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
    finally { setAdding(false) }
  }

  const handleReview = async (contId, approved) => {
    const note = approved ? 'Đã xem xét và phê duyệt' : prompt('Lý do từ chối:') || 'Từ chối'
    try {
      await reviewContainment(incId, contId, { approved, review_note: note })
      toast.success(approved ? 'Đã phê duyệt' : 'Đã từ chối')
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
  }

  const handleExecute = async (contId) => {
    const note = prompt('Ghi chú thực hiện:') || 'Đã thực hiện'
    try {
      await executeContainment(incId, contId, { execution_note: note })
      toast.success('Đã thực hiện containment')
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
  }

  return (
    <div className="space-y-4">
      {(isIT || isAnalyst) && (
        <div className="flex justify-end">
          <button onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Đề xuất containment
          </button>
        </div>
      )}

      {items.length === 0 ? (
        <Card><p className="text-sm text-gray-400">Chưa có containment action</p></Card>
      ) : items.map(c => (
        <Card key={c.id} title={
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{c.action_type}</span>
            <span className="text-gray-700">{c.target}</span>
            <Badge label={c.status} type={c.status}/>
            <Badge label={c.risk_level} type={c.risk_level==='high'?'critical':c.risk_level==='medium'?'warning':'info'}/>
          </div>
        }>
          <div className="space-y-2 text-sm">
            <p className="text-gray-600">{c.reason}</p>
            {c.review_note && (
              <p className="text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded">
                Review: {c.review_note}
              </p>
            )}
            {c.execution_note && (
              <p className="text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded">
                {c.execution_note}
              </p>
            )}
            <div className="flex gap-2 pt-1">
              {c.status === 'proposed' && isAnalyst && (
                <>
                  <button onClick={() => handleReview(c.id, true)}
                    className="text-xs px-3 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200">✓ Phê duyệt</button>
                  <button onClick={() => handleReview(c.id, false)}
                    className="text-xs px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200">✗ Từ chối</button>
                </>
              )}
              {c.status === 'approved' && (isIT || isAnalyst) && (
                <button onClick={() => handleExecute(c.id)}
                  className="text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200">▶ Thực hiện</button>
              )}
            </div>
          </div>
        </Card>
      ))}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Đề xuất Containment">
        <form onSubmit={handleAdd} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Loại hành động</label>
              <select value={form.action_type} onChange={e=>setForm({...form,action_type:e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
                {['block_ip','lock_account','isolate_machine','block_domain','disable_service','other'].map(t=>(
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Mức rủi ro</label>
              <select value={form.risk_level} onChange={e=>setForm({...form,risk_level:e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
                {['low','medium','high'].map(r=><option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mục tiêu *</label>
            <input value={form.target} onChange={e=>setForm({...form,target:e.target.value})}
              placeholder="IP, tài khoản, hostname..." required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Lý do *</label>
            <textarea value={form.reason} onChange={e=>setForm({...form,reason:e.target.value})}
              rows={3} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-xs text-orange-700">
            ⚠️ MVP chỉ mô phỏng — không tự động thực hiện trên hệ thống thật
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={()=>setShowAdd(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={adding}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {adding?'Đang gửi...':'Đề xuất'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// ── Tab 4: Recovery ──────────────────────────────
function RecoveryTab({ incId, canWrite, isAnalyst, isStakeholder }) {
  const [actions, setActions] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding]   = useState(false)
  const [form, setForm] = useState({ action_type:'patch_vulnerability', description:'', assigned_to:'' })

  const load = () => getRecovery(incId).then(r => setActions(r.data))
  useEffect(() => { load() }, [incId])

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await addRecovery(incId, { ...form, assigned_to: form.assigned_to ? parseInt(form.assigned_to) : null })
      toast.success('Thêm recovery action thành công')
      setShowAdd(false)
      load()
    } catch { toast.error('Thất bại') }
    finally { setAdding(false) }
  }

  const handleDone = async (recId) => {
    const note = prompt('Ghi chú hoàn thành:') || 'Đã xong'
    try {
      await updateRecoveryStatus(incId, recId, { status:'done', note })
      toast.success('Đã hoàn thành')
      load()
    } catch (err) { toast.error(err.response?.data?.detail||'Thất bại') }
  }

  const handleConfirm = async (recId) => {
    try {
      await confirmRecovery(incId, recId, { confirm_note:'Xác nhận hệ thống đã phục hồi' })
      toast.success('Đã xác nhận recovery')
      load()
    } catch (err) { toast.error(err.response?.data?.detail||'Thất bại') }
  }

  const statusColor = { pending:'gray', in_progress:'blue', done:'green', failed:'red' }

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="flex justify-end">
          <button onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Thêm recovery action
          </button>
        </div>
      )}

      {actions.length === 0 ? (
        <Card><p className="text-sm text-gray-400">Chưa có recovery action</p></Card>
      ) : actions.map(rec => (
        <Card key={rec.id} title={
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{rec.action_type}</span>
            <Badge label={rec.status} type={rec.status==='done'?'closed':rec.status==='failed'?'critical':'new'}/>
            {rec.is_confirmed && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">✓ Confirmed</span>}
          </div>
        }>
          <div className="space-y-2 text-sm">
            <p className="text-gray-700">{rec.description}</p>
            {rec.note && <p className="text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded">{rec.note}</p>}
            {rec.confirm_note && <p className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded">{rec.confirm_note}</p>}
            <div className="flex gap-2 pt-1">
              {rec.status !== 'done' && canWrite && (
                <button onClick={() => handleDone(rec.id)}
                  className="text-xs px-3 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200">✓ Hoàn thành</button>
              )}
              {rec.status === 'done' && !rec.is_confirmed && (isStakeholder || isAnalyst) && (
                <button onClick={() => handleConfirm(rec.id)}
                  className="text-xs px-3 py-1 bg-teal-100 text-teal-700 rounded hover:bg-teal-200">✓ Xác nhận</button>
              )}
            </div>
          </div>
        </Card>
      ))}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Thêm Recovery Action">
        <form onSubmit={handleAdd} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Loại hành động</label>
            <select value={form.action_type} onChange={e=>setForm({...form,action_type:e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
              {['remove_malware','patch_vulnerability','restore_backup','reset_credentials','rebuild_system','re_enable_service','other'].map(t=>(
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mô tả *</label>
            <textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})}
              rows={3} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Giao cho (User ID)</label>
            <input type="number" value={form.assigned_to} onChange={e=>setForm({...form,assigned_to:e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={()=>setShowAdd(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={adding}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {adding?'Đang lưu...':'Thêm'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// ── Tab 5: Thông báo ──────────────────────────────
function CommunicationTab({ incId, isAnalyst }) {
  const [comms, setComms] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding]   = useState(false)
  const [form, setForm] = useState({ comm_type:'internal_update', subject:'', content:'', recipients:[] })
  const [recipInput, setRecipInput] = useState('')

  const load = () => getCommunications(incId).then(r => setComms(r.data))
  useEffect(() => { load() }, [incId])

  const parseJson = s => { try { return JSON.parse(s||'[]') } catch { return [] } }

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await createCommunication(incId, form)
      toast.success('Tạo thông báo thành công')
      setShowAdd(false)
      setForm({ comm_type:'internal_update', subject:'', content:'', recipients:[] })
      load()
    } catch { toast.error('Thất bại') }
    finally { setAdding(false) }
  }

  const handleApprove = async (commId) => {
    try { await approveCommunication(incId, commId); toast.success('Đã phê duyệt'); load() }
    catch (err) { toast.error(err.response?.data?.detail||'Thất bại') }
  }

  const handleSend = async (commId) => {
    try { await sendCommunication(incId, commId); toast.success('Đã gửi'); load() }
    catch (err) { toast.error(err.response?.data?.detail||'Thất bại') }
  }

  const statusColor = { draft:'gray', sent:'blue', acknowledged:'green' }

  return (
    <div className="space-y-4">
      {isAnalyst && (
        <div className="flex justify-end">
          <button onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Tạo thông báo
          </button>
        </div>
      )}

      {comms.length === 0 ? (
        <Card><p className="text-sm text-gray-400">Chưa có thông báo</p></Card>
      ) : comms.map(c => (
        <Card key={c.id} title={
          <div className="flex items-center gap-2">
            <Badge label={c.status} type={c.status==='acknowledged'?'closed':c.status==='sent'?'escalated':'new'}/>
            <span className="text-gray-700">{c.subject}</span>
            {c.is_approved && <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">✓ Approved</span>}
          </div>
        }>
          <div className="space-y-2 text-sm">
            <div className="text-xs text-gray-500">
              Gửi đến: {parseJson(c.recipients).join(', ') || '—'}
            </div>
            <p className="text-gray-700 text-sm">{c.content}</p>
            {c.sent_at && <p className="text-xs text-gray-400">Gửi lúc: {new Date(c.sent_at).toLocaleString('vi-VN')}</p>}
            {isAnalyst && (
              <div className="flex gap-2 pt-1">
                {!c.is_approved && c.status === 'draft' && (
                  <button onClick={() => handleApprove(c.id)}
                    className="text-xs px-3 py-1 bg-green-100 text-green-700 rounded">✓ Phê duyệt</button>
                )}
                {c.is_approved && c.status === 'draft' && (
                  <button onClick={() => handleSend(c.id)}
                    className="text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded">▶ Gửi</button>
                )}
              </div>
            )}
          </div>
        </Card>
      ))}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Tạo thông báo">
        <form onSubmit={handleAdd} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Loại</label>
            <select value={form.comm_type} onChange={e=>setForm({...form,comm_type:e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
              {['internal_update','stakeholder_notify','escalation','external','other'].map(t=>(
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tiêu đề *</label>
            <input value={form.subject} onChange={e=>setForm({...form,subject:e.target.value})} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Nội dung *</label>
            <textarea value={form.content} onChange={e=>setForm({...form,content:e.target.value})}
              rows={4} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Recipients (Enter để thêm)</label>
            <input value={recipInput} onChange={e=>setRecipInput(e.target.value)}
              onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();if(recipInput.trim()){setForm(f=>({...f,recipients:[...f.recipients,recipInput.trim()]}));setRecipInput('')}}}}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"/>
            <div className="flex flex-wrap gap-1 mt-1">
              {form.recipients.map(r=>(
                <span key={r} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded cursor-pointer"
                  onClick={()=>setForm(f=>({...f,recipients:f.recipients.filter(i=>i!==r)}))}>
                  {r} ✕
                </span>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={()=>setShowAdd(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={adding}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {adding?'Đang tạo...':'Tạo (Draft)'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// ── Tab 6: Postmortem ──────────────────────────────
function PostmortemTab({ incId, isAnalyst, incident, reload }) {
  const [pm, setPm]           = useState(null)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating]     = useState(false)
  const [form, setForm] = useState({
    root_cause:'', impact:'', lessons_learned:'',
    responsible_party:'',
    timeline: [{ time:'', event:'', actor:'' }],
    action_items: [{ task:'', owner:'', deadline:'', done: false }]
  })

  useEffect(() => {
    getPostmortem(incId)
      .then(r => setPm(r.data))
      .catch(() => setPm(null))
      .finally(() => setLoading(false))
  }, [incId])

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      await createPostmortem(incId, form)
      toast.success('Lưu postmortem thành công')
      setShowCreate(false)
      getPostmortem(incId).then(r => setPm(r.data))
    } catch (err) { toast.error(err.response?.data?.detail||'Thất bại') }
    finally { setCreating(false) }
  }

  const handleFinalize = async () => {
    if (!confirm('Finalize postmortem và đóng incident?')) return
    try {
      await finalizePostmortem(incId)
      toast.success('Đã finalize — incident đóng')
      getPostmortem(incId).then(r => setPm(r.data))
      reload()
    } catch (err) { toast.error(err.response?.data?.detail||'Thất bại') }
  }

  const parseJson = s => { try { return JSON.parse(s||'[]') } catch { return [] } }

  if (loading) return <LoadingSpinner/>

  return (
    <div className="space-y-4">
      {!pm ? (
        <Card>
          <p className="text-sm text-gray-400 mb-3">Chưa có postmortem</p>
          {isAnalyst && (
            <button onClick={() => setShowCreate(true)}
              className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
              + Viết postmortem
            </button>
          )}
        </Card>
      ) : (
        <>
          <Card title={
            <div className="flex items-center gap-2">
              <span>Postmortem</span>
              {pm.is_finalized && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">✓ Finalized</span>}
            </div>
          } action={
            isAnalyst && !pm.is_finalized && (
              <button onClick={handleFinalize}
                className="text-xs px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700">
                Finalize & Đóng incident
              </button>
            )
          }>
            <div className="space-y-4 text-sm">
              <div>
                <div className="text-xs font-semibold text-gray-500 mb-1">ROOT CAUSE</div>
                <p className="text-gray-800">{pm.root_cause}</p>
              </div>
              <div>
                <div className="text-xs font-semibold text-gray-500 mb-1">IMPACT</div>
                <p className="text-gray-700">{pm.impact}</p>
              </div>
              {pm.lessons_learned && (
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-1">LESSONS LEARNED</div>
                  <p className="text-gray-700">{pm.lessons_learned}</p>
                </div>
              )}
              <div>
                <div className="text-xs font-semibold text-gray-500 mb-2">TIMELINE</div>
                <div className="space-y-2">
                  {parseJson(pm.timeline).map((t,i) => (
                    <div key={i} className="flex gap-3 text-sm">
                      <span className="text-gray-400 w-16 flex-shrink-0 font-mono text-xs">{t.time}</span>
                      <span className="text-gray-700 flex-1">{t.event}</span>
                      <span className="text-gray-400 text-xs">{t.actor}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs font-semibold text-gray-500 mb-2">ACTION ITEMS</div>
                <div className="space-y-2">
                  {parseJson(pm.action_items).map((a,i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center text-xs ${a.done ? 'bg-green-500 border-green-500 text-white':'border-gray-300'}`}>
                        {a.done ? '✓' : ''}
                      </span>
                      <span className={`flex-1 ${a.done ? 'line-through text-gray-400' : 'text-gray-700'}`}>{a.task}</span>
                      <span className="text-xs text-gray-400">{a.owner}</span>
                      <span className="text-xs text-gray-400">{a.deadline}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Viết Postmortem">
        <form onSubmit={handleCreate} className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Root Cause *</label>
            <textarea value={form.root_cause} onChange={e=>setForm({...form,root_cause:e.target.value})}
              rows={2} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Impact *</label>
            <textarea value={form.impact} onChange={e=>setForm({...form,impact:e.target.value})}
              rows={2} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Lessons Learned</label>
            <textarea value={form.lessons_learned} onChange={e=>setForm({...form,lessons_learned:e.target.value})}
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-2">Timeline</label>
            {form.timeline.map((t,i) => (
              <div key={i} className="grid grid-cols-3 gap-2 mb-2">
                <input placeholder="Thời gian" value={t.time}
                  onChange={e=>{const tl=[...form.timeline];tl[i].time=e.target.value;setForm({...form,timeline:tl})}}
                  className="border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-primary-400"/>
                <input placeholder="Sự kiện" value={t.event}
                  onChange={e=>{const tl=[...form.timeline];tl[i].event=e.target.value;setForm({...form,timeline:tl})}}
                  className="border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-primary-400"/>
                <input placeholder="Người thực hiện" value={t.actor}
                  onChange={e=>{const tl=[...form.timeline];tl[i].actor=e.target.value;setForm({...form,timeline:tl})}}
                  className="border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-primary-400"/>
              </div>
            ))}
            <button type="button" onClick={()=>setForm(f=>({...f,timeline:[...f.timeline,{time:'',event:'',actor:''}]}))}
              className="text-xs text-primary-600 hover:underline">+ Thêm dòng</button>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-2">Action Items</label>
            {form.action_items.map((a,i) => (
              <div key={i} className="grid grid-cols-3 gap-2 mb-2">
                <input placeholder="Công việc" value={a.task}
                  onChange={e=>{const ai=[...form.action_items];ai[i].task=e.target.value;setForm({...form,action_items:ai})}}
                  className="border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-primary-400"/>
                <input placeholder="Owner" value={a.owner}
                  onChange={e=>{const ai=[...form.action_items];ai[i].owner=e.target.value;setForm({...form,action_items:ai})}}
                  className="border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-primary-400"/>
                <input type="date" value={a.deadline}
                  onChange={e=>{const ai=[...form.action_items];ai[i].deadline=e.target.value;setForm({...form,action_items:ai})}}
                  className="border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-primary-400"/>
              </div>
            ))}
            <button type="button" onClick={()=>setForm(f=>({...f,action_items:[...f.action_items,{task:'',owner:'',deadline:'',done:false}]}))}
              className="text-xs text-primary-600 hover:underline">+ Thêm action item</button>
          </div>
          <div className="flex gap-2 sticky bottom-0 bg-white pt-2">
            <button type="button" onClick={()=>setShowCreate(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={creating}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {creating?'Đang lưu...':'Lưu postmortem'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}