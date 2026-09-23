import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/temperature'
const MAX_POINTS = 40

function Sparkline({ points, min, max }) {
  if (points.length < 2) return null
  const range = max - min || 1
  const coords = points.map((value, i) => {
    const x = (i / (points.length - 1)) * 100
    const y = 100 - ((value - min) / range) * 100
    return `${x},${y}`
  })
  return (
    <svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline points={coords.join(' ')} fill="none" strokeWidth="3" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export default function App() {
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const socketRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/temperature/history`)
      .then((res) => res.json())
      .then((data) => setHistory(data.filter((r) => r.ok).slice(-MAX_POINTS)))
      .catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false
    let retryTimer

    function connect() {
      const socket = new WebSocket(WS_URL)
      socketRef.current = socket

      socket.onopen = () => !cancelled && setConnected(true)
      socket.onclose = () => {
        if (cancelled) return
        setConnected(false)
        retryTimer = setTimeout(connect, 2000)
      }
      socket.onerror = () => socket.close()
      socket.onmessage = (event) => {
        const reading = JSON.parse(event.data)
        setLatest(reading)
        if (reading.ok) {
          setHistory((prev) => [...prev, reading].slice(-MAX_POINTS))
        }
      }
    }

    connect()
    return () => {
      cancelled = true
      clearTimeout(retryTimer)
      socketRef.current?.close()
    }
  }, [])

  const temps = history.map((r) => r.temperature)
  const hums = history.map((r) => r.humidity)

  return (
    <div className="dashboard">
      <header>
        <h1>Temperatura y humedad</h1>
        <span className={`status ${connected ? 'online' : 'offline'}`}>
          {connected ? 'En vivo' : 'Reconectando…'}
        </span>
      </header>

      {!latest && <p className="hint">Esperando la primera lectura del Arduino…</p>}

      {latest && !latest.ok && (
        <p className="error">Sin lectura válida del sensor (ERR TEMP). Revisa el cableado en D5.</p>
      )}

      {latest?.ok && (
        <div className="cards">
          <div className="card">
            <span className="label">Temperatura</span>
            <span className="value">{latest.temperature}°C</span>
            {temps.length > 1 && <Sparkline points={temps} min={Math.min(...temps) - 1} max={Math.max(...temps) + 1} />}
          </div>
          <div className="card">
            <span className="label">Humedad</span>
            <span className="value">{latest.humidity}%</span>
            {hums.length > 1 && <Sparkline points={hums} min={Math.min(...hums) - 1} max={Math.max(...hums) + 1} />}
          </div>
        </div>
      )}

      {latest && (
        <p className="timestamp">
          Última actualización: {new Date(latest.timestamp * 1000).toLocaleTimeString()}
        </p>
      )}
    </div>
  )
}
