import tempfile
import unittest
import csv
import io
from pathlib import Path
from event_history import EventHistory

class HistoryTests(unittest.TestCase):
    def test_changes_persistence_and_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'events.db'
            history=EventHistory(path)
            row={'timestamp':1,'serial_connected':True,'outputs_valid':True,'ok':True,
                 'temperature':25,'humidity':55,'cycle':{'valid':True,'id':4,'heater_on':26,'heater_off':27},
                 'controls':{'heater':{'mode':'auto','on':True}}}
            history.record(row)
            n=len(history.recent())
            history.record(dict(row,timestamp=2)); self.assertEqual(len(history.recent()),n)
            changed=dict(row,timestamp=3,temperature=27,controls={'heater':{'mode':'auto','on':False}})
            history.record(changed)
            self.assertEqual(len(history.recent()),n+2)
            self.assertIn('apagada',history.recent()[0]['message'])
            self.assertEqual(history.recent()[0]['context']['temperature'],27)
            history.record({'timestamp':4,'serial_connected':False,'outputs_valid':False,'ok':False})
            self.assertIn('desconectado',history.recent()[0]['message'])
            history.record(dict(changed,timestamp=5))
            self.assertIn('Estado observado',history.recent()[0]['message'])
            reopened=EventHistory(path)
            self.assertEqual(reopened.recent(),history.recent())
            reopened.record(dict(changed,timestamp=6,ok=False,temperature=None,humidity=None))
            self.assertIsNone(reopened.recent()[0]['context']['temperature'])
            reopened.command('heater','off',0,changed)
            self.assertIn('hasta pulsar',reopened.recent()[0]['message'])

    def test_countdown_does_not_create_false_output_changes(self):
        with tempfile.TemporaryDirectory() as d:
            history=EventHistory(Path(d)/'events.db')
            row={'timestamp':1,'serial_connected':True,'outputs_valid':True,'ok':False,
                 'controls':{'heater':{'mode':'off','on':False,'remaining_seconds':300}}}
            history.record(row); n=len(history.recent())
            history.record(dict(row,timestamp=2,controls={'heater':{'mode':'off','on':False,'remaining_seconds':298}}))
            self.assertEqual(len(history.recent()),n)

    def test_pages_stable_while_new_events_arrive_and_filter_before_limit(self):
        with tempfile.TemporaryDirectory() as d:
            history=EventHistory(Path(d)/'events.db')
            for n in range(73):
                history.command('heater','off',60,{'timestamp':n,'ok':False})
            first=history.page()
            self.assertEqual((len(first['events']),first['total'],first['pages']),(25,73,3))
            for n in range(5): history.command('alarm','auto',0,{'timestamp':100+n})
            ids=[event['id'] for event in first['events']]
            for page in (2,3):
                result=history.page(page=page,snapshot_id=first['snapshot_id'])
                ids.extend(event['id'] for event in result['events'])
                self.assertEqual(result['total'],73)
            self.assertEqual(ids,list(range(73,0,-1)))
            self.assertEqual(history.page()['total'],78)
            self.assertEqual(history.page(kind='reading')['total'],0)
            self.assertEqual(history.page(kind='output')['total'],78)
            self.assertEqual(history.page(page=999)['page'],4)
            self.assertEqual(history.page(snapshot_id=0)['events'],[])

    def test_csv_samples_numeric_missing_values_and_commands(self):
        with tempfile.TemporaryDirectory() as d:
            history=EventHistory(Path(d)/'events.db')
            row={'timestamp':1,'serial_connected':True,'outputs_valid':True,'ok':True,
                 'temperature':26,'humidity':59,'cycle':{'valid':True,'id':4,'temp_max':27},
                 'alert':{'valid':True,'active':False,'reasons':0},
                 'controls':{'heater':{'mode':'off','on':False,'remaining_seconds':900}}}
            history.record(row)
            history.record(dict(row,timestamp=2))
            history.record(dict(row,timestamp=3,serial_connected=False,ok=False,outputs_valid=False))
            history.command('heater','off',900,row)
            def exported(dataset,kind='all'):
                return list(csv.DictReader(io.StringIO(''.join(history.export_csv(dataset,kind)).lstrip('\ufeff'))))
            readings=exported('readings')
            self.assertEqual(len(readings),3)  # unchanged values are retained
            self.assertEqual(float(readings[0]['temperature_c']),26)
            self.assertEqual(float(readings[0]['heater_on']),0)
            self.assertEqual(readings[0]['heater_mode'],'off')
            self.assertEqual(float(readings[0]['alarm_active']),0)
            self.assertEqual(readings[0]['alarm_on'],'')  # no physical output reported
            self.assertTrue(readings[0]['timestamp_utc'].endswith('+00:00'))
            for key in ('temperature_c','humidity_pct','heater_on','heater_mode','cycle','alarm_active'):
                self.assertEqual(readings[2][key],'',key)
            events=exported('events','output')
            self.assertTrue(all(e['kind']=='output' for e in events))
            self.assertEqual(events[-1]['duration_seconds'],'900')
            self.assertEqual(events[-1]['output'],'heater')
            self.assertEqual(events[0]['output_on'],'0')

    def test_archives_keep_legacy_events_append_and_recover_partial_write(self):
        with tempfile.TemporaryDirectory() as d:
            legacy=Path(d)/'legacy.db'; destination=Path(d)/'backend/data'
            old=EventHistory(legacy)
            old.command('heater','off',0,{'timestamp':1})
            new=EventHistory(legacy,archive_dir=destination)
            self.assertEqual(new.recent(),old.recent())
            self.assertIn('Mando confirmado',(destination/'events.csv').read_text())
            new.command('alarm','auto',0,{'timestamp':2})
            new.record({'timestamp':3,'ok':False,'serial_connected':False})
            for dataset in ('events','readings'):
                self.assertEqual((destination/(dataset+'.csv')).read_bytes().decode('utf-8'),''.join(new.export_csv(dataset)))
            with (destination/'events.csv').open('a') as target: target.write('partial corrupt row')
            reopened=EventHistory(legacy,archive_dir=destination)
            self.assertEqual((destination/'events.csv').read_bytes().decode('utf-8'),''.join(reopened.export_csv('events')))

    def test_empty_csv_has_header_and_export_crosses_batches(self):
        with tempfile.TemporaryDirectory() as d:
            history=EventHistory(Path(d)/'events.db')
            self.assertIn('temperature_c',''.join(history.export_csv('readings')))
            for i in range(503): history.command('alarm','auto',0,{'timestamp':i})
            rows=list(csv.DictReader(io.StringIO(''.join(history.export_csv('events')).lstrip('\ufeff'))))
            self.assertEqual(len(rows),503)
            self.assertEqual([int(r['id']) for r in rows],list(range(1,504)))

if __name__=='__main__': unittest.main()
