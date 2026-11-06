import { useRef, useState } from 'react'

const LABELS = { feeder: 'Comedero', drinker: 'Bebedero', heater: 'Calefacción' }
const fmt = n => Number(n).toLocaleString('es-PE', { maximumFractionDigits: 1 })
const rectStyle = r => ({left:`${r.x*100}%`,top:`${r.y*100}%`,width:`${r.width*100}%`,height:`${r.height*100}%`})
const midpoint = b => ({x:b.x+b.width/2,y:b.y+b.height/2})

export default function VisionScene({ camera, vision, fresh, streamError, onStreamError, api }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(null)
  const [drawing, setDrawing] = useState(null)
  const [selection, setSelection] = useState(null)
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const drag = useRef(null)
  const stage = useRef(null)
  const boxes = fresh ? vision.detections : []
  const tracked = boxes.filter(b => b.confirmed && b.track_id)
  const byId = new Map(tracked.map(b => [b.track_id,b]))
  const settings = vision?.configuration
  const zones = (editing ? draft?.zones : settings?.zones) || []
  const groups = fresh ? vision.groups || [] : []
  const pairs = fresh ? vision.near_pairs || [] : []
  const neighbors = fresh ? vision.nearest_neighbors || [] : []
  const message = fresh ? boxes.length ? 'Detecciones del último análisis reciente' : 'El modelo no detectó aves en la imagen' :
    ({loading:'Cargando detector…',waiting_camera:'Esperando imágenes para analizar…',error:'Detector no disponible. El video continúa activo.',unavailable:'Esperando conexión con el detector…'})[vision?.status] || 'Actualizando el análisis…'

  async function configure() {
    setNotice('Cargando configuración…')
    try {
      const response = await fetch(`${api}/api/vision/config`, {cache:'no-store'})
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'No se pudo cargar la configuración')
      setDraft(data); setEditing(true); setNotice('Selecciona una zona y arrastra un rectángulo sobre el video. Los cambios se aplican al guardar.')
    } catch (error) { setNotice(error.message) }
  }
  async function save() {
    setSaving(true); setNotice('Guardando…')
    try {
      const response = await fetch(`${api}/api/vision/config`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draft)})
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'No se pudo guardar')
      setDraft(data); setEditing(false); setDrawing(null); setSelection(null)
      setNotice('Zonas y criterios guardados. Actualizando el análisis…')
    } catch (error) { setNotice(error.message) }
    finally { setSaving(false) }
  }
  function position(event) {
    const bounds = event.currentTarget.getBoundingClientRect()
    return {x:Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width)),y:Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height))}
  }
  function rectangle(a,b) {
    return {x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(a.x-b.x),height:Math.abs(a.y-b.y)}
  }
  function pointerDown(event) {
    if (!editing || !drawing || saving || event.button!==0 || event.isPrimary===false) return
    event.preventDefault()
    drag.current = {point:position(event),pointerId:event.pointerId}
    event.currentTarget.setPointerCapture(event.pointerId)
    setSelection(rectangle(drag.current.point,drag.current.point))
  }
  function pointerMove(event) {
    if (drag.current?.pointerId===event.pointerId) setSelection(rectangle(drag.current.point,position(event)))
  }
  function pointerUp(event) {
    if (drag.current?.pointerId!==event.pointerId) return
    const zone = {id:drawing,...rectangle(drag.current.point,position(event))}
    drag.current = null
    setSelection(null)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    if (zone.width<0.02 || zone.height<0.02) { setNotice('El rectángulo es demasiado pequeño. Intenta de nuevo.'); return }
    setDraft(previous => ({...previous,zones:[...previous.zones.filter(z=>z.id!==zone.id),zone]}))
    setDrawing(null)
    setNotice('Zona dibujada en vista previa. Pulsa Guardar configuración para aplicarla.')
  }
  const validDraft = draft && draft.near_ratio>=.03 && draft.near_ratio<=.4 && Number.isInteger(draft.min_group_size) && draft.min_group_size>=2 && draft.min_group_size<=20 && draft.persistence_seconds>=2 && draft.persistence_seconds<=300

  return <>
    <div id="camera-view" className="camera-view">
      {camera?.ok && !streamError ? <div ref={stage} className={`camera-stage ${drawing ? 'is-drawing' : ''}`} style={{maxWidth:`min(800px, ${65*(camera.width/camera.height || 4/3)}vh)`}}
        onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={()=>{drag.current=null;setSelection(null)}}>
        <img draggable="false" src={`${api}/api/camera/stream`} alt="Video en vivo de la cámara del criadero" onError={onStreamError} />
        <div className="vision-overlay" aria-hidden="true">
          {zones.map(zone => <div key={zone.id} className={`vision-zone zone-${zone.id} ${editing ? 'zone-preview' : ''}`} style={rectStyle(zone)}><span>{LABELS[zone.id]} · {editing ? 'Vista previa' : fresh ? vision.zone_counts?.find(z=>z.id===zone.id)?.count ?? '—' : '—'}</span></div>)}
          <svg className="vision-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
            {tracked.filter(b=>b.trail?.length>1).map(b=><polyline key={b.track_id} className="track-trail" vectorEffect="non-scaling-stroke" points={b.trail.map(p=>`${p.x*100},${p.y*100}`).join(' ')} stroke={`hsl(${b.track_id*137.5%360} 85% 65%)`} />)}
            {pairs.map(p=>{const a=byId.get(p.a),b=byId.get(p.b);if(!a||!b)return null;const ca=midpoint(a),cb=midpoint(b);return <line key={`${p.a}-${p.b}`} className="near-link" vectorEffect="non-scaling-stroke" x1={ca.x*100} y1={ca.y*100} x2={cb.x*100} y2={cb.y*100}/>})}
          </svg>
          {groups.map(group=><div key={group.id} className={`vision-group ${group.persistent ? 'persistent' : ''}`} style={rectStyle(group)}><span>G{group.id} · {group.count} IDs · {fmt(group.duration_seconds)} s</span></div>)}
          {boxes.map((box,index)=><div className="vision-box" key={`${vision.tracking_session}-${box.track_id || index}`} data-track-id={box.track_id} style={rectStyle(box)}><span>{box.track_id ? `#${box.track_id}${box.confirmed ? '' : '?'}` : `Det. ${index+1}`} · {Math.round(box.confidence*100)}%</span></div>)}
          {selection && <div className="zone-selection" style={rectStyle(selection)}/>}
        </div>
        {drawing && <div className="drawing-hint">Arrastra para marcar {LABELS[drawing]}</div>}
      </div> : <p role="status">{streamError ? 'Video interrumpido. Reconectando…' : camera?.error || 'Esperando imágenes de la cámara…'}</p>}
    </div>
    <div className="vision-summary" aria-label="Detección de pollitos">
      <div><h3>Detección de pollitos <span className="badge warm">En evaluación</span></h3><strong>{fresh ? `${vision.count} posibles pollitos` : 'Sin resultado reciente'}</strong><p role="status">{message}</p><p>{fresh ? `${tracked.length} IDs en seguimiento` : 'Sin seguimiento reciente'}</p></div>
      <div><p>{fresh ? `IA: ${fmt(vision.fps)} FPS · ${fmt(vision.inference_ms)} ms por análisis` : 'Los recuadros se muestran al recibir un análisis reciente.'}</p><p className="subtle">Conteo estimado: puede omitir pollitos ocultos o confundir objetos con aves. Los IDs son temporales y pueden cambiar al cruzarse o desaparecer. Trayectorias de hasta 6 s.</p></div>
    </div>
    <section className="spatial-panel" aria-label="Agrupamiento y zonas">
      <div className="section-heading"><h3>Agrupamiento y zonas</h3><button disabled={editing || saving} onClick={configure}>Configurar zonas y cercanía</button></div>
      <p>Cercanía: hasta {fmt((settings?.near_ratio ?? .12)*100)} % de la diagonal de la imagen. Un grupo conecta al menos {settings?.min_group_size ?? 3} IDs por cercanía; se marca como sostenido tras {fmt(settings?.persistence_seconds ?? 5)} s. Distancias relativas; no están calibradas en centímetros.</p>
      <div className="group-list" aria-live="polite">{!fresh ? <p>Sin análisis reciente de agrupamiento.</p> : groups.length ? groups.map(group=><article key={group.id} className={group.persistent ? 'group-persistent' : ''}><strong>{group.persistent ? 'Agrupamiento sostenido' : 'Grupo en observación'} · G{group.id}</strong><p>{group.count} IDs próximos · {fmt(group.duration_seconds)} s</p><small>{group.ids.map(id=>`#${id}`).join(', ')}</small></article>) : <p>No hay grupos con el tamaño mínimo configurado.</p>}</div>
      <div className="zone-counts">{Object.entries(LABELS).map(([id,label])=>{const zone=settings?.zones.find(z=>z.id===id),count=vision?.zone_counts?.find(z=>z.id===id);return <article key={id} data-zone-id={id}><strong>{label}</strong><span>{!settings ? 'Configuración no disponible' : !zone ? 'Sin configurar' : fresh && count ? `${count.count} en seguimiento` : 'Sin dato reciente'}</span></article>})}</div>
      <p className="subtle">Las zonas cuentan el centro de cada detección en seguimiento; si se superponen, un ID puede aparecer en ambas. Si mueves la cámara, vuelve a dibujarlas. Un grupo observado no determina su causa.</p>
      {tracked.length>0 && <details className="neighbor-details"><summary>IDs y vecino más cercano ({tracked.length})</summary><div className="neighbor-scroll"><table><thead><tr><th>ID temporal</th><th>Vecino</th><th>Separación</th></tr></thead><tbody>{tracked.map(box=>{const nearest=neighbors.find(n=>n.track_id===box.track_id);return <tr key={box.track_id}><td>#{box.track_id}</td><td>{nearest ? `#${nearest.neighbor_id}` : 'Sin otro ID visible'}</td><td>{nearest ? `${fmt(nearest.distance_ratio*100)} % diagonal` : '—'}</td></tr>})}</tbody></table></div></details>}
      {editing && draft && <form className="zone-editor" onSubmit={event=>{event.preventDefault();save()}}>
        <h4>Zonas · vista previa</h4><p>Elige Dibujar y arrastra sobre el video. Solo se guarda al pulsar Guardar configuración.</p>
        {Object.entries(LABELS).map(([id,label])=><div className="zone-editor-row" key={id}><strong>{label}</strong><button type="button" disabled={saving} aria-pressed={drawing===id} onClick={()=>{setDrawing(id);setSelection(null);stage.current?.scrollIntoView({behavior:'smooth',block:'center'})}}>{draft.zones.some(z=>z.id===id) ? 'Redibujar' : 'Dibujar'} {label}</button><button type="button" disabled={saving || !draft.zones.some(z=>z.id===id)} onClick={()=>{setDraft({...draft,zones:draft.zones.filter(z=>z.id!==id)});if(drawing===id)setDrawing(null)}}>Quitar {label}</button></div>)}
        <div className="spatial-settings"><label>Cercanía (% diagonal)<input type="number" min="3" max="40" step="1" value={Math.round(draft.near_ratio*10000)/100} onChange={e=>setDraft({...draft,near_ratio:Number(e.target.value)/100})} disabled={saving}/></label><label>IDs mínimos por grupo<input type="number" min="2" max="20" step="1" value={draft.min_group_size} onChange={e=>setDraft({...draft,min_group_size:Number(e.target.value)})} disabled={saving}/></label><label>Persistencia (segundos)<input type="number" min="2" max="300" step="1" value={draft.persistence_seconds} onChange={e=>setDraft({...draft,persistence_seconds:Number(e.target.value)})} disabled={saving}/></label></div>
        <div className="zone-editor-actions"><button type="submit" disabled={saving || !validDraft || !!drawing}>Guardar configuración</button><button type="button" disabled={saving} onClick={()=>{setEditing(false);setDrawing(null);setSelection(null);drag.current=null;setNotice('Cambios descartados.')}}>Cancelar</button></div>
      </form>}
      <p className="vision-notice" role="status">{notice}</p>
    </section>
  </>
}
