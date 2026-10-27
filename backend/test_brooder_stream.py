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

if __name__ == '__main__':
    unittest.main()
