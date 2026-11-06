import unittest
from brooder_stream import Telemetry

class TelemetryTests(unittest.TestCase):
    def test_real_sequence_and_stale(self):
        t = Telemetry()
        self.assertIsNone(t.feed('TEMP 27 HUM 94', 0))
        line = 'STATE heater=0 alarm=0 position=49152 target=49152 referenced=1 stopped=0'
        r = t.feed(line, 1)
        self.assertTrue(r['ok'])
        self.assertEqual((r['door'], r['door_percent'], r['temperature']), ('closed', 100, 27))
        self.assertFalse(t.feed(line, 6)['ok'])
        self.assertEqual(t.feed(line, 6)['door'], 'sensor_fault')

    def test_fault_and_corruption(self):
        t = Telemetry()
        t.feed('TEMP 24 HUM 50', 0)
        t.feed('FAULT DHT11', 1)
        r = t.feed('STATE heater=0 alarm=1 position=0 target=49152 referenced=1 stopped=0', 2)
        self.assertFalse(r['ok'])
        self.assertTrue(r['alarm'])
        self.assertIsNone(t.feed('garbage TEMP 24 HUM 50', 3))
        self.assertIsNone(t.feed('STATE heater=1 alarm=1 position=99999 target=49152 referenced=1 stopped=0', 3))

    def test_movement_unknown_and_stop(self):
        t = Telemetry()
        t.feed('TEMP 24 HUM 50', 0)
        for values, expected in [
            ('100 49152 1 0', 'closing'), ('100 0 1 0', 'opening'),
            ('100 0 0 0', 'unknown'), ('100 0 1 1', 'paused')]:
            pos, target, ref, stop = values.split()
            r=t.feed(f'STATE heater=1 alarm=1 position={pos} target={target} referenced={ref} stopped={stop}', 1)
            self.assertEqual(r['door'], expected)

class CycleTelemetryTests(unittest.TestCase):
    state = 'STATE heater=1 alarm=1 position=49152 target=49152 referenced=1 stopped=0'
    def test_four_profiles_and_air_outputs(self):
        for i, limits in enumerate([(33,34,60,70),(30,32,50,65),(27,29,50,60),(24,27,50,60)],1):
            t=Telemetry(); t.feed('TEMP 26 HUM 50',0)
            t.feed(f'CYCLE id={i} pin={i+1} humidifier=1 exhaust=0 intake=0 reason=4',0)
            r=t.feed(self.state,1)
            self.assertTrue(r['ok']); self.assertTrue(r['cycle']['humidifier'])
            self.assertEqual(r['pins']['temperature'],f'D{i+1}')
            self.assertEqual(tuple(r['cycle'][k] for k in ['temp_min','temp_max','humidity_min','humidity_max']),limits)
    def test_missing_cycle_and_corruption_disable_valid_reading(self):
        t=Telemetry(); t.feed('READY BROODER_7_CYCLES',0)
        t.feed('TEMP 26 HUM 50',0)
        self.assertFalse(t.feed(self.state,1)['ok'])
        for invalid in ['CYCLE id=1 pin=5 humidifier=0 exhaust=0 intake=0 reason=0','CYCLE id=0 pin=0 humidifier=1 exhaust=0 intake=0 reason=4','CYCLE garbage']:
            t.feed(invalid,1)
            self.assertFalse(t.feed(self.state,1)['ok'])
        t.feed('CYCLE id=0 pin=0 humidifier=0 exhaust=0 intake=0 reason=0',1)
        self.assertEqual(t.feed(self.state,1)['cycle']['id'],0)
        self.assertFalse(t.feed(self.state,1)['ok'])
    def test_cycle_does_not_survive_stale_or_restart(self):
        t=Telemetry(); t.feed('CYCLE id=1 pin=2 humidifier=0 exhaust=0 intake=0 reason=0',0)
        t.feed('TEMP 26 HUM 50',5)
        self.assertFalse(t.feed(self.state,6)['ok'])
        t.feed('CYCLE id=1 pin=2 humidifier=0 exhaust=0 intake=0 reason=0',7)
        t.feed('READY BROODER_7_CYCLES',8)
        t.feed('TEMP 26 HUM 50',8)
        self.assertFalse(t.feed(self.state,8)['ok'])

class AlertTelemetryTests(unittest.TestCase):
    quiet = 'STATE heater=0 alarm=0 position=49152 target=49152 referenced=1 stopped=0'
    alarm = quiet.replace('alarm=0','alarm=1')
    def test_pending_confirmed_and_recovery(self):
        t=Telemetry()
        t.feed('ALERT active=0 pending=1 recovering=0 sounding=0 reasons=4',0)
        self.assertTrue(t.feed(self.quiet,0)['alert']['pending'])
        t.feed('ALERT active=1 pending=0 recovering=0 sounding=1 reasons=4',1)
        self.assertTrue(t.feed(self.alarm,1)['alert']['sounding'])
        t.feed('ALERT active=1 pending=0 recovering=1 sounding=0 reasons=4',2)
        self.assertTrue(t.feed(self.alarm,2)['alert']['recovering'])
        self.assertFalse(t.feed(self.alarm,8)['alert']['valid'])
    def test_inconsistent_diagnostics_are_unknown(self):
        for bad in ['ALERT active=0 pending=1 recovering=0 sounding=1 reasons=4',
                    'ALERT active=1 pending=1 recovering=0 sounding=0 reasons=4',
                    'ALERT active=0 pending=0 recovering=1 sounding=0 reasons=4',
                    'ALERT active=1 pending=0 recovering=0 sounding=0 reasons=64']:
            t=Telemetry(); t.feed(bad,0)
            self.assertFalse(t.feed(self.alarm,0)['alert']['valid'])
        t=Telemetry(); t.feed('ALERT active=1 pending=0 recovering=0 sounding=1 reasons=4',0)
        self.assertFalse(t.feed(self.quiet,0)['alert']['valid'])
    def test_centers_match_user_ranges(self):
        from brooder_stream import PROFILES
        self.assertEqual([(p['temp_target'],p['humidity_target']) for p in PROFILES.values()],[(33.5,65),(31,57.5),(28,55),(25.5,55)])
        self.assertEqual([(p['heater_on'],p['heater_off']) for p in PROFILES.values()],[(33,34),(31,32),(28,29),(26,27)])
        self.assertEqual((PROFILES[2]['humidifier_on'],PROFILES[2]['humidifier_off']),(55.5,57.5))
        self.assertEqual((PROFILES[2]['vent_humidity_on'],PROFILES[2]['vent_humidity_off']),(59.5,57.5))

class ThreeAirOutputsTests(unittest.TestCase):
    state = 'STATE heater=0 alarm=0 position=49152 target=49152 referenced=1 stopped=0'
    def test_three_outputs_reasons_and_thresholds(self):
        t=Telemetry();t.feed('TEMP 31 HUM 62',0)
        for reason,humidifier,vent in [(1,0,1),(2,0,1),(3,0,1),(4,1,0),(8,0,0),(0,0,0)]:
            t.feed(f'CYCLE id=2 pin=3 humidifier={humidifier} exhaust={vent} intake={vent} reason={reason}',0)
            c=t.feed(self.state,0)['cycle']
            self.assertEqual(c['air_reason'],reason)
            self.assertEqual((c['humidifier'],c['exhaust'],c['intake']),(bool(humidifier),bool(vent),bool(vent)))
            self.assertEqual((c['vent_humidity_on'],c['vent_humidity_off']),(59.5,57.5))
            self.assertEqual((c['vent_temp_on'],c['vent_temp_off']),(32,31))
    def test_corruption_and_new_banner(self):
        t=Telemetry();t.feed('READY BROODER_9_THREE_AIR',0);t.feed('TEMP 31 HUM 62',0)
        self.assertFalse(t.feed(self.state,0)['ok'])
        for line in ['CYCLE id=1 pin=2 humidifier=0 exhaust=2 intake=0 reason=1','CYCLE id=0 pin=0 humidifier=0 exhaust=0 intake=0 reason=2','CYCLE id=1 pin=2 humidifier=0 exhaust=1 intake=1 reason=16','CYCLE id=1 pin=2 humidifier=0 exhaust=1 reason=1']:
            t.feed(line,0);self.assertFalse(t.feed(self.state,0)['cycle']['valid'])

class ManualTests(unittest.TestCase):
    def test_confirmed_controls_expire_and_reset(self):
        t=Telemetry()
        state='STATE heater=0 alarm=0 position=49152 target=49152 referenced=1 stopped=0'
        t.feed('CONTROL modes=02100 outputs=01000 door_enabled=0',0)
        r=t.feed(state,0)
        self.assertEqual(r['controls']['humidifier'],{'mode':'on','on':True})
        self.assertFalse(r['door_enabled'])
        self.assertIsNone(t.feed(state,6)['controls'])
        t.feed('CONTROL modes=02100 outputs=01000 door_enabled=0',7)
        t.feed('READY BROODER_10_MANUAL',8)
        self.assertIsNone(t.feed(state,8)['controls'])
    def test_independent_manual_fans(self):
        t=Telemetry()
        t.feed('CYCLE id=4 pin=5 humidifier=0 exhaust=1 intake=0 reason=0',0)
        self.assertTrue(t.cycle['exhaust'])
        self.assertFalse(t.cycle['intake'])

if __name__ == '__main__':
    unittest.main()

class RemappedWiringTests(unittest.TestCase):
    def test_d5_sensor_new_outputs_and_restart(self):
        t = Telemetry()
        t.feed('READY BROODER_12_PIN_REMAP', 0)
        t.feed('CYCLE id=4 pin=5 humidifier=0 exhaust=0 intake=0 reason=0', 1)
        t.feed('TEMP 25 HUM 55', 1)
        state = 'STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=1'
        row = t.feed(state, 1)
        self.assertTrue(row['ok'])
        self.assertEqual(row['pins'], {'temperature':'D5', 'heater':'D9', 'humidifier':'D7',
                                      'exhaust':'D8', 'intake':None, 'alarm':'A0',
                                      'servo':'D6', 'door':'D10–D13'})
        self.assertEqual(row['cycle']['pin'], 'D5')
        t.feed('READY BROODER_12_PIN_REMAP', 2)
        self.assertFalse(t.feed(state, 2)['ok'])

    def test_old_sensor_pin_rejected_by_new_firmware(self):
        t = Telemetry()
        t.feed('READY BROODER_12_PIN_REMAP', 0)
        t.feed('CYCLE id=4 pin=15 humidifier=0 exhaust=0 intake=0 reason=0', 1)
        t.feed('TEMP 25 HUM 55', 1)
        row = t.feed('STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=1', 1)
        self.assertFalse(row['ok'])
        self.assertEqual(row['pins']['temperature'], 'D5')


class DeviceTelemetryTests(unittest.TestCase):
    def test_identity_requested_cycle_servo_and_expiry(self):
        t=Telemetry()
        t.feed('FIRMWARE BROODER_12_PIN_REMAP',0)
        t.feed('CYCLE_REQUEST id=2',0)
        t.feed('SERVO stage=1 angle=180 remaining=22',0)
        state='STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=1'
        row=t.feed(state,1)
        self.assertEqual(row['requested_cycle'],2)
        self.assertTrue(row['servo']['running'])
        self.assertEqual(row['pins']['temperature'],'D5')
        self.assertIsNone(t.feed(state,6)['servo'])
        t.feed('SERVO stage=0 angle=130 remaining=0',7)
        self.assertFalse(t.feed(state,7)['servo']['running'])
        t.feed('READY BROODER_12_PIN_REMAP',8)
        self.assertIsNone(t.feed(state,8)['servo'])
        self.assertIsNone(t.feed(state,8)['requested_cycle'])


class ManualDoorTelemetryTests(unittest.TestCase):
    def test_manual_limits_and_door_independent_of_climate_pause(self):
        t=Telemetry()
        t.feed('FIRMWARE BROODER_13_MANUAL_DOOR',0)
        t.feed('DOOR_CONTROL running=1 manual_only=1',0)
        t.feed('BLOCK codes=3,0,0',0)
        t.feed('CONTROL modes=22200 outputs=01100 door_enabled=1 remaining=60,60,60,0,0',0)
        row=t.feed('STATE heater=0 alarm=0 position=100 target=49152 referenced=1 stopped=1',1)
        self.assertEqual(row['door'],'closing')
        self.assertTrue(row['door_control']['running'])
        self.assertEqual(row['controls']['heater']['blocked_reason'],'Temperatura en el máximo del ciclo')
        self.assertIsNone(row['controls']['humidifier']['blocked_reason'])
        self.assertEqual(row['pins']['heater'],'D9')
        t.feed('DOOR_CONTROL running=0 manual_only=1',2)
        row=t.feed('STATE heater=0 alarm=0 position=100 target=49152 referenced=1 stopped=1',2)
        self.assertEqual(row['door'],'paused')
        self.assertIsNone(t.feed('STATE heater=0 alarm=0 position=100 target=49152 referenced=1 stopped=1',8)['door_control'])


class PhysicalCycleTests(unittest.TestCase):
    def test_all_four_sensor_pins_select_their_own_profile(self):
        t=Telemetry()
        t.feed('FIRMWARE BROODER_14_PHYSICAL_CYCLES',0)
        for cycle in range(1,5):
            t.feed(f'CYCLE id={cycle} pin={cycle+1} humidifier=0 exhaust=0 intake=0 reason=0',cycle)
            t.feed('TEMP 27 HUM 55',cycle)
            row=t.feed('STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=1',cycle)
            self.assertTrue(row['ok'])
            self.assertEqual(row['cycle']['id'],cycle)
            self.assertEqual(row['pins']['temperature'],f'D{cycle+1}')
            self.assertEqual(row['cycle_selection'],'physical')
            self.assertEqual(row['pins']['heater'],'D9')
        t.feed('CYCLE id=1 pin=5 humidifier=0 exhaust=0 intake=0 reason=0',5)
        self.assertFalse(t.feed('STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=1',5)['ok'])


class SensorPinDiagnosticsTests(unittest.TestCase):
    def test_no_response_is_visible_and_expires(self):
        t=Telemetry()
        t.feed('FIRMWARE BROODER_14_PHYSICAL_CYCLES',0)
        t.feed('SENSOR D2=1 D3=1 D4=1 D5=1 mask=0',0)
        line='STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=1'
        row=t.feed(line,1)
        self.assertFalse(row['ok'])
        self.assertEqual(row['sensor_diagnostics'],{'pins':{'D2':1,'D3':1,'D4':1,'D5':1},'mask':0})
        self.assertIsNone(t.feed(line,6)['sensor_diagnostics'])


class AutomaticCycleFirmwareTests(unittest.TestCase):
    def test_automatic_firmware_preserves_physical_cycle_mapping(self):
        t=Telemetry()
        t.feed('READY BROODER_15_AUTO_CYCLES',0)
        t.feed('CYCLE id=1 pin=2 humidifier=1 exhaust=0 intake=0 reason=4',1)
        t.feed('TEMP 32 HUM 55',1)
        row=t.feed('STATE heater=1 alarm=0 position=0 target=0 referenced=0 stopped=0',1)
        self.assertTrue(row['ok'])
        self.assertTrue(row['heater'])
        self.assertEqual(row['cycle_selection'],'physical')
        self.assertEqual(row['pins']['temperature'],'D2')
        self.assertTrue(row['cycle']['heater_immediate_below_min'])
        self.assertFalse(row['stopped'])


class ManualPumpFirmwareTests(unittest.TestCase):
    def test_low_humidity_does_not_mean_pump_on(self):
        t=Telemetry()
        t.feed('FIRMWARE BROODER_16_MANUAL_PUMP',0)
        t.feed('CONTROL modes=01000 outputs=00100 door_enabled=1 remaining=0,0,0,0,0',0)
        t.feed('CYCLE id=3 pin=4 humidifier=0 exhaust=1 intake=0 reason=1',0)
        t.feed('TEMP 31 HUM 10',0)
        row=t.feed('STATE heater=0 alarm=0 position=0 target=0 referenced=0 stopped=0',1)
        self.assertTrue(row['ok'])
        self.assertFalse(row['controls']['humidifier']['on'])
        self.assertTrue(row['controls']['humidifier']['manual_only'])
        self.assertEqual(row['cycle_selection'],'physical')
        self.assertEqual(row['pins']['temperature'],'D4')
