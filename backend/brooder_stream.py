"""Decodifica telemetría del criadero sin enviar órdenes al Arduino."""
import re
import time

REMAPPED_FIRMWARES = ('BROODER_12_PIN_REMAP', 'BROODER_13_MANUAL_DOOR', 'BROODER_14_PHYSICAL_CYCLES', 'BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP')
BLOCK_REASONS = {0:None,1:'Control automático en pausa',2:'Sensor o ciclo sin lectura válida',3:'Temperatura en el máximo del ciclo',4:'Humedad en el máximo del ciclo',5:'Temperatura en el mínimo del ciclo'}
SERVO = re.compile(r'SERVO stage=([0-3]) angle=(-1|130|180) remaining=(\d+)')
TEMP = re.compile(r'TEMP (-?\d+) HUM (\d+)')
CONTROL = re.compile(r'CONTROL modes=([012]{5}) outputs=([01]{5}) door_enabled=([01])(?: remaining=(\d+,\d+,\d+,\d+,\d+))?')
OUTPUT_NAMES = ('heater', 'humidifier', 'exhaust', 'intake', 'alarm')
STATE = re.compile(r'STATE heater=([01]) alarm=([01]) position=(\d+) target=(\d+) referenced=([01]) stopped=([01])')
ALERT = re.compile(r'ALERT active=([01]) pending=([01]) recovering=([01]) sounding=([01]) reasons=(\d+)')
CYCLE = re.compile(
    r'CYCLE id=([0-4]) pin=(\d+) humidifier=([01]) exhaust=([01]) '
    r'intake=([01]) reason=([0-9]|1[0-5])')
PROFILES = {
    1: {'pin': 'D2', 'days': '1–3', 'temp_min': 33, 'temp_max': 34, 'humidity_min': 60, 'humidity_max': 70},
    2: {'pin': 'D3', 'days': '4–7', 'temp_min': 30, 'temp_max': 32, 'humidity_min': 50, 'humidity_max': 65},
    3: {'pin': 'D4', 'days': '8–14', 'temp_min': 27, 'temp_max': 29, 'humidity_min': 50, 'humidity_max': 60},
    4: {'pin': 'D5', 'days': '15–21', 'temp_min': 24, 'temp_max': 27, 'humidity_min': 50, 'humidity_max': 60},
}
for profile in PROFILES.values():
    profile['temp_target'] = (profile['temp_min']+profile['temp_max']) / 2
    profile['humidity_target'] = (profile['humidity_min']+profile['humidity_max']) / 2
    profile['heater_on'] = profile['temp_max']-1
    profile['heater_off'] = profile['temp_max']
    profile['heater_dwell_seconds'] = 60
    profile['heater_immediate_below_min'] = True
    profile['humidifier_on'] = profile['humidity_target']-2
    profile['humidifier_off'] = profile['humidity_target']
    profile['vent_humidity_on'] = profile['humidity_target']+2
    profile['vent_humidity_off'] = profile['humidity_target']
    profile['vent_temp_on'] = profile['heater_off']
    profile['vent_temp_off'] = profile['temp_max']-1
TRAVEL = 49152


class Telemetry:
    def __init__(self):
        self.firmware_reported = None
        self.servo = None
        self.servo_at = None
        self.requested_cycle = None
        self.door_control = self.door_control_at = None
        self.block_codes = None
        self.sensor_diagnostics = self.sensor_diagnostics_at = None
        self.sample = None
        self.controls = None
        self.controls_at = 0
        self.door_enabled = None
        self.sample_at = None
        self.cycle = None
        self.cycle_at = None
        self.cycle_seen = False
        self.alert = None
        self.alert_at = None

    def feed(self, line, now=None):
        now = time.monotonic() if now is None else now
        match = re.fullmatch(r'SENSOR D2=([0-8]) D3=([0-8]) D4=([0-8]) D5=([0-8]) mask=(\d+)',line)
        if match and int(match[5])<=15:
            self.sensor_diagnostics = {'pins':{f'D{i+2}':int(match[i+1]) for i in range(4)},'mask':int(match[5])}
            self.sensor_diagnostics_at=now
            return None
        if line.startswith('FIRMWARE '):
            self.firmware_reported = line.removeprefix('FIRMWARE ').strip()
            if self.firmware_reported in REMAPPED_FIRMWARES: self.cycle_seen = True
            return None
        match = re.fullmatch(r'DOOR_CONTROL running=([01]) manual_only=1', line)
        if match:
            self.door_control = {'running':match[1]=='1','manual_only':True}
            self.door_control_at = now
            return None
        match = re.fullmatch(r'BLOCK codes=([0-5]),([0-5]),([0-5])', line)
        if match:
            self.block_codes = list(map(int,match.groups()))
            return None
        match = re.fullmatch(r'CYCLE_REQUEST id=([0-4])', line)
        if match:
            self.requested_cycle = int(match[1])
            return None
        if line.startswith('SERVO stage='):
            self.servo = self.servo_at = None
            match = SERVO.fullmatch(line)
            if match and int(match[3]) <= 22:
                self.servo = {'stage': int(match[1]), 'running': match[1] != '0',
                              'last_angle': None if match[2] == '-1' else int(match[2]),
                              'remaining_seconds': int(match[3])}
                self.servo_at = now
            return None
        if line.startswith('CONTROL '):
            self.controls = None
            self.door_enabled = None
            match = CONTROL.fullmatch(line)
            if match:
                self.controls = {name: {'mode': ('auto','off','on')[int(mode)], 'on': value == '1'}
                                 for name, mode, value in zip(OUTPUT_NAMES, match[1], match[2])}
                if self.block_codes is not None:
                    for name,code in zip(OUTPUT_NAMES,self.block_codes):
                        self.controls[name]['blocked_reason'] = BLOCK_REASONS[code]
                if self.firmware_reported=='BROODER_16_MANUAL_PUMP':
                    self.controls['humidifier']['manual_only']=True
                self.controls_at = now
                if match[4]:
                    for name,remaining in zip(OUTPUT_NAMES,map(int,match[4].split(','))):
                        self.controls[name]['remaining_seconds'] = remaining
                self.door_enabled = match[3] == '1'
            return None
        if line.startswith('ALERT '):
            self.alert = self.alert_at = None
            match = ALERT.fullmatch(line)
            if match:
                active, pending, recovering, sounding, reasons = map(int, match.groups())
                if reasons <= 63 and not (active and pending) and not (recovering and not active) and not (sounding and (not active or recovering)):
                    self.alert = {'active': bool(active), 'pending': bool(pending), 'recovering': bool(recovering), 'sounding': bool(sounding), 'reasons': reasons}
                    self.alert_at = now
            return None
        if line.startswith('CYCLE '):
            self.cycle_seen = True
            self.cycle = self.cycle_at = None
            match = CYCLE.fullmatch(line)
            if match:
                cycle, pin, humidifier, exhaust, intake, reason = map(int, match.groups())
                outputs_valid = cycle != 0 or not (humidifier or exhaust or intake or reason)
                remapped = self.firmware_reported in REMAPPED_FIRMWARES
                physical = self.firmware_reported in ('BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP')
                expected_pin = (5 if remapped and not physical else cycle+1) if cycle else 0
                if pin == expected_pin and outputs_valid:
                    self.cycle = {
                        'id': cycle, 'humidifier': bool(humidifier),
                        'exhaust': bool(exhaust), 'intake': bool(intake),
                        'air_reason': reason, **PROFILES.get(cycle, {})}
                    if remapped and not physical and cycle:
                        self.cycle['pin'] = 'D5'
                    if self.firmware_reported=='BROODER_16_MANUAL_PUMP':
                        self.cycle.update(pump_manual_only=True,humidifier_on=None,humidifier_off=None)
                    self.cycle_at = now
            return None
        match = TEMP.fullmatch(line)
        if match:
            temperature, humidity = map(int, match.groups())
            if 0 <= temperature <= 50 and 0 <= humidity <= 100:
                self.sample = {'temperature': temperature, 'humidity': humidity}
                self.sample_at = now
            else:
                self.sample = None
            return None
        if line.startswith(('FAULT', 'READY')):
            if line.startswith('READY'):
                self.firmware_reported = line.removeprefix('READY ').strip()
                self.servo = self.servo_at = self.requested_cycle = None
                self.door_control = self.door_control_at = self.block_codes = None
                self.sensor_diagnostics = self.sensor_diagnostics_at = None
                self.controls = None
                self.alert = self.alert_at = None
                self.cycle = self.cycle_at = None
                self.cycle_seen = any(version in line for version in ('BROODER_7', 'BROODER_8', 'BROODER_9', 'BROODER_10', 'BROODER_11', 'BROODER_12', 'BROODER_13', 'BROODER_14', 'BROODER_15', 'BROODER_16'))
            self.sample = None
            return None
        match = STATE.fullmatch(line)
        if not match:
            return None
        heater, alarm, position, target, referenced, stopped = map(int, match.groups())
        if position > TRAVEL or target not in (0, TRAVEL):
            return None
        valid = self.sample is not None and now - self.sample_at < 6
        cycle_fresh = self.cycle is not None and now - self.cycle_at < 6
        cycle = {**self.cycle, 'valid': True} if cycle_fresh else {'valid': False}
        if self.cycle_seen:
            valid = valid and cycle_fresh and self.cycle['id'] != 0
        remapped = self.firmware_reported in REMAPPED_FIRMWARES
        sensor_pin = cycle.get('pin', 'D5' if remapped and self.firmware_reported not in ('BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP') else 'D2–D5' if self.cycle_seen else 'A1')
        door = ('unknown' if not referenced else 'paused' if stopped else
                'sensor_fault' if not valid else
                'closing' if position < target else 'opening' if position > target else
                'closed' if position == TRAVEL else 'open')
        door_control = self.door_control if self.door_control_at is not None and now-self.door_control_at<6 else None
        if door_control and referenced:
            door = ('closing' if position<target else 'opening' if position>target else 'closed' if position==TRAVEL else 'open') if door_control['running'] else ('paused' if position!=target else 'closed' if position==TRAVEL else 'open')
        alert_fresh = self.alert is not None and now-self.alert_at < 6 and self.alert['active'] == bool(alarm)
        alert = {**self.alert, 'valid': True} if alert_fresh else {'valid': False}
        return {
            'firmware_reported': self.firmware_reported,
            'servo': self.servo if self.servo_at is not None and now-self.servo_at < 6 else None,
            'requested_cycle': self.requested_cycle if remapped else None,
            'sensor_diagnostics': self.sensor_diagnostics if self.sensor_diagnostics_at is not None and now-self.sensor_diagnostics_at<6 else None,
            'cycle_selection': 'physical' if self.firmware_reported in ('BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP') else 'software' if remapped else 'physical',
            'door_control': door_control,
            'door_enabled': self.door_enabled if self.controls is not None and now-self.controls_at < 6 else None,
            'controls': self.controls if self.controls is not None and now-self.controls_at < 6 else None,
            'alert': alert, 'cycle': cycle,
            'ok': valid, 'serial_connected': True, 'outputs_valid': True,
            'timestamp': time.time(),
            'temperature': self.sample['temperature'] if valid else None,
            'humidity': self.sample['humidity'] if valid else None,
            'error': None if valid else f'Sin lectura válida y ciclo confirmado del DHT11 en {sensor_pin}',
            'heater': bool(heater), 'alarm': bool(alarm),
            'stopped': bool(stopped), 'referenced': bool(referenced),
            'position': position, 'target': target, 'door': door,
            'door_percent': round(position / TRAVEL * 100, 1) if referenced else None,
            'pins': {'temperature': sensor_pin, 'humidifier': 'D7', 'exhaust': 'D8' if remapped else 'A4',
                     'intake': None if remapped else 'A5', 'alarm': 'A0', 'heater': 'D9' if remapped else 'A2',
                     **({'servo': 'D6', 'door': 'D10–D13'} if remapped else {})},
        }
