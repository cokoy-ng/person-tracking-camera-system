"""API audit tests use a temporary database and never open a serial port."""
import asyncio
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from types import SimpleNamespace
from event_history import EventHistory


class ControlAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.history=EventHistory(Path(self.directory.name)/'events.db')
        with patch.dict(sys.modules, {'serial_bridge':SimpleNamespace(serial=None)}), patch('event_history.EventHistory',return_value=self.history), patch('configuration_audit.software_snapshot',return_value={}):
            sys.modules.pop('main',None)
            self.main=importlib.import_module('main')
        self.main.state['latest']={'timestamp':1,'ok':False,'serial_connected':False}
        self.request=self.main.ControlRequest(output='heater',mode='off',duration_seconds=300)

    def tearDown(self):
        sys.modules.pop('main',None)
        self.directory.cleanup()

    def statuses(self):
        return [e['context']['command_status'] for e in reversed(self.history.recent()) if e['kind']=='command']

    def test_disconnected_request_is_recorded_and_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(self.main.control_output(self.request))
        self.assertEqual(raised.exception.status_code,409)
        self.assertEqual(self.statuses(),['requested','rejected'])
        self.assertTrue(self.main.commands.empty())

    def test_confirmed_and_unconfirmed_are_distinct(self):
        row={'timestamp':2,'ok':False,'controls':{'heater':{'mode':'off','on':False}}}
        with patch.object(self.main,'execute_control',AsyncMock(return_value=(row,row['controls']['heater']))):
            result=asyncio.run(self.main.control_output(self.request))
        self.assertTrue(result['confirmed'])
        self.assertEqual(self.statuses(),['requested','confirmed'])
        context=self.history.recent()[0]['context']
        self.assertEqual(context['request_id'],result['request_id'])
        self.assertEqual(context['duration_seconds'],300)
        with patch.object(self.main,'execute_control',AsyncMock(side_effect=HTTPException(504,'Sin ACK'))):
            with self.assertRaises(HTTPException): asyncio.run(self.main.control_output(self.request))
        self.assertEqual(self.statuses()[-2:],['requested','unconfirmed'])

    def test_no_command_sent_if_request_cannot_be_persisted(self):
        with patch.object(self.history,'audit_command',side_effect=OSError('disk full')), patch.object(self.main,'execute_control',AsyncMock()) as execute:
            with self.assertRaises(HTTPException) as raised: asyncio.run(self.main.control_output(self.request))
        self.assertEqual(raised.exception.status_code,503)
        execute.assert_not_awaited()

    def test_invalid_request_recorded_without_actuation(self):
        request=SimpleNamespace(url=SimpleNamespace(path='/api/control'))
        result=asyncio.run(self.main.invalid_request(request,RequestValidationError([])))
        self.assertEqual(result.status_code,422)
        self.assertEqual(self.statuses(),['rejected'])
        self.assertTrue(self.main.commands.empty())

    def test_device_audit_and_failed_storage(self):
        request=self.main.DeviceRequest(action='servo_cycle')
        row={'timestamp':2,'servo':{'running':True}}
        with patch.object(self.main,'execute_device',AsyncMock(return_value=row)):
            result=asyncio.run(self.main.control_device(request))
        self.assertTrue(result['confirmed'])
        self.assertEqual(self.statuses(),['requested','confirmed'])
        with patch.object(self.history,'audit_command',side_effect=OSError('disk full')), patch.object(self.main,'execute_device',AsyncMock()) as execute:
            with self.assertRaises(HTTPException): asyncio.run(self.main.control_device(request))
            execute.assert_not_awaited()

    def test_device_queue_checks_acknowledged_state(self):
        async def run():
            import time
            self.main.state['latest']={'timestamp':time.time(),'serial_connected':True,
                'firmware_reported':'BROODER_12_PIN_REMAP','servo':{'running':False}}
            task=asyncio.create_task(self.main.execute_device(self.main.DeviceRequest(action='cycle',cycle=3)))
            await asyncio.sleep(0)
            command,expires,future=self.main.commands.get_nowait()
            self.assertEqual(command,'~333')
            future.set_result({'requested_cycle':3})
            self.assertEqual(await task,{'requested_cycle':3})
        asyncio.run(run())

    def test_servo_is_never_retransmitted_without_ack(self):
        from concurrent.futures import Future
        from unittest.mock import Mock
        future=Future()
        fake=Mock()
        fake.readline.return_value=b''
        self.main.state['serial']=fake
        self.main.commands.put_nowait(('~Z5A',100,future))
        clock=[0]
        def monotonic():
            clock[0]+=.2
            return clock[0]
        with patch.object(self.main.time,'monotonic',side_effect=monotonic):
            with self.assertRaises(TimeoutError): self.main.read_once()
        self.assertEqual(fake.write.call_count,1)
        fake.write.assert_called_once_with(b"~Z5A\n")
        self.assertIsInstance(future.exception(),TimeoutError)

    def test_stale_frame_error_does_not_override_matching_ack(self):
        from concurrent.futures import Future
        from unittest.mock import Mock
        future=Future()
        fake=Mock()
        fake.readline.side_effect=[b'ERR FRAME\n',b'OK CYCLE 4\n',b'state\n']
        self.main.state['serial']=fake
        self.main.commands.put_nowait(('~434',1e30,future))
        row={'requested_cycle':4}
        with patch.object(self.main.telemetry,'feed',side_effect=[None,None,row]):
            self.assertEqual(self.main.read_once(),row)
        self.assertEqual(future.result(),row)

    def test_busy_servo_and_removed_output_do_not_enqueue(self):
        import time
        self.main.state['latest']={'timestamp':time.time(),'serial_connected':True,
            'firmware_reported':'BROODER_12_PIN_REMAP','servo':{'running':True},'controls':{'intake':{}}}
        with self.assertRaises(HTTPException):
            asyncio.run(self.main.execute_device(self.main.DeviceRequest(action='servo_cycle')))
        with self.assertRaises(HTTPException):
            asyncio.run(self.main.execute_control(self.main.ControlRequest(output='intake',mode='on')))
        self.assertTrue(self.main.commands.empty())


    def test_door_reference_requires_explicit_confirmation(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError): self.main.DeviceRequest(action='door_reference_open')
        self.assertTrue(self.main.DeviceRequest(action='door_reference_open',confirmed_position=True).confirmed_position)

    def test_door_motion_requires_reference_without_enqueuing(self):
        import time
        self.main.state['latest']={'timestamp':time.time(),'serial_connected':True,
            'firmware_reported':'BROODER_13_MANUAL_DOOR','door_control':{'running':False},'referenced':False}
        with self.assertRaises(HTTPException):
            asyncio.run(self.main.execute_device(self.main.DeviceRequest(action='door_open')))
        self.assertTrue(self.main.commands.empty())

    def test_door_command_ack_and_state(self):
        async def run():
            import time
            self.main.state['latest']={'timestamp':time.time(),'serial_connected':True,
                'firmware_reported':'BROODER_13_MANUAL_DOOR','door_control':{'running':False},'referenced':True}
            task=asyncio.create_task(self.main.execute_device(self.main.DeviceRequest(action='door_close')))
            await asyncio.sleep(0)
            command,_,future=self.main.commands.get_nowait()
            self.assertEqual(command,'~D44')
            self.assertEqual(self.main.command_ack(command),'OK DOOR CLOSE')
            future.set_result({'referenced':True,'target':49152,'door_control':{'running':True}})
            self.assertEqual((await task)['target'],49152)
        asyncio.run(run())

    def test_physical_cycle_rejects_software_selection(self):
        import time
        self.main.state['latest']={'timestamp':time.time(),'serial_connected':True,'firmware_reported':'BROODER_14_PHYSICAL_CYCLES'}
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.main.execute_device(self.main.DeviceRequest(action='cycle',cycle=4)))
        self.assertEqual(error.exception.status_code,409)
        self.assertTrue(self.main.commands.empty())

    def test_pump_automatic_mode_is_rejected_without_sending(self):
        import time
        self.main.state['latest']={'timestamp':time.time(),'serial_connected':True,
            'firmware_reported':'BROODER_16_MANUAL_PUMP','controls':{'humidifier':{'mode':'off','on':False}}}
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.main.execute_control(self.main.ControlRequest(output='humidifier',mode='auto')))
        self.assertEqual(error.exception.status_code,409)
        self.assertTrue(self.main.commands.empty())

if __name__=='__main__': unittest.main()
