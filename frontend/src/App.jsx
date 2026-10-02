import { useEffect, useRef, useState } from 'react'
import { api, getApiKey, setApiKey, usePoll } from './api'

const THRESHOLD = 70
const MAX_POINTS = 90
const NAV = ['Overview', 'Incidents', 'Approvals', 'Remediation', 'Safety policies', 'Logs / Loki', 'Infrastructure']

const hhmm = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--')
const hhmmss = (iso) => (iso ? new Date(iso).toLocaleTimeString() : '--:--:--')
const mmss = (seconds) => (seconds ? `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}` : '0:00')
const ago = (iso) => {
  if (!iso) return 'no action yet'
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000))
  return minutes < 1 ? 'just now' : minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`
}
const severityClass = (value = '') => (/crit|high/i.test(value) ? 'cr' : /med|warn/i.test(value) ? 'wa' : 'ok')
const statusClass = (value = '') => ({ resolved: 'ok', failed: 'cr', escalated: 'wa' }[value] || 'am')
const params = (value = {}) => Object.entries(value).slice(0, 2).map(([key, item]) => `${key}=${typeof item === 'object' ? JSON.stringify(item) : item}`).join(' · ')
const formatPercent = (value) => typeof value === 'number' ? `${value.toFixed(1)}%` : '--'
const formatRate = (value) => typeof value === 'number' ? `${(value / 1024).toFixed(1)} KB/s` : '--'

export default function App() {
  const [activePage, setActivePage] = useState('Overview')
  const summary = usePoll(api.summary)
  const infra = usePoll(api.infra)
  const decisions = usePoll(() => api.decisions(20))
  const pending = usePoll(api.pending, 4000)
  const history = usePoll(() => api.history(8))
  const [points, setPoints] = useState([])
  const [apiKey, setKey] = useState(getApiKey)
  const [draftKey, setDraftKey] = useState(getApiKey)
  const approvalsRef = useRef(null)
  const s = summary.data
  const list = pending.data?.approvals ?? []
  const last = decisions.data?.recent?.[0]
  const lastEvent = history.data?.history?.[0]
  const cpu = infra.data?.cpu_percent

  useEffect(() => {
    if (typeof cpu === 'number') setPoints((current) => [...current, { t: new Date().toISOString(), v: cpu }].slice(-MAX_POINTS))
  }, [cpu])

  const saveApiKey = (event) => {
    event.preventDefault()
    setApiKey(draftKey.trim())
    setKey(draftKey.trim())
  }

  const errors = [summary, infra, decisions, pending, history].map((item) => item.error).filter(Boolean)
  const title = list.length ? `Steady, with ${list.length} decision${list.length > 1 ? 's' : ''} waiting.` : 'All systems steady.'

  return <div className="app">
    <Sidebar active={activePage} onNavigate={setActivePage} pending={list.length} escalated={s?.escalated ?? 0} lastAction={ago(lastEvent?.timestamp)} />
    <main className="main">
      <header className="head">
        <div><div className="eyebrow">{new Date().toUTCString().slice(0, 16).toUpperCase()} · UTC</div><h1>{title}</h1></div>
        <div className="row gap10"><button className="btn" disabled title="Pause endpoint is not exposed by the backend">Pause agent</button><button className="btn pri" onClick={() => approvalsRef.current?.scrollIntoView({ behavior: 'smooth' })}>Review approvals</button></div>
      </header>
      <form className="connection" onSubmit={saveApiKey}><div><div className="eyebrow">Backend connection</div><div className="connection-copy">{apiKey ? 'API key configured in this browser' : 'Enter the API key used by Flask'}</div></div><input type="password" value={draftKey} onChange={(event) => setDraftKey(event.target.value)} placeholder="API key" aria-label="Backend API key" /><button className="btn" type="submit">Connect</button></form>
      {errors.length > 0 && <div className="notice">{errors.some((error) => error.status === 401) ? 'API key rejected. Check API_KEY in frontend/.env.' : `Backend unavailable: ${errors[0].message}`}</div>}
      {activePage !== 'Overview' && <PageHeader page={activePage} />}
      {activePage === 'Overview' && <>
      <section className="kpis">
        <Kpi label="Incidents detected" value={s?.detected ?? '--'} sub={`${s?.resolved ?? 0} resolved · ${s?.failed ?? 0} failed`} tone="ok" />
        <Kpi label="Awaiting approval" value={s?.pending_approval ?? list.length} sub={`${s?.escalated ?? 0} escalated`} tone="wa" accent />
        <Kpi label="Auto-remediated" value={s?.resolved ?? '--'} sub={`${Math.round((s?.auto_resolution_rate ?? 0) * 100)}% success rate`} tone="ok" />
        <Kpi label="Mean time to resolve" value={mmss(s?.mttr_seconds_avg)} unit="min" sub={`${s?.total_incidents ?? 0} incidents tracked`} tone="ok" />
      </section>
      <section className="mid"><div className="card grow"><CardHead title="CPU saturation · node-exporter" sub="Live · Prometheus" /><Chart points={points} /></div><Pipeline last={last} infra={infra.data} cpu={cpu} pending={list.length} /></section>
      <section className="card infrastructure"><CardHead title="Infrastructure telemetry" sub={infra.data?.source ?? 'Prometheus'} /><div className="infra-grid"><Metric label="CPU" value={formatPercent(infra.data?.cpu_percent)} tone={typeof cpu === 'number' && cpu > 70 ? 'wa' : 'ok'} /><Metric label="Memory" value={formatPercent(infra.data?.memory_percent)} tone="ok" /><Metric label="Network receive" value={formatRate(infra.data?.network_receive_bytes_per_second)} tone="am" /><Metric label="Network transmit" value={formatRate(infra.data?.network_transmit_bytes_per_second)} tone="am" /><Metric label="Prometheus" value={infra.data?.prometheus_up === 1 ? 'up' : infra.data?.prometheus_up === 0 ? 'down' : '--'} tone={infra.data?.prometheus_up === 1 ? 'ok' : 'wa'} /><Metric label="Node exporter" value={infra.data?.node_exporter_up === 1 ? 'up' : infra.data?.node_exporter_up === 0 ? 'down' : '--'} tone={infra.data?.node_exporter_up === 1 ? 'ok' : 'wa'} /></div></section>
      <section className="bottom">
        <div className="card grow" ref={approvalsRef}><CardHead title="Awaiting your approval" sub={`${list.length} pending`} />{!list.length && <div className="empty">Nothing waiting. The agent is handling everything on its own.</div>}{list.map((item, index) => <ApprovalRow key={item.action_id} approval={item} first={!index} onDone={pending.refresh} />)}</div>
        <div className="card side-card"><CardHead title="Live events" sub="Streaming" />{(history.data?.history ?? []).slice(0, 6).map((event, index) => <div className="event" key={`${event.action_id}-${index}`}><span className="mono dm">{hhmmss(event.timestamp)}</span><span className={`mono source ${statusClass(event.status)}`}>{event.status}</span><span className="message">{event.message}</span></div>)}{!history.data?.history?.length && <div className="empty">No events yet.</div>}</div>
      </section>
      </>}
      {activePage === 'Incidents' && <IncidentPage decisions={decisions.data} history={history.data} />}
      {activePage === 'Approvals' && <ApprovalPage list={list} onDone={pending.refresh} />}
      {activePage === 'Remediation' && <RemediationPage decisions={decisions.data} history={history.data} />}
      {activePage === 'Safety policies' && <SafetyPage />}
      {activePage === 'Logs / Loki' && <LogPage history={history.data} />}
      {activePage === 'Infrastructure' && <InfrastructurePage infra={infra.data} points={points} />}
    </main>
  </div>
}

function PageHeader({ page }) { return <div className="page-heading"><div className="eyebrow">Monitor / {page}</div><h2>{page}</h2></div> }

function EventRow({ event }) { return <div className="event"><span className="mono dm">{hhmmss(event.timestamp)}</span><span className={`mono source ${statusClass(event.status)}`}>{event.status}</span><span className="message">{event.message}</span></div> }

function IncidentPage({ decisions, history }) {
  const rows = decisions?.recent ?? []
  return <div className="page-grid"><div className="card"><CardHead title="Recent incidents" sub={`${rows.length} decisions`} />{rows.length ? rows.map((item) => <div className="data-row" key={item.id}><div><strong>{item.incident_id || 'Unassigned incident'}</strong><div className="mu small">{item.reason || 'No reason recorded'}</div></div><span className={`eyebrow ${statusClass(item.outcome)}`}>{item.outcome || item.mode}</span><span className="mono tiny dm">{hhmm(item.timestamp)}</span></div>) : <div className="empty">No incidents have been recorded yet.</div>}</div><div className="card"><CardHead title="Recent outcomes" sub="Audit history" />{(history?.history ?? []).map((event, index) => <EventRow event={event} key={`${event.action_id}-${index}`} />)}</div></div>
}

function ApprovalPage({ list, onDone }) { return <div className="card"><CardHead title="Approval queue" sub={`${list.length} pending`} />{list.length ? list.map((item, index) => <ApprovalRow key={item.action_id} approval={item} first={!index} onDone={onDone} />) : <div className="empty tall">No critical actions are waiting for approval.</div>}</div> }

function RemediationPage({ decisions, history }) { return <div className="page-grid"><div className="card"><CardHead title="Decision engine" sub="Latest actions" />{(decisions?.recent ?? []).map((item) => <div className="data-row" key={item.id}><div><strong>{item.action_type || 'No action selected'}</strong><div className="mu small">{item.reason || 'No decision reason'}</div></div><span className="mono tiny am-t">{item.confidence != null ? `${Math.round(item.confidence * 100)}% confidence` : 'Escalated'}</span></div>)}{!decisions?.recent?.length && <div className="empty">No remediation decisions yet.</div>}</div><div className="card"><CardHead title="Execution history" sub="Safety audit" />{(history?.history ?? []).map((event, index) => <EventRow event={event} key={`${event.action_id}-${index}`} />)}</div></div> }

function SafetyPage() { const controls = [['Rate limit', 'enabled'], ['Circuit breaker', 'closed'], ['Human approval', 'enabled'], ['Kill switch', 'normal'], ['Blast radius', 'limited']]; return <div className="card"><CardHead title="Safety policies" sub="Guardrails" /><div className="policy-grid">{controls.map(([label, value]) => <div className="policy" key={label}><span className="dot ok" /><div><strong>{label}</strong><div className="mu small">{value}</div></div></div>)}</div><div className="notice">Destructive actions remain supervised and require an explicit approval.</div></div> }

function LogPage({ history }) { return <div className="card"><CardHead title="Logs / Loki" sub="Latest events" />{(history?.history ?? []).map((event, index) => <div className="log-row" key={`${event.action_id}-${index}`}><span className="mono dm">{hhmmss(event.timestamp)}</span><span className={`eyebrow ${statusClass(event.status)}`}>{event.status}</span><span>{event.message || 'No message'}</span></div>)}{!history?.history?.length && <div className="empty tall">No log events available.</div>}</div> }

function InfrastructurePage({ infra, points }) { return <><div className="card"><CardHead title="Infrastructure telemetry" sub={infra?.source || 'Prometheus'} /><div className="infra-grid"><Metric label="CPU" value={formatPercent(infra?.cpu_percent)} tone="ok" /><Metric label="Memory" value={formatPercent(infra?.memory_percent)} tone="ok" /><Metric label="Network receive" value={formatRate(infra?.network_receive_bytes_per_second)} tone="am" /><Metric label="Network transmit" value={formatRate(infra?.network_transmit_bytes_per_second)} tone="am" /><Metric label="Prometheus" value={infra?.prometheus_up === 1 ? 'up' : '--'} tone="ok" /><Metric label="Node exporter" value={infra?.node_exporter_up === 1 ? 'up' : '--'} tone="ok" /></div></div><div className="card"><CardHead title="CPU history" sub={`${points.length} samples`} /><Chart points={points} /></div></> }

function Metric({ label, value, tone }) { return <div className="metric"><div className="eyebrow mu">{label}</div><strong className={tone}>{value}</strong></div> }

function Sidebar({ active, onNavigate, pending, escalated, lastAction }) {
  const badges = { Incidents: escalated, Approvals: pending }
  return <aside className="side"><div className="logo"><span className="ring" /><div><div className="brand">Warden</div><div className="eyebrow small-eyebrow">DevOps agent</div></div></div><nav><div className="eyebrow small-eyebrow">Monitor</div>{NAV.map((name) => <button type="button" key={name} className={`nav ${active === name ? 'on' : ''}`} onClick={() => onNavigate(name)}><i className="dot" /><span>{name}</span>{badges[name] > 0 && <b className={`badge ${name === 'Approvals' ? 'hot' : ''}`}>{badges[name]}</b>}</button>)}</nav><div className="grow" /><div className="agent"><div className="eyebrow small-eyebrow">Agent</div><div className="row gap8"><i className="dot ok" /><strong>Supervised mode</strong></div><span className="mu">Last action {lastAction}</span></div></aside>
}

const CardHead = ({ title, sub }) => <div className="chead"><span>{title}</span><span className="eyebrow">{sub}</span></div>
function Kpi({ label, value, unit, sub, tone, accent }) { return <div className="card kpi"><div className="eyebrow mu">{label}</div><div className="val"><span className={accent ? 'am-t' : ''}>{value}</span>{unit && <small>{unit}</small>}</div><div className={`mono sub ${tone}`}>{sub}</div></div> }

function Chart({ points }) {
  if (points.length < 2) return <div className="empty tall">Collecting CPU samples from Prometheus...</div>
  const width = 720
  const x = (index) => (index * width) / (points.length - 1)
  const y = (value) => 190 - Math.min(Math.max(value, 0), 100) * 1.7
  const path = (items, offset = 0) => items.map((point, index) => `${index ? 'L' : 'M'}${x(index + offset).toFixed(1)} ${y(point.v).toFixed(1)}`).join(' ')
  const cross = points.findIndex((point) => point.v > THRESHOLD)
  const hotOffset = Math.max(cross - 1, 0)
  const hot = cross === -1 ? [] : points.slice(hotOffset)
  const ticks = [0, 1, 2, 3].map((index) => hhmm(points[Math.round((index * (points.length - 1)) / 3)].t))
  return <><div className="chart"><svg viewBox="0 0 720 210" preserveAspectRatio="none">{[30, 80, 130, 180].map((line) => <line key={line} x1="0" x2={width} y1={line} y2={line} className="grid" vectorEffect="non-scaling-stroke" />)}<path d={`${path(points)} L${width} 190 L0 190 Z`} className="area" /><line x1="0" x2={width} y1={y(THRESHOLD)} y2={y(THRESHOLD)} className="threshold" vectorEffect="non-scaling-stroke" /><path d={path(cross === -1 ? points : points.slice(0, cross))} className="cold" vectorEffect="non-scaling-stroke" />{hot.length > 1 && <path d={path(hot, hotOffset)} className="hot" vectorEffect="non-scaling-stroke" />}</svg><span className="eyebrow threshold-label" style={{ top: y(THRESHOLD) - 18 }}>Threshold {THRESHOLD}%</span>{cross !== -1 && <><i className="marker" style={{ left: `${(x(cross) / width) * 100}%`, top: y(points[cross].v) }} /><span className="anomaly" style={{ right: `calc(${100 - (x(cross) / width) * 100}% + 22px)`, top: y(points[cross].v) - 22 }}>Anomaly detected · {hhmm(points[cross].t)}</span></>}</div><div className="ticks mono">{ticks.map((tick) => <span key={tick}>{tick}</span>)}</div></>
}

function Pipeline({ last, infra, cpu, pending }) {
  const human = last && last.mode !== 'AUTO_EXECUTE'
  const waiting = human && pending > 0
  const time = hhmm(last?.timestamp)
  const steps = [['Collect', typeof cpu === 'number' ? `CPU ${cpu.toFixed(0)}% · Prometheus ${infra?.prometheus_up ? 'up' : 'down'}` : 'Waiting for Prometheus', 'now', typeof cpu === 'number' ? 'done' : 'idle'], ['Detect', last ? `Incident ${String(last.incident_id ?? last.id).slice(0, 8)}` : 'No incident', time, last ? 'done' : 'idle'], ['Diagnose', last?.reason ?? 'No diagnosis yet', time, last?.reason ? 'done' : 'idle'], ['Remediate', last?.action_type ?? 'No plan yet', time, last?.action_type ? 'done' : 'idle'], ['Safety check', !last ? 'Idle' : human ? 'Human approval required' : 'Policy passed · auto-execute', time, last ? 'done' : 'idle'], ['Execute', waiting ? 'Awaiting your approval' : last?.outcome ?? (last ? 'Executed' : 'Idle'), waiting ? 'now' : time, waiting ? 'active' : last ? 'done' : 'idle']]
  return <div className="card pipe"><CardHead title="Agent pipeline" sub={last ? `Incident ${String(last.incident_id ?? last.id).slice(0, 8)}` : 'Idle'} />{steps.map(([name, description, stamp, state]) => <div className="step" key={name}><i className={`dot ${state === 'active' ? 'am' : state === 'done' ? 'ok' : 'off'} big`} /><div className="grow"><div className={state === 'active' ? 'am-t strong' : 'strong'}>{name}</div><div className="mu small">{description}</div></div><span className={`mono tiny ${state === 'active' ? 'am-t' : 'dm'}`}>{stamp}</span></div>)}</div>
}

function ApprovalRow({ approval, first, onDone }) {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const act = async (decision) => { setBusy(decision); setError(null); try { await api.decide(approval.action_id, decision); await onDone() } catch (err) { setError(err.message) } finally { setBusy(null) } }
  const tone = severityClass(approval.severity)
  return <div className={`approval-row ${first ? 'first' : ''}`}><div className="grow"><div className="approval-title">{approval.reason || approval.executor}</div><div className="row gap10 mono approval-meta"><span className="mu">{[approval.executor, params(approval.params)].filter(Boolean).join(' · ')}</span><i className="sep" /><i className={`dot ${tone}`} /><span className={`eyebrow ${tone}`}>Risk {approval.severity}</span><i className="sep" /><span className="eyebrow mu">Requested {hhmm(approval.requested_at)}</span></div>{error && <div className="mono cr small">{error}</div>}</div><button className="btn" disabled={Boolean(busy)} onClick={() => act('reject')}>{busy === 'reject' ? '...' : 'Reject'}</button><button className="btn pri" disabled={Boolean(busy)} onClick={() => act('approve')}>{busy === 'approve' ? 'Executing...' : 'Approve'}</button></div>
}
