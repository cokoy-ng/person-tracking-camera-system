"""Historial persistente de cambios observados; no reconstruye periodos sin datos."""
import json
import sqlite3
import csv
import io
import math
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from configuration_audit import configuration_values, fingerprint

LABELS = {'heater':'Calefacción / foco', 'humidifier':'Humedad interna',
          'exhaust':'Extracción', 'intake':'Entrada de aire', 'alarm':'Salida de alarma'}
MODES = {'auto':'automático', 'off':'manual apagado', 'on':'manual encendido'}
NUMERIC_FIELDS = ('serial_connected', 'sensor_valid', 'outputs_valid', 'cycle',
                  'temperature_c', 'humidity_pct', 'temp_min_c', 'temp_max_c',
                  'humidity_min_pct', 'humidity_max_pct', 'heater_on_c', 'heater_off_c',
                  'stopped', 'alarm_active', 'alarm_reasons', 'air_reason')
SAMPLE_FIELDS = NUMERIC_FIELDS + tuple(field for name in LABELS
    for field in (name+'_on', name+'_mode', name+'_remaining_seconds'))
SAMPLE_FIELDS += ('config_id','session_id','firmware_reported','temp_target_c','humidity_target_pct',
    'temperature_in_range','humidity_in_range','temperature_error_to_center_c','humidity_error_to_center_pct',
    'heater_dwell_seconds','humidifier_on_pct','humidifier_off_pct','vent_humidity_on_pct',
    'vent_humidity_off_pct','vent_temp_on_c','vent_temp_off_c','alarm_pending','alarm_recovering',
    'alarm_sounding','door_enabled','door_position_steps','door_target_steps','door_referenced')
TEXT_FIELDS = {'session_id','firmware_reported'}
EVENT_DETAILS = ('output','mode','output_on','duration_seconds','request_id','command_status','reason',
                 'http_status','before_config_id','before_json','after_json','context_json')
DATASETS = ('events','readings','configurations')


def sample_values(row):
    connected = bool(row.get('serial_connected'))
    valid = connected and bool(row.get('ok'))
    outputs = connected and bool(row.get('outputs_valid'))
    cycle = row.get('cycle') or {}
    if not connected or not cycle.get('valid'): cycle = {}
    alert = row.get('alert') or {}
    if not connected or not alert.get('valid'): alert = {}
    values = dict(serial_connected=int(connected), sensor_valid=int(valid), outputs_valid=int(outputs),
                  cycle=cycle.get('id'), temperature_c=row.get('temperature') if valid else None,
                  humidity_pct=row.get('humidity') if valid else None,
                  temp_min_c=cycle.get('temp_min'), temp_max_c=cycle.get('temp_max'),
                  humidity_min_pct=cycle.get('humidity_min'), humidity_max_pct=cycle.get('humidity_max'),
                  heater_on_c=cycle.get('heater_on'), heater_off_c=cycle.get('heater_off'),
                  stopped=row.get('stopped') if outputs else None,
                  alarm_active=alert.get('active'), alarm_reasons=alert.get('reasons'),
                  air_reason=cycle.get('air_reason'))
    controls = (row.get('controls') or {}) if outputs else {}
    values.update(firmware_reported=row.get('firmware_reported') if connected else None,
        temp_target_c=cycle.get('temp_target'),humidity_target_pct=cycle.get('humidity_target'),
        heater_dwell_seconds=cycle.get('heater_dwell_seconds'),humidifier_on_pct=cycle.get('humidifier_on'),
        humidifier_off_pct=cycle.get('humidifier_off'),vent_humidity_on_pct=cycle.get('vent_humidity_on'),
        vent_humidity_off_pct=cycle.get('vent_humidity_off'),vent_temp_on_c=cycle.get('vent_temp_on'),
        vent_temp_off_c=cycle.get('vent_temp_off'),alarm_pending=alert.get('pending'),
        alarm_recovering=alert.get('recovering'),alarm_sounding=alert.get('sounding'),
        door_enabled=row.get('door_enabled') if outputs else None,
        door_position_steps=row.get('position') if outputs else None,
        door_target_steps=row.get('target') if outputs else None,
        door_referenced=row.get('referenced') if outputs else None)
    for field,prefix,unit in (('temperature','temp','c'),('humidity','humidity','pct')):
        value=row.get(field) if valid else None
        low,high,target=cycle.get(prefix+'_min'),cycle.get(prefix+'_max'),cycle.get(prefix+'_target')
        values[field+'_in_range'] = low<=value<=high if None not in (value,low,high) else None
        values[field+'_error_to_center_'+unit] = value-target if None not in (value,target) else None
    for name in LABELS:
        control = controls.get(name) or {}
        values.update({name+'_on':control.get('on'), name+'_mode':control.get('mode'),
                       name+'_remaining_seconds':control.get('remaining_seconds')})
    return {key:int(value) if isinstance(value,bool) else value for key,value in values.items()}


class EventHistory:
    def __init__(self, path, archive_dir=None, software=None):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.previous = None
        self.lock = threading.RLock()
        self.archive_dir = Path(archive_dir) if archive_dir else None
        self.archived = {}
        self.session_id = uuid.uuid4().hex
        self.software = software or {'configuration_basis':'unspecified'}
        self.software_id = fingerprint(self.software)
        self.last_config_id = None
        self.manual_requests = {}
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL, context TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS events_kind_id ON events(kind,id)')
            columns = ','.join(name+(' TEXT' if name.endswith('_mode') or name in TEXT_FIELDS else ' REAL') for name in SAMPLE_FIELDS)
            db.execute('CREATE TABLE IF NOT EXISTS readings (id INTEGER PRIMARY KEY, timestamp REAL NOT NULL,'+columns+')')
            existing={row[1] for row in db.execute('PRAGMA table_info(readings)')}
            for name in SAMPLE_FIELDS:
                if name not in existing:
                    db.execute('ALTER TABLE readings ADD COLUMN '+name+(' TEXT' if name in TEXT_FIELDS else ' REAL'))
            db.execute('CREATE TABLE IF NOT EXISTS software_versions (hash TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO software_versions VALUES(?,?)',(self.software_id,json.dumps(self.software,ensure_ascii=False)))
            db.execute('CREATE TABLE IF NOT EXISTS configurations (id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, hash TEXT UNIQUE NOT NULL, software_id TEXT NOT NULL, payload TEXT NOT NULL)')
            for (context,) in db.execute("SELECT context FROM events WHERE kind='command' ORDER BY id DESC"):
                context=json.loads(context)
                output=context.get('output')
                if context.get('command_status')=='confirmed' and output not in self.manual_requests:
                    self.manual_requests[output]={key:context.get(key) for key in ('request_id','mode','duration_seconds')}
                if len(self.manual_requests)==len(LABELS): break
        if self.archive_dir:
            self.archive_dir.mkdir(parents=True,exist_ok=True)
            # Rebuild atomically on startup: recover interrupted appends, including a final partial line.
            software_dir=self.archive_dir/'software'
            software_dir.mkdir(exist_ok=True)
            with self.connect() as db:
                versions=db.execute('SELECT hash,payload FROM software_versions').fetchall()
            for key,payload in versions:
                target=software_dir/(key+'.json')
                if not target.exists():
                    temporary=target.with_suffix('.tmp')
                    temporary.write_text(payload,encoding='utf-8')
                    temporary.replace(target)
            for dataset in DATASETS:
                with self.connect() as db:
                    maximum = db.execute('SELECT COALESCE(MAX(id),0) FROM '+dataset).fetchone()[0]
                temporary = self.archive_dir / (dataset+'.csv.tmp')
                with temporary.open('w',encoding='utf-8',newline='') as target:
                    for chunk in self.export_csv(dataset,stop_id=maximum): target.write(chunk)
                    target.flush(); os.fsync(target.fileno())
                temporary.replace(self.archive_dir / (dataset+'.csv'))
                self.archived[dataset] = maximum

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db: yield db
        finally:
            db.close()

    def record(self, row):
        with self.lock:
            self._record(row)
            self.sync_archives()

    def config(self, row, db):
        payload=configuration_values(row)
        payload['last_dashboard_request']={name:request for name,request in self.manual_requests.items()
            if payload['modes'].get(name)==request['mode'] and request['mode']!='auto'}
        digest=fingerprint({'software_id':self.software_id,**payload})
        db.execute('INSERT OR IGNORE INTO configurations(timestamp,hash,software_id,payload) VALUES(?,?,?,?)',
                   (row['timestamp'],digest,self.software_id,json.dumps(payload,ensure_ascii=False)))
        return db.execute('SELECT id FROM configurations WHERE hash=?',(digest,)).fetchone()[0]

    def configuration(self, config_id):
        with self.connect() as db:
            row=db.execute('SELECT c.id,c.timestamp,c.hash,c.payload,s.payload FROM configurations c JOIN software_versions s ON c.software_id=s.hash WHERE c.id=?',(config_id,)).fetchone()
        if row is None: return None
        return dict(id=row[0],timestamp=row[1],hash=row[2],configuration=json.loads(row[3]),software=json.loads(row[4]))

    def _record(self, row):
        prev = self.previous
        connected = bool(row.get('serial_connected'))
        valid = bool(row.get('ok'))
        events = []
        def add(kind, message, **details): events.append((kind,message,details))
        with self.connect() as db:
            config_id=self.config(row,db)
        if config_id != self.last_config_id:
            add('configuration',f'Configuración observada #{config_id}',before_config_id=self.last_config_id)
        if prev is None:
            add('system','Monitor iniciado; estado inicial observado')
        if prev is None or connected != bool(prev.get('serial_connected')):
            add('connection','Arduino conectado' if connected else 'Arduino desconectado; salidas físicas desconocidas')
        if connected and (prev is None or not prev.get('serial_connected') or valid != bool(prev.get('ok'))):
            add('sensor','Lectura del sensor recuperada' if valid else 'Sin lectura válida del sensor o ciclo')
        if connected and row.get('outputs_valid') and prev and prev.get('outputs_valid') and row.get('stopped') != prev.get('stopped'):
            add('system','STOP activado' if row.get('stopped') else 'STOP liberado')
        cycle = row.get('cycle') or {}
        oldcycle = (prev or {}).get('cycle') or {}
        if cycle.get('valid') and (prev is None or not oldcycle.get('valid') or cycle.get('id') != oldcycle.get('id')):
            add('cycle',f"Ciclo {cycle['id']} confirmado" if cycle['id'] else 'Sin ciclo confirmado')
        if valid and (prev is None or not prev.get('ok') or
                      (row.get('temperature'),row.get('humidity')) != (prev.get('temperature'),prev.get('humidity'))):
            add('reading',f"Temperatura {row['temperature']} °C · Humedad {row['humidity']} %")
        controls = row.get('controls') if connected and row.get('outputs_valid') else None
        old = (prev or {}).get('controls') if (prev or {}).get('serial_connected') and (prev or {}).get('outputs_valid') else None
        if controls:
            for name, current in controls.items():
                before = (old or {}).get(name)
                if before is None or (current['on'],current['mode']) != (before['on'],before['mode']):
                    label = LABELS.get(name,name)
                    value = 'encendida' if current['on'] else 'apagada'
                    prefix = 'Estado observado' if before is None else 'Cambio confirmado'
                    add('output',f"{prefix}: {label} {value} · {MODES.get(current['mode'],current['mode'])}", output=name, mode=current['mode'], output_on=current['on'])
        alert = row.get('alert') or {}
        oldalert = (prev or {}).get('alert') or {}
        if alert.get('valid') and (not oldalert.get('valid') or
            (alert.get('active'),alert.get('reasons')) != (oldalert.get('active'),oldalert.get('reasons'))):
            add('alarm','Alerta confirmada' if alert.get('active') else 'Sin alerta confirmada')
        context = {'temperature':row.get('temperature') if valid else None,
                   'humidity':row.get('humidity') if valid else None,
                   'cycle':cycle.get('id') if cycle.get('valid') else None,
                   'stopped':row.get('stopped'), 'sensor_valid':valid,
                   'heater_on':cycle.get('heater_on'), 'heater_off':cycle.get('heater_off'),
                   'alarm_reasons':alert.get('reasons'), 'controls':controls}
        values = sample_values(row)
        values.update(config_id=config_id,session_id=self.session_id)
        context['sample'] = values
        with self.connect() as db:
            db.executemany('INSERT INTO events(timestamp,kind,message,context) VALUES(?,?,?,?)',
                [(row['timestamp'],kind,message,json.dumps({**context,**details},ensure_ascii=False)) for kind,message,details in events])
            db.execute('INSERT INTO readings(timestamp,'+','.join(SAMPLE_FIELDS)+') VALUES('+','.join('?' for _ in range(1+len(SAMPLE_FIELDS)))+')',
                       [row['timestamp']]+[values[name] for name in SAMPLE_FIELDS])
        self.previous = row
        self.last_config_id = config_id

    def command(self, output, mode, seconds, reading):
        with self.lock:
            self._command(output, mode, seconds, reading)
            self.sync_archives()

    def _command(self, output, mode, seconds, reading):
        message=f"Mando confirmado: {LABELS[output]} · {MODES[mode]}"
        if mode!='auto': message += f' · {seconds} segundos' if seconds else ' · hasta pulsar Automático'
        values = sample_values(reading)
        context={'temperature':values['temperature_c'], 'humidity':values['humidity_pct'],
                 'cycle':values['cycle'], 'sensor_valid':bool(values['sensor_valid']),
                 'duration_seconds':seconds, 'output':output, 'mode':mode,
                 'output_on':values[output+'_on'], 'sample':values}
        with self.connect() as db:
            values.update(config_id=self.config(reading,db),session_id=self.session_id)
            db.execute('INSERT INTO events(timestamp,kind,message,context) VALUES(?,?,?,?)',
                       (reading['timestamp'],'output',message,json.dumps(context,ensure_ascii=False)))

    def audit_command(self, request_id, status, output, mode, seconds, before, after=None, reason='', http_status=None):
        with self.lock:
            timestamp=time.time()
            before=dict(before or {},timestamp=(before or {}).get('timestamp',timestamp))
            observed=dict(after or before,timestamp=(after or before).get('timestamp',timestamp))
            values=sample_values(observed)
            with self.connect() as db:
                before_config_id=self.config(before,db)
                if status=='confirmed':
                    self.manual_requests[output]={'request_id':request_id,'mode':mode,'duration_seconds':seconds}
                values.update(config_id=self.config(observed,db),session_id=self.session_id)
                context={'request_id':request_id,'command_status':status,'output':output,'mode':mode,
                         'duration_seconds':seconds,'output_on':values.get(str(output)+'_on'),
                         'reason':reason,'http_status':http_status,'before_config_id':before_config_id,
                         'before_json':json.dumps(before,ensure_ascii=False),'after_json':json.dumps(after,ensure_ascii=False) if after else None,
                         'temperature':values['temperature_c'],'humidity':values['humidity_pct'],
                         'sensor_valid':bool(values['sensor_valid']),'cycle':values['cycle'],'sample':values}
                label={'requested':'solicitado','confirmed':'confirmado','rejected':'rechazado','unconfirmed':'sin confirmación'}[status]
                message=f'Mando {label}: {LABELS.get(output,output or "petición inválida")} · {MODES.get(mode,mode or "")} · {seconds if seconds is not None else "?"} s'
                if reason: message+=' · '+reason
                db.execute('INSERT INTO events(timestamp,kind,message,context) VALUES(?,?,?,?)',
                           (timestamp,'command',message,json.dumps(context,ensure_ascii=False)))
            self.sync_archives()

    def recent(self, limit=200):
        with self.connect() as db:
            rows = db.execute('SELECT id,timestamp,kind,message,context FROM events ORDER BY id DESC LIMIT ?',
                              (max(1,min(limit,500)),)).fetchall()
        return [dict(id=i,timestamp=t,kind=k,message=m,context=json.loads(c)) for i,t,k,m,c in rows]

    def page(self, page=1, page_size=25, kind='all', snapshot_id=None):
        page_size = max(1,min(page_size,100))
        with self.connect() as db:
            maximum = db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
            snapshot = maximum if snapshot_id is None else min(maximum,max(0,snapshot_id))
            where, args = 'id <= ?', [snapshot]
            if kind != 'all': where += ' AND kind = ?'; args.append(kind)
            total = db.execute('SELECT COUNT(*) FROM events WHERE '+where,args).fetchone()[0]
            pages = max(1,math.ceil(total/page_size))
            page = max(1,min(page,pages))
            rows = db.execute('SELECT id,timestamp,kind,message,context FROM events WHERE '+where+
                              ' ORDER BY id DESC LIMIT ? OFFSET ?',args+[page_size,(page-1)*page_size]).fetchall()
        return dict(events=[dict(id=i,timestamp=t,kind=k,message=m,context=json.loads(c)) for i,t,k,m,c in rows],
                    page=page, page_size=page_size, total=total, pages=pages, snapshot_id=snapshot)

    def sync_archives(self):
        if not self.archive_dir: return
        for dataset in DATASETS:
            with self.connect() as db:
                maximum = db.execute('SELECT COALESCE(MAX(id),0) FROM '+dataset).fetchone()[0]
            if maximum <= self.archived[dataset]: continue
            path = self.archive_dir / (dataset+'.csv')
            with path.open('r+b') as target:
                target.seek(0,2)
                original_size = target.tell()
                try:
                    for chunk in self.export_csv(dataset,start_id=self.archived[dataset],stop_id=maximum,header=False):
                        target.write(chunk.encode('utf-8'))
                    target.flush(); os.fsync(target.fileno())
                except Exception:
                    target.seek(original_size); target.truncate()
                    raise
            self.archived[dataset] = maximum

    def export_csv(self, dataset, kind='all', start_id=0, stop_id=None, header=True):
        if dataset not in DATASETS: raise ValueError('Unknown dataset')
        fields = ['id','timestamp_utc','timestamp_epoch']
        if dataset == 'events': fields += ['kind','message',*EVENT_DETAILS]
        if dataset == 'configurations': fields += ['hash','software_id','cycle','snapshot_json']
        else: fields += list(SAMPLE_FIELDS)
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer,fieldnames=fields,extrasaction='ignore')
        if header:
            writer.writeheader()
            yield '\ufeff'+buffer.getvalue()
            buffer.seek(0); buffer.truncate(0)
        # Batches close their connections before yielding: downloads do not hold a write lock.
        with self.connect() as db:
            maximum = db.execute('SELECT COALESCE(MAX(id),0) FROM '+dataset).fetchone()[0]
        if stop_id is not None: maximum = min(maximum,stop_id)
        last = start_id
        while last < maximum:
            where, args = 'id > ? AND id <= ?', [last,maximum]
            if dataset == 'events' and kind != 'all': where += ' AND kind = ?'; args.append(kind)
            with self.connect() as db:
                db.row_factory = sqlite3.Row
                batch = db.execute('SELECT * FROM '+dataset+' WHERE '+where+' ORDER BY id LIMIT 500',args).fetchall()
            if not batch: break
            for record in batch:
                row = dict(record)
                last = row['id']
                if dataset == 'events':
                    context = json.loads(row.pop('context'))
                    sample = context.get('sample') or self.legacy_sample(context)
                    row.update(sample)
                    row.update({key:context.get(key) for key in EVENT_DETAILS})
                    row['context_json']=json.dumps(context,ensure_ascii=False)
                elif dataset == 'configurations':
                    payload=row.pop('payload')
                    row.update(snapshot_json=payload,cycle=json.loads(payload).get('profile',{}).get('id'))
                timestamp = row.pop('timestamp')
                row.update(timestamp_epoch=timestamp, timestamp_utc=datetime.fromtimestamp(timestamp,timezone.utc).isoformat())
                writer.writerow({k:int(v) if isinstance(v,bool) else v for k,v in row.items()})
            yield buffer.getvalue()
            buffer.seek(0); buffer.truncate(0)

    @staticmethod
    def legacy_sample(context):
        # Only export facts present in older events; unknown values stay empty.
        sample = {'sensor_valid':context.get('sensor_valid'), 'cycle':context.get('cycle'),
                  'temperature_c':context.get('temperature') if context.get('sensor_valid') else None,
                  'humidity_pct':context.get('humidity') if context.get('sensor_valid') else None,
                  'heater_on_c':context.get('heater_on'), 'heater_off_c':context.get('heater_off'),
                  'stopped':context.get('stopped'), 'alarm_reasons':context.get('alarm_reasons')}
        for name, control in (context.get('controls') or {}).items():
            sample.update({name+'_on':control.get('on'),name+'_mode':control.get('mode'),
                           name+'_remaining_seconds':control.get('remaining_seconds')})
        return sample
