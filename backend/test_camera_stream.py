import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import camera_stream
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scrips'))
from camera_capture import Capture


class CameraStreamTests(unittest.TestCase):
    def status(self, age=0):
        return dict(ok=True, transport='memory-v1', timestamp=time.time()-age,
                    name='USB', width=640, height=480, frames=100, fps=30,
                    device_fps=30, encode_ms=1)

    def packet(self, sequence=1, age=0, jpeg=b'\xff\xd8sample\xff\xd9'):
        return (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(jpeg)).encode()+
                b'\r\nX-Sequence: '+str(sequence).encode()+b'\r\nX-Captured-At: '+
                str(time.time()-age).encode()+b'\r\n\r\n'+jpeg+b'\r\n')

    def test_status_rejects_stale_or_unavailable_capture(self):
        with patch('camera_stream.urllib.request.urlopen', side_effect=OSError('disconnected')):
            self.assertFalse(camera_stream.camera_status()['ok'])
        with patch('camera_stream.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(self.status(10)).encode())):
            self.assertFalse(camera_stream.camera_status()['ok'])
        with patch('camera_stream.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(self.status()).encode())):
            self.assertEqual(camera_stream.camera_status()['fps'], 30)

    def test_relay_drops_old_frames_and_reports_delivery_without_reencoding(self):
        source = io.BytesIO(self.packet(1, age=2)+self.packet(2))
        with patch('camera_stream.urllib.request.urlopen', return_value=source):
            stream = camera_stream.mjpeg_frames()
            frame = next(stream)
            self.assertIn(b'X-Sequence: 2\r\n', frame)
            self.assertIn(b'\xff\xd8sample\xff\xd9', frame)
            self.assertEqual(len(camera_stream._streams), 1)
            with self.assertRaises(StopIteration):
                next(stream)
        self.assertFalse(camera_stream._streams)
        self.assertTrue(source.closed)

    def test_corrupt_or_truncated_video_ends_cleanly(self):
        for content in (self.packet(jpeg=b'incomplete'), self.packet()[:-10], b'--frame\r\n'):
            with patch('camera_stream.urllib.request.urlopen', return_value=io.BytesIO(content)):
                self.assertEqual(list(camera_stream.mjpeg_frames()), [])

    def test_slow_consumer_receives_newest_frame_without_a_queue(self):
        capture = Capture()
        for i in range(100):
            capture.publish(str(i).encode(), {})
        seq, stamp, jpeg = capture.next_frame(0)
        self.assertEqual((seq, jpeg), (100, b'99'))
        self.assertTrue(capture.status()['ok'])
        capture.stop()
        self.assertIsNone(capture.next_frame(seq))
        self.assertFalse(capture.status()['ok'])


if __name__ == '__main__':
    unittest.main()
