import { useEffect, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8000`
const LIMIT = 60
const fmt = n => Number(n).toLocaleString('es-PE', { maximumFractionDigits: 2 })
const doorNames = { open: 'Abierta', closed: 'Cerrada', opening: 'Abriendo', closing: 'Cerrando', unknown: 'Sin referencia', paused: 'En pausa', sensor_fault: 'Detenida por sensor' }

function Chart({ history, profile }) {
  const valid = history.filter(r => r.ok)
  if (valid.length < 2) return <div className="chart-empty">Recopilando lecturas para la gráfica…</div>
  const low = Math.min(profile?.temp_min ?? 23, ...valid.map(r => r.temperature))
  const high = Math.max(profile?.temp_max ?? 35, ...valid.map(r => r.temperature))
  const y = v => 130 - (v - low) / (high - low) * 110
  const first = valid[0].timestamp, span = valid.at(-1).timestamp - first || 1
  return <svg className="chart" viewBox="0 0 740 160" role="img" aria-label="Historial de temperatura y rango del ciclo actual">
    {profile && <rect x="42" y={y(profile.temp_max)} width="650" height={y(profile.temp_min) - y(profile.temp_max)} fill="#dcefe6" />}
    {(profile ? [profile.temp_min, profile.temp_max] : []).map(v => <g key={v}><line x1="42" x2="692" y1={y(v)} y2={y(v)} stroke="#8bba9f" strokeDasharray="5 5" /><text x="5" y={y(v) + 4}>{v}°</text></g>)}
    <polyline points={valid.map(r => `${42 + (r.timestamp - first) / span * 650},${y(r.temperature)}`).join(' ')} fill="none" stroke="#21795d" strokeWidth="3" strokeLinejoin="round" />
    <text x="42" y="153">{new Date(first * 1000).toLocaleTimeString()}</text><text x="692" y="153" textAnchor="end">{new Date(valid.at(-1).timestamp * 1000).toLocaleTimeString()}</text>
  </svg>
}

function ManualPanel({ controls, available, pins }) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const [minutes, setMinutes] = useState({})
  const [hold, setHold] = useState({})
  async function send(output, mode) {
    setPending(true); setMessage('Esperando confirmación del Arduino…')
    try {
      const duration_seconds = hold[output] ? 0 : Number(minutes[output] ?? 5)*60
      const response = await fetch(`${API}/api/control`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ output, mode, duration_seconds: mode==='auto' ? 0 : duration_seconds }) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'No se confirmó la orden')
      setMessage(data.history_error || (data.control.mode === 'on' && !data.control.on ? `No se activó: ${data.control.blocked_reason || 'protección del firmware o pausa'}.` : 'Arduino confirmó el cambio. El estado se actualiza con la telemetría.'))
    } catch (error) { setMessage(error.message) }
    finally { setPending(false) }
  }
  return <section className="panel manual-panel" aria-label="Control manual"><h2>Control por salida</h2>
    <p>«Encender» actúa sobre esa salida incluso con el automático en pausa. «Detener salidas y motores» la apaga. Elige la duración de cada orden: la bomba se apaga al terminar; las otras salidas vuelven a automático. Puedes mantener una orden sin temporizador con su casilla. Las protecciones siguen activas. El control arranca en automático, con las salidas apagadas hasta confirmar sensor y ciclo. Cambiar de pin confirmado devuelve calefacción y ventilador a automático. La motobomba es solo manual y permanece apagada hasta que pulses Encender.</p>
    {[['heater','Calefacción','D9'],['humidifier','Motobomba','D7'],['exhaust','Ventilador','D8'],['intake','Entrada de aire','A5'],['alarm','Alarma','A0']].filter(([key]) => key !== 'intake' || Boolean(pins?.intake)).map(([key,label,pin]) => {
      pin = pins?.[key] || pin
      if (pins?.heater === 'D9' && key === 'humidifier') label = 'Motobomba'
      if (pins?.heater === 'D9' && key === 'exhaust') label = 'Ventilador'
      const current = available ? controls?.[key] : null
      const durationValid = hold[key] || (Number.isInteger(Number(minutes[key] ?? 5)) && Number(minutes[key] ?? 5)>=1 && Number(minutes[key] ?? 5)<=1440)
      return <div className="manual-row" key={key}><div><strong>{label} · {pin}</strong><p>{current ? `${({auto:'Automático',off:'Manual apagado',on:'Manual encendido'})[current.mode]} · Salida ${current.on ? 'activada' : 'desactivada'}` : 'Sin confirmación actual'}</p></div>
        {current?.mode==='on' && !current.on && <p className="notice" role="status">Bloqueada: {current.blocked_reason || 'protección del firmware o pausa'}</p>}
        <div className="manual-actions"><label>Duración (min) <input aria-label={`Minutos ${label}`} type="number" min="1" max="1440" step="1" value={minutes[key] ?? 5} disabled={hold[key] || pending} onChange={e=>setMinutes({...minutes,[key]:e.target.value})} /></label><label><input type="checkbox" checked={hold[key] || false} disabled={pending} onChange={e=>setHold({...hold,[key]:e.target.checked})} /> {key==='humidifier' ? 'Hasta pulsar Apagar' : 'Hasta pulsar Automático'}</label>
        {current && current.mode!=='auto' && (key!=='humidifier' || current.mode==='on') && <p>{current.remaining_seconds>0 ? `${key==='humidifier' ? 'Se apaga' : 'Vuelve a automático'} en ${Math.ceil(current.remaining_seconds/60)} min (${current.remaining_seconds} s)` : key==='humidifier' ? 'Sin temporizador: se detiene con Apagar' : 'Sin temporizador: vuelve con Automático'}</p>}
        <div className="manual-buttons">{[['on','Encender'],['off','Apagar'],['auto','Automático']].filter(([mode])=>key!=='humidifier' || mode!=='auto').map(([mode,text]) => <button key={mode} disabled={!current || pending || (mode!=='auto' && !durationValid)} aria-pressed={current?.mode === mode} onClick={() => send(key,mode)}>{text}</button>)}</div></div></div>
    })}
    <p role="status">{message}</p><p className="subtle">El estado confirma la orden eléctrica; no mide giro, calor ni sonido. Apagar manualmente la alarma silencia su salida durante el tiempo elegido; la alerta visual continúa.</p>
  </section>
}

function DevicePanel({ latest, available }) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const supported = available && ['BROODER_12_PIN_REMAP','BROODER_13_MANUAL_DOOR','BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP'].includes(latest?.firmware_reported)
  const physical = latest?.cycle_selection!=='software'
  const servo = supported ? latest?.servo : null
  async function send(action, cycle) {
    setPending(true)
    setMessage('Esperando confirmación del Arduino…')
    try {
      const response = await fetch(`${API}/api/device`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action, ...(cycle ? {cycle} : {})}) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'No se confirmó la orden')
      setMessage(data.history_error || ({servo_cycle:'Ciclo del servo iniciado.',stop:'Automático en pausa; salidas manuales y motores detenidos. La alarma mantiene su modo.',resume:'Calefacción y ventilador devueltos a automático.',cycle:`Ciclo ${cycle} solicitado; esperando dos lecturas válidas.`})[action])
    } catch(error) { setMessage(error.message) }
    finally { setPending(false) }
  }
  return <section className="panel device-panel" aria-label="Control del criadero">
    <div className="section-heading"><h2>Control del criadero</h2><span className="badge neutral">{supported ? latest.stopped ? 'Automático en pausa' : 'Reanudado' : 'Sin conexión actual'}</span></div>
    <div className="device-controls"><button disabled={!supported} onClick={()=>send('stop')}>Detener salidas y motores</button><button disabled={!supported || pending || !latest?.ok} onClick={()=>send('resume')}>Activar automático</button></div>
    <p>Activar automático devuelve calefacción y ventilador al rango del ciclo detectado. Cambiar el sensor a otro pin confirmado también restaura esos dos modos; una parada explícita se mantiene hasta activar automático.</p>
    <h3>Ciclo de crianza · {physical ? 'selección por cable D2–D5' : 'sensor D5'}</h3>
    {physical ? <p>Mueve la señal del único sensor: D2 → ciclo 1; D3 → ciclo 2; D4 → ciclo 3; D5 → ciclo 4. Se confirma con dos lecturas consecutivas. No se selecciona por botones.</p> : <><div className="device-controls">{[1,2,3,4].map(id=><button key={id} disabled={!supported || pending} aria-pressed={supported && latest.requested_cycle===id} onClick={()=>send('cycle',id)}>Seleccionar ciclo {id}</button>)}</div><p>El sensor permanece en D5. Cada cambio espera dos lecturas válidas antes de habilitar el control.</p></>}
    <div className="servo-control"><div><h3>Servomotor · D6</h3><strong>{servo ? servo.running ? `En movimiento · ${servo.remaining_seconds} s restantes` : 'Sin ciclo en curso' : 'Sin estado actual'}</strong><p>180° durante 10 s, espera de 3 s y regreso a 130° durante 9 s. Ejecuta una sola vez.</p>{servo?.last_angle !== null && servo?.last_angle !== undefined && <p>Última orden: {servo.last_angle}°. La posición se confirma observando el motor.</p>}</div><button disabled={!supported || !servo || pending || servo.running} onClick={()=>send('servo_cycle')}>Ejecutar ciclo del servo</button></div>
    <p role="status">{message}</p><p className="subtle">A0: alarma · D2–D5: sensor y selección de ciclo · D6: servo · D7: motobomba · D8: ventilador · D9: calefacción · D10–D13: motor de puerta. A1–A5 libres. Puerta con control manual y referencia física antes del movimiento.</p>
  </section>
}

function DoorPanel({ latest, available }) {
  const [pending,setPending] = useState(false)
  const [confirmed,setConfirmed] = useState(false)
  const [message,setMessage] = useState('')
  const supported = available && ['BROODER_13_MANUAL_DOOR','BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP'].includes(latest?.firmware_reported) && latest?.door_control
  const running = supported && latest.door_control.running
  async function send(action) {
    setPending(true); setMessage('Esperando confirmación de puerta…')
    try {
      const response = await fetch(`${API}/api/device`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...(action.startsWith('door_reference_') ? {confirmed_position:confirmed} : {})})})
      const data = await response.json()
      if(!response.ok) throw new Error(data.detail || 'Sin confirmación de puerta')
      setMessage(data.history_error || ({door_open:'Apertura solicitada.',door_close:'Cierre solicitado.',door_stop:'Motor detenido.',door_reference_open:'Posición abierta registrada, sin mover el motor.',door_reference_closed:'Posición cerrada registrada, sin mover el motor.'})[action])
      if(action.startsWith('door_reference_')) setConfirmed(false)
    } catch(error) {setMessage(error.message)}
    finally {setPending(false)}
  }
  return <article className="panel device-panel door" aria-label="Control de puerta">
    <div className="section-heading"><h2>Puerta</h2><span className="pin">D10–D13</span></div>
    <div className="state-value">{supported ? doorNames[latest.door] || 'Sin datos' : 'Esperando firmware de puerta'}</div>
    {supported && <p>{latest.referenced ? `Recorrido estimado: ${latest.door_percent}% cerrado.` : 'Primero confirma la posición física en un extremo.'} {running ? 'Motor en marcha.' : 'Motor detenido.'}</p>}
    <div className="device-controls"><button disabled={!supported || pending || running || !latest?.referenced} onClick={()=>send('door_open')}>Abrir puerta</button><button disabled={!supported || pending || running || !latest?.referenced} onClick={()=>send('door_close')}>Cerrar puerta</button><button disabled={!supported} onClick={()=>send('door_stop')}>Detener puerta</button></div>
    <details><summary>Confirmar posición física</summary><p>Estos botones registran el extremo actual; no mueven la puerta. Selecciona únicamente el extremo donde realmente está.</p><label><input type="checkbox" checked={confirmed} disabled={!supported || running || pending} onChange={e=>setConfirmed(e.target.checked)} /> He comprobado físicamente la posición de la puerta</label><div className="device-controls"><button disabled={!supported || running || pending || !confirmed} onClick={()=>send('door_reference_open')}>Está totalmente abierta</button><button disabled={!supported || running || pending || !confirmed} onClick={()=>send('door_reference_closed')}>Está totalmente cerrada</button></div></details>
    <p role="status">{message}</p><p className="subtle">Control manual independiente del automático del clima. Posición estimada por pasos, sin finales de carrera. Recorrido configurado: 12 vueltas. Si está a medio recorrido y sin referencia, primero debe colocarse en un extremo con el montaje desconectado.</p>
  </article>
}

function EventPanel() {
  const [result,setResult] = useState({events:[],page:1,pages:1,total:0,snapshot_id:0})
  const [error,setError] = useState('')
  const [filter,setFilter] = useState('all')
  const [view,setView] = useState({page:1,snapshot:null})
  const [loading,setLoading] = useState(true)
  useEffect(() => {
    const controller=new AbortController()
    let timer
    async function refresh() {
      try {
        const params=new URLSearchParams({page:view.page,page_size:25,kind:filter})
        if(view.snapshot !== null) params.set('snapshot_id',view.snapshot)
        const response=await fetch(`${API}/api/events?${params}`,{signal:controller.signal})
        if(!response.ok) throw new Error('No se pudo consultar el historial')
        const data=await response.json()
        if(!controller.signal.aborted) {
          setResult(data)
          setError(data.error ? 'No se están guardando nuevos registros; revisa el almacenamiento del servidor.' : '')
        }
      } catch(error) {if(!controller.signal.aborted)setError(error.message)}
      finally {
        if(!controller.signal.aborted) {
          setLoading(false)
          if(view.page===1 && view.snapshot===null) timer=setTimeout(refresh,5000)
        }
      }
    }
    refresh()
    return()=>{controller.abort();clearTimeout(timer)}
  },[filter,view])
  function navigate(page) {
    setLoading(true);setError('')
    setView({page,snapshot:result.snapshot_id})
  }
  function latest() {setLoading(true);setError('');setView({page:1,snapshot:null})}
  return <section className="panel event-panel" aria-label="Historial de cambios">
    <div className="section-heading"><h2>Historial de cambios</h2><label>Mostrar <select value={filter} onChange={e=>{setFilter(e.target.value);latest()}}><option value="all">Todos</option><option value="reading">Temperatura y humedad</option><option value="output">Encendidos y modos</option><option value="configuration">Configuraciones</option><option value="command">Mandos y resultados</option><option value="system">Reinicios y STOP</option><option value="alarm">Alertas</option><option value="connection">Conexión</option></select></label></div>
    <p>Registros guardados en el servidor, incluso al cerrar esta página. 25 eventos por página. El servidor debe estar encendido para registrar.</p>
    <div className="history-actions"><a href={`${API}/api/history/readings.csv`}>Descargar lecturas CSV</a><a href={`${API}/api/history/events.csv?kind=${filter}`}>Descargar eventos CSV{filter!=='all' ? ' (filtro actual)' : ''}</a><a href={`${API}/api/history/configurations.csv`}>Descargar configuraciones CSV</a></div>
    <p className="subtle">Cada lectura y evento nuevo incluye config_id y session_id para relacionar ajustes y resultados. Las versiones conservan rangos, modos, pines y reglas del software. CSV completo: fecha UTC, temperatura, humedad, ciclo, salidas y modos. Estados: 1 = activo, 0 = inactivo; vacío = desconocido. Las lecturas incluyen cada telemetría recibida, aunque el valor no cambie.</p>
    {error && <p role="status" className="notice">{error}</p>}
    <div className="event-scroll" aria-busy={loading}><table><thead><tr><th>Fecha y hora</th><th>Cambio observado</th><th>Ambiente</th></tr></thead><tbody>
      {loading ? <tr><td colSpan="3">Cargando página…</td></tr> : result.events.map(event=><tr key={event.id} data-event-id={event.id}><td>{new Date(event.timestamp*1000).toLocaleString('es-PE')}</td><td>{event.message}<small>{event.context.cycle ? `Ciclo ${event.context.cycle}` : 'Sin ciclo'}{event.context.heater_off != null ? ` · Foco: ON ≤${event.context.heater_on} °C / OFF ≥${event.context.heater_off} °C` : ''}{event.context.stopped ? ' · STOP activo' : ''}{!event.context.sensor_valid ? ' · Sensor sin lectura válida' : ''}{event.context.sample?.config_id && <> · <a href={`${API}/api/configurations/${event.context.sample.config_id}`}>Configuración #{event.context.sample.config_id}</a></>}</small></td><td>{event.context.temperature == null ? 'Sin lectura' : `${event.context.temperature} °C · ${event.context.humidity} %`}</td></tr>)}
      {!loading && !result.events.length && <tr><td colSpan="3">Todavía no hay cambios registrados en esta categoría.</td></tr>}
    </tbody></table></div>
    <nav className="history-pagination" aria-label="Páginas del historial"><button disabled={loading || !!error || result.page<=1} onClick={()=>navigate(result.page-1)}>Anterior</button><span aria-live="polite">Página {result.page} de {result.pages} · {result.total} eventos</span><button disabled={loading || !!error || result.page>=result.pages} onClick={()=>navigate(result.page+1)}>Siguiente</button><button disabled={loading} onClick={latest}>Ver más recientes</button></nav>
    <p className="subtle">{view.snapshot===null ? 'Actualización cada 5 segundos.' : 'Vista fija para recorrer páginas sin saltos. Pulsa «Ver más recientes» para actualizar.'} Horas de la tabla según tu dispositivo; CSV en UTC. Los encendidos son órdenes reportadas por el Arduino; no confirman luz o giro físicos. Durante una desconexión no se reconstruyen los cambios perdidos.</p>
  </section>
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
  const cycle = fresh && latest?.cycle?.valid ? latest.cycle : null
  const profile = cycle?.id ? cycle : null
  const range = profile ? `${profile.temp_min}–${profile.temp_max} °C` : 'Sin ciclo confirmado'
  const humidityRange = profile ? `${profile.humidity_min}–${profile.humidity_max} %` : 'Sin ciclo confirmado'
  const remapped = ['BROODER_12_PIN_REMAP','BROODER_13_MANUAL_DOOR','BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP'].includes(latest?.firmware_reported)
  const physical = latest?.cycle_selection!=='software'
  const sensorPin = fresh ? latest?.pins?.temperature || 'D2–D5' : 'D2–D5'
  const climate = temp === null ? 'Sin lectura' : !profile ? 'Sin ciclo confirmado' : temp < profile.temp_min ? 'Temperatura baja' : temp > profile.temp_max ? 'Temperatura alta' : latest.humidity < profile.humidity_min ? 'Humedad baja' : latest.humidity > profile.humidity_max ? 'Humedad alta' : 'Dentro de los rangos'
  const live = fresh && latest?.serial_connected
  const alarm = outputs ? latest.alarm : null
  const alert = outputs && latest?.alert?.valid ? latest.alert : null
  const alarmLabel = alarm === null ? 'Sin datos' : alert?.recovering ? 'Recuperando' : alarm ? 'Alerta confirmada' : alert?.pending ? 'Confirmando desvío' : 'Sin alerta'
  const alarmTone = alarm === null ? 'neutral' : alert?.recovering || alert?.pending ? 'warm' : alarm ? 'danger' : 'good'
  const reasons = alert ? [[1,'Temperatura baja'],[2,'Temperatura alta'],[4,'Humedad baja'],[8,'Humedad alta'],[16,'Sensor o ciclo sin confirmar'],[32,'Puerta sin referencia']].filter(([bit]) => alert.reasons & bit).map(([,text]) => text).join(' · ') : ''
  return <main className="dashboard">
    <header><div className="brand"><span className="brand-icon">◒</span><div><span className="eyebrow">MONITOREO DEL CRIADERO</span><h1>Un vistazo al ambiente</h1></div></div><span className={`badge ${live ? 'good' : 'neutral'}`}><i />{live ? 'Arduino conectado' : 'Esperando conexión'}</span></header>
    <section className={`summary ${sensor && profile && temp >= profile.temp_min && temp <= profile.temp_max && latest.humidity >= profile.humidity_min && latest.humidity <= profile.humidity_max ? 'normal' : 'warning'}`}>
      <div><span className="eyebrow">ESTADO DEL AMBIENTE</span><h2>{climate}</h2><p>Rango objetivo <strong>{range}</strong> · Lectura del DHT11 cada 2,5 segundos</p></div>
      <div className="mode"><span className="eyebrow">CONTROL</span><strong>{outputs ? latest.stopped ? 'Automático en pausa' : 'Automático' : 'Sin datos actuales'}</strong></div>
    </section>
    {(!live || (latest && !latest.ok)) && <p className="notice" role="status">{!live ? 'Esperando telemetría actual. Los estados anteriores no se muestran como activos.' : latest.error || 'Esperando una lectura válida del sensor.'}</p>}
    <section className="panel cycle-panel" aria-label="Ciclo de crianza">
      <div className="section-heading"><h2>{profile ? `Ciclo ${profile.id} · Días ${profile.days}` : 'Esperando selección de ciclo'}</h2><span className="pin">{sensorPin}</span></div>
      <p>{profile ? `Rangos: ${range} · Humedad ${humidityRange}` : remapped && !physical ? 'Sensor en D5. Selecciona el ciclo en los controles del criadero; se confirma con dos lecturas consecutivas.' : 'Conecta la señal del sensor a un solo pin: D2, D3, D4 o D5. Se confirma con dos lecturas consecutivas.'}</p>
      {physical && fresh && latest?.sensor_diagnostics && <p className="subtle">Respuesta del sensor: {Object.entries(latest.sensor_diagnostics.pins).map(([pin,code])=>`${pin}: ${['lectura válida','sin respuesta','respuesta bloqueada','respuesta bloqueada','datos incompletos','datos incompletos','checksum incorrecto','fuera de rango','pendiente'][code]}`).join(' · ')}</p>}
      {profile && <p className="center-target">Calefacción: enciende a ≤<strong>{fmt(profile.heater_on)} °C</strong>, apaga a ≥<strong>{fmt(profile.heater_off)} °C</strong>. Humedad objetivo: <strong>{fmt(profile.humidity_target)} % HR</strong>.</p>}
      <div className="cycle-options">{[['D2','1–3','33–34','60–70'],['D3','4–7','30–32','50–65'],['D4','8–14','27–29','50–60'],['D5','15–21','24–27','50–60']].map(([pin,days,t,h],i) => <div key={pin} className={profile?.id === i+1 ? 'cycle-option selected' : 'cycle-option'}><strong>Ciclo {i+1} · {remapped && !physical ? 'D5' : pin}</strong><span>Días {days}</span><span>{t} °C · {h} % HR</span></div>)}</div>
      <p className="subtle">{remapped && !physical ? 'Selección desde los controles; el sensor permanece en D5.' : 'Selección manual por conexión del sensor.'} El Arduino no calcula la edad ni cambia de ciclo por fecha.</p>
    </section>
    <section className="cards" aria-label="Sensores y salidas">
      <article className="card"><div className="card-top"><span>Temperatura</span><span className="pin">{sensorPin} · DHT11</span></div><div className="value">{temp ?? '—'}<small>°C</small></div><p>Objetivo: {range}</p><div className="mini-range"><span style={{ width: `${temp === null ? 0 : Math.max(0, Math.min(100, (temp - 15) / 30 * 100))}%` }} /></div></article>
      <article className="card"><div className="card-top"><span>Humedad</span><span className="pin">{sensorPin} · DHT11</span></div><div className="value">{sensor ? latest.humidity : '—'}<small>%</small></div><p>Objetivo: {humidityRange}</p></article>
      <article className={`card ${alarm && !alert?.recovering ? 'alert-card' : ''}`} aria-label="Alarma"><div className="card-top"><span>Alarma</span><span className="pin">A0 · Salida</span></div><div className="state-value">{alarmLabel}</div><p>{reasons || 'Sin desvío confirmado'}</p><span className={`badge ${alarmTone}`}>{alarm === null ? 'Sin telemetría' : alert?.recovering ? 'Comprobando estabilidad' : alarm ? 'Aviso de 1 s cada minuto' : alert?.pending ? 'Filtrando lectura transitoria' : 'Ambiente vigilado'}</span><p className="subtle">Fuera de rango: 30 s · Fallo: 10 s<br />La salida no confirma sonido físico.</p></article>
      <article className="card"><div className="card-top"><span>Calefacción / foco</span><span className="pin">{latest?.pins?.heater || 'D9'} · Salida</span></div><div className="state-value">{outputs ? latest.heater ? 'Encendido' : 'Apagado' : 'Sin datos'}</div><p>{profile ? `Enciende a ≤${fmt(profile.heater_on)} °C` : 'Esperando ciclo'}<br />{profile ? `Apaga a ≥${fmt(profile.heater_off)} °C` : 'Sin rango activo'}</p><span className={`badge ${outputs && latest.heater ? 'warm' : 'neutral'}`}>{outputs ? 'Orden enviada a la salida' : 'Sin telemetría'}</span></article>
    </section>
    <section className="panel fan-panel" aria-label="Sistema de aireación"><div className="section-heading"><h2>Sistema de aireación</h2><span className="pin">{remapped ? 'D7 · D8' : 'D7 · A4 · A5'}</span></div>
      <div className="air-grid">
        <article><div className="card-top"><span>{remapped ? 'Motobomba' : 'Humedad interna'}</span><span className="pin">D7</span></div><div className="state-value">{cycle ? cycle.humidifier ? 'Encendido' : 'Apagado' : 'Sin datos'}</div><p>Solo manual: Encender/Apagar. La humedad y el cambio de ciclo no encienden la bomba.</p></article>
        <article><div className="card-top"><span>{remapped ? 'Ventilador' : 'Extracción'}</span><span className="pin">{latest?.pins?.exhaust || 'D8'}</span></div><div className="state-value">{cycle ? cycle.exhaust ? 'Encendido' : 'Apagado' : 'Sin datos'}</div><p>{remapped ? 'Sentido del aire pendiente de confirmar.' : 'Saca aire caliente o con exceso de humedad.'}</p></article>
        {!remapped && <article><div className="card-top"><span>Entrada de aire</span><span className="pin">A5</span></div><div className="state-value">{cycle ? cycle.intake ? 'Encendido' : 'Apagado' : 'Sin datos'}</div><p>Ingresa aire exterior junto con la extracción.</p></article>}
      </div>
      <p>{profile ? `${remapped ? 'D8 enciende' : 'A4 y A5 encienden'} a ≥${fmt(profile.vent_temp_on)} °C o ≥${fmt(profile.vent_humidity_on)} % HR; apagan al volver a ${fmt(profile.vent_temp_off)} °C y ${fmt(profile.vent_humidity_off)} % HR.` : 'Esperando un ciclo confirmado del sensor.'}</p>
      {profile && <p className="subtle">Demanda automática: {[[1,'temperatura alta'],[2,'humedad alta'],[8,'renovación bloqueada por frío']].filter(([bit]) => cycle.air_reason & bit).map(([,label]) => label).join(' · ') || 'sin demanda de aireación'}</p>}
      <p className="subtle">{remapped ? 'A1–A5 libres. Bomba, ventilador y calefacción configurados para relés activos en LOW. Confirma físicamente la polaridad de D9 antes de conectar potencia.' : 'En automático A4 y A5 trabajan juntos; las pruebas manuales son independientes. D7 recircula dentro.'} Permanencia automática mínima: 15 s. Fallo y STOP apagan las salidas de aire.</p></section>
    <DevicePanel latest={latest} available={outputs && live} />
    <ManualPanel controls={latest?.controls} available={outputs && live} pins={latest?.pins} />
    <p className="notice">Calefacción automática: al bajar al mínimo del ciclo, enciende de inmediato; al alcanzar el máximo, se apaga. Dentro del rango mantiene una espera de 60 segundos para evitar conmutaciones rápidas. Sin lectura válida del sensor se apagan las salidas de clima.</p>
    <EventPanel />
    <section className="lower-grid"><article className="panel"><div className="section-heading"><h2>Temperatura reciente</h2><span className="legend">Rango del ciclo actual</span></div><Chart history={history} profile={profile} /><p className="subtle">Historial de lecturas recibidas · Las interrupciones no confirman continuidad.</p></article>
      <DoorPanel latest={latest} available={outputs && live} /></section>
    <section className="rules"><strong>Reglas automáticas</strong><span>{remapped && !physical ? 'Sensor D5 · ciclo manual' : 'Control por ciclo D2–D5'}</span><span>Duración manual configurable</span><span>Fuera de rango por 30 s: alarma</span></section>
    <footer><span>Control autónomo · El DHT11 actual informa valores enteros.</span><span>{latest ? `Último dato: ${new Date(latest.timestamp * 1000).toLocaleTimeString()}` : 'Esperando primera lectura'}</span></footer>
  </main>
}
