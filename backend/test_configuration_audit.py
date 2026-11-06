import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from event_history import EventHistory
from brooder_stream import Telemetry


def reading(timestamp=1, mode='auto', **changes):
    return dict({'timestamp':timestamp,'serial_connected':True,'ok':True,'outputs_valid':True,
        'temperature':26,'humidity':59,'stopped':False,'door_enabled':False,
        'cycle':{'id':4,'valid':True,'pin':'D5','temp_min':24,'temp_max':27,'temp_target':25.5,
                 'humidity_min':50,'humidity_max':60,'humidity_target':55,'heater_on':26,'heater_off':27},
        'controls':{'heater':{'on':True,'mode':mode,'remaining_seconds':300}}},**changes)


class ConfigurationTests(unittest.TestCase):
    def test_configuration_ids_outcome_metrics_and_no_countdown_churn(self):
        with tempfile.TemporaryDirectory() as d:
            h=EventHistory(Path(d)/'db')
            first=reading(); h.record(first)
            config=h.last_config_id
            h.record(reading(2,temperature=27,humidity=61,controls={'heater':{'on':False,'mode':'auto','remaining_seconds':298}}))
            self.assertEqual(config,h.last_config_id)
            h.record(reading(3,mode='off'))
            self.assertNotEqual(config,h.last_config_id)
            rows=list(csv.DictReader(io.StringIO(''.join(h.export_csv('readings')).lstrip('\ufeff'))))
            self.assertEqual(float(rows[0]['temperature_in_range']),1)
            self.assertEqual(float(rows[1]['humidity_in_range']),0)
            self.assertEqual(float(rows[1]['humidity_error_to_center_pct']),6)
            self.assertEqual(float(rows[0]['temperature_error_to_center_c']),.5)
            self.assertTrue(rows[0]['session_id'])
            self.assertEqual(h.configuration(config)['configuration']['profile']['heater_off'],27)
            self.assertIsNone(h.configuration(99999))

    def test_commands_link_before_after_and_durations_even_same_mode(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'db';h=EventHistory(db)
            before=reading(); after=reading(2,mode='off')
            h.audit_command('request1','requested','heater','off',300,before)
            h.audit_command('request1','confirmed','heater','off',300,before,after)
            first=h.recent()[0]['context']; cfg=first['sample']['config_id']
            self.assertEqual(first['before_config_id'],h.recent()[1]['context']['sample']['config_id'])
            self.assertEqual(json.loads(first['before_json'])['controls']['heater']['mode'],'auto')
            self.assertEqual(json.loads(first['after_json'])['controls']['heater']['mode'],'off')
            self.assertEqual(h.configuration(cfg)['configuration']['last_dashboard_request']['heater']['duration_seconds'],300)
            h.audit_command('request2','confirmed','heater','off',900,after,after)
            second=h.recent()[0]['context']['sample']['config_id']; self.assertNotEqual(cfg,second)
            reopened=EventHistory(db)
            reopened.record(after)
            self.assertEqual(reopened.last_config_id,second)
            h.audit_command('request3','unconfirmed','heater','on',60,after,reason='timeout',http_status=504)
            self.assertIsNone(h.recent()[0]['context']['after_json'])
            self.assertEqual(h.recent()[0]['context']['command_status'],'unconfirmed')

    def test_schema_upgrade_keeps_unknown_history_and_source_versions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db'; archive=Path(d)/'data'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE readings(id INTEGER PRIMARY KEY,timestamp REAL,temperature_c REAL)')
                db.execute('INSERT INTO readings VALUES(1,1,25)')
            db.close()
            h=EventHistory(path,archive,software={'version':1,'sources':{'config.h':'original rules'}})
            h.record(reading(2)); old_id=h.last_config_id
            newer=EventHistory(path,archive,software={'version':2,'sources':{'config.h':'changed rules'}})
            newer.record(reading(3)); self.assertNotEqual(old_id,newer.last_config_id)
            self.assertEqual(newer.configuration(old_id)['software']['sources']['config.h'],'original rules')
            rows=list(csv.DictReader(io.StringIO((archive/'readings.csv').read_text(encoding='utf-8-sig'))))
            self.assertEqual(rows[0]['config_id'],'')
            self.assertEqual(rows[0]['session_id'],'')
            self.assertNotEqual(rows[1]['session_id'],rows[2]['session_id'])
            self.assertEqual(len(list((archive/'software').glob('*.json'))),2)
            configs=list(csv.DictReader(io.StringIO((archive/'configurations.csv').read_text(encoding='utf-8-sig'))))
            self.assertEqual(len(configs),2)

    def test_stop_recorded_and_firmware_not_invented(self):
        with tempfile.TemporaryDirectory() as d:
            h=EventHistory(Path(d)/'db');h.record(reading())
            h.record(reading(2,stopped=True))
            self.assertTrue(any(e['message']=='STOP activado' for e in h.recent()))
            parser=Telemetry(); self.assertIsNone(parser.firmware_reported)
            parser.feed('READY BROODER_11_HEAT_LIMIT')
            self.assertEqual(parser.firmware_reported,'BROODER_11_HEAT_LIMIT')

if __name__=='__main__': unittest.main()
