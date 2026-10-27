import { useEffect, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8000`
const LIMIT = 60
const doorNames = { open: 'Abierta', closed: 'Cerrada', opening: 'Abriendo', closing: 'Cerrando', unknown: 'Sin referencia', paused: 'En pausa', sensor_fault: 'Detenida por sensor' }

function Chart({ history }) {
  const valid = history.filter(r => r.ok)
  if (valid.length < 2) return <div className="chart-empty">Recopilando lecturas para la gráfica…</div>
  const low = Math.min(23, ...valid.map(r => r.temperature))
  const high = Math.max(35, ...valid.map(r => r.temperature))
  const y = v => 130 - (v - low) / (high - low) * 110
  const first = valid[0].timestamp, span = valid.at(-1).timestamp - first || 1
  return <svg className="chart" viewBox="0 0 740 160" role="img" aria-label="Historial de temperatura con rango objetivo de 26 a 32 grados">
    <rect x="42" y={y(32)} width="650" height={y(26) - y(32)} fill="#dcefe6" />
    {[26, 32].map(v => <g key={v}><line x1="42" x2="692" y1={y(v)} y2={y(v)} stroke="#8bba9f" strokeDasharray="5 5" /><text x="5" y={y(v) + 4}>{v}°</text></g>)}
    <polyline points={valid.map(r => `${42 + (r.timestamp - first) / span * 650},${y(r.temperature)}`).join(' ')} fill="none" stroke="#21795d" strokeWidth="3" strokeLinejoin="round" />
    <text x="42" y="153">{new Date(first * 1000).toLocaleTimeString()}</text><text x="692" y="153" textAnchor="end">{new Date(valid.at(-1).timestamp * 1000).toLocaleTimeString()}</text>
  </svg>
}

export default function App() {
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [received, setReceived] = useState(0)
  useEffect(() => {
    let cancelled = false, socket, retry
    fetch(`${API}/api/temperature/history`).then(r => r.json()).then(rows => {
      if (!cancelled) setHistory(prev => [...rows, ...prev].filter((r, i, a) => a.findIndex(x => x.timestamp === r.timestamp) === i).sort((a, b) => a.timestamp - b.timestamp).slice(-LIMIT))
    }).catch(() => {})
    function connect() {
      socket = new WebSocket(API.replace(/^http/, 'ws') + '/ws/temperature')
      socket.onopen = () => { if (!cancelled) setConnected(true) }
      socket.onmessage = e => {
        if (cancelled) return
        try {
          const row = JSON.parse(e.data)
          setReceived(Date.now())
          setLatest(row)
          setHistory(prev => [...prev.filter(r => r.timestamp !== row.timestamp), row].slice(-LIMIT))
        } catch { /* Esperar la siguiente muestra completa. */ }
      }
      socket.onerror = () => socket.close()
      socket.onclose = () => {
        if (!cancelled) { setConnected(false); retry = setTimeout(connect, 2000) }
      }
    }
    connect()
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => { cancelled = true; clearTimeout(retry); clearInterval(timer); socket?.close() }
  }, [])
  const fresh = connected && now - received < 8000 && latest && now / 1000 - latest.timestamp < 8
  const sensor = fresh && latest?.ok
  const outputs = fresh && latest?.outputs_valid
  const temp = sensor ? latest.temperature : null
  const climate = temp === null ? 'Sin lectura' : temp < 26 ? 'Temperatura baja' : temp > 32 ? 'Temperatura alta' : 'Dentro del rango'
  const live = fresh && latest?.serial_connected
  const alarm = outputs ? latest.alarm : null
  return <main className="dashboard">
    <header><div className="brand"><span className="brand-icon">◒</span><div><span className="eyebrow">MONITOREO DEL CRIADERO</span><h1>Un vistazo al ambiente</h1></div></div><span className={`badge ${live ? 'good' : 'neutral'}`}><i />{live ? 'Arduino conectado' : 'Esperando conexión'}</span></header>
    <section className={`summary ${sensor && temp >= 26 && temp <= 32 ? 'normal' : 'warning'}`}>
      <div><span className="eyebrow">ESTADO DEL AMBIENTE</span><h2>{climate}</h2><p>Rango objetivo <strong>26–32 °C</strong> · Lectura del DHT11 cada 2,5 segundos</p></div>
      <div className="mode"><span className="eyebrow">CONTROL</span><strong>{outputs ? latest.stopped ? 'En pausa' : 'Automático' : 'Sin datos actuales'}</strong></div>
    </section>
    {(!live || (latest && !latest.ok)) && <p className="notice" role="status">{!live ? 'Esperando telemetría actual. Los estados anteriores no se muestran como activos.' : latest.error || 'Esperando una lectura válida del sensor en A1.'}</p>}
    <section className="cards" aria-label="Sensores y salidas">
      <article className="card"><div className="card-top"><span>Temperatura</span><span className="pin">A1 · DHT11</span></div><div className="value">{temp ?? '—'}<small>°C</small></div><p>Objetivo: 26 a 32 °C</p><div className="mini-range"><span style={{ width: `${temp === null ? 0 : Math.max(0, Math.min(100, (temp - 15) / 30 * 100))}%` }} /></div></article>
      <article className="card"><div className="card-top"><span>Humedad</span><span className="pin">A1 · DHT11</span></div><div className="value">{sensor ? latest.humidity : '—'}<small>%</small></div><p>Humedad relativa del ambiente</p></article>
      <article className={`card ${alarm ? 'alert-card' : ''}`}><div className="card-top"><span>Alarma</span><span className="pin">A0 · Salida</span></div><div className="state-value">{alarm === null ? 'Sin datos' : alarm ? 'Activada' : 'Apagada'}</div><p>Señal de control · No confirma sonido</p><span className={`badge ${alarm === null ? 'neutral' : alarm ? 'danger' : 'good'}`}>{alarm === null ? 'Sin telemetría' : alarm ? 'Revisar ambiente o sensor' : 'Sin alerta del controlador'}</span></article>
      <article className="card"><div className="card-top"><span>Calefacción / foco</span><span className="pin">A2 · Salida</span></div><div className="state-value">{outputs ? latest.heater ? 'Encendido' : 'Apagado' : 'Sin datos'}</div><p>Enciende debajo de 26 °C<br />Se apaga desde 30 °C</p><span className={`badge ${outputs && latest.heater ? 'warm' : 'neutral'}`}>{outputs ? 'Orden enviada a la salida' : 'Sin telemetría'}</span></article>
    </section>
    <section className="lower-grid"><article className="panel"><div className="section-heading"><h2>Temperatura reciente</h2><span className="legend">Rango objetivo</span></div><Chart history={history} /><p className="subtle">Historial de lecturas recibidas · Las interrupciones no confirman continuidad.</p></article>
      <article className="panel door"><div className="section-heading"><h2>Puerta</h2><span className="pin">D8–D11</span></div><div className="state-value">{outputs ? doorNames[latest.door] || 'Sin datos' : 'Sin datos'}</div><div className="door-meter"><span style={{ width: `${outputs ? latest.door_percent ?? 0 : 0}%` }} /></div><div className="meter-labels"><span>Abierta</span><span>Cerrada</span></div><p>{outputs && latest.referenced ? `${latest.door_percent}% de cierre estimado` : 'Posición sin confirmar'}</p><p className="subtle">12 vueltas por recorrido · 6 RPM<br />Posición calculada por pasos, sin sensor de posición.</p></article></section>
    <section className="rules"><strong>Reglas automáticas</strong><span>≤32 °C: cerrar</span><span>&gt;32 °C por más de 5 min: abrir</span><span>Fuera de 26–32 °C: alarma inmediata</span></section>
    <footer><span>Vista de monitoreo · El Arduino mantiene el control autónomo.</span><span>{latest ? `Último dato: ${new Date(latest.timestamp * 1000).toLocaleTimeString()}` : 'Esperando primera lectura'}</span></footer>
  </main>
}
