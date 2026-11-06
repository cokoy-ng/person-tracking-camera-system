import importlib.util
import io
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import vision_stream

path = Path(__file__).resolve().parent.parent / 'ai/comp_vision/chick-monitor/worker.py'
spec = importlib.util.spec_from_file_location('chick_worker_test', path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class VisionTests(unittest.TestCase):
    def data(self):
        return dict(status='ready', fresh=True, captured_at=time.time(), timestamp=time.time(),
            sequence=7, count=99, detections=[dict(x=0.2,y=0.3,width=0.2,height=0.4,confidence=0.85)])

    def test_valid_boxes_recompute_visible_count_and_preserve_normalized_coordinates(self):
        result = vision_stream.normalize(self.data())
        self.assertTrue(result['fresh'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['detections'][0]['confidence'], 0.85)

    def test_lost_stale_and_future_results_clear_boxes_and_do_not_report_zero(self):
        for age in (-20, 2, 20):
            data=self.data();data['captured_at']=time.time()-age
            result=vision_stream.normalize(data)
            self.assertFalse(result['fresh'])
            self.assertIsNone(result['count'])
            self.assertEqual(result['detections'], [])
        with patch('vision_stream.urllib.request.urlopen',side_effect=OSError()):
            self.assertIsNone(vision_stream.vision_status()['count'])

    def test_malformed_boxes_are_not_displayed_as_an_empty_scene(self):
        for value in (float('nan'),-1,2,None):
            data=self.data();data['detections'][0]['x']=value
            result=vision_stream.normalize(data)
            self.assertFalse(result['fresh'])
            self.assertIsNone(result['count'])

    def test_empty_detection_is_a_real_zero_and_loading_is_not(self):
        vision=worker.Vision()
        self.assertIsNone(vision.snapshot()['count'])
        vision.set_result(status='ready',count=0,detections=[],captured_at=time.time(),timestamp=time.time())
        result=vision_stream.normalize(vision.snapshot())
        self.assertTrue(result['fresh'])
        self.assertEqual(result['count'], 0)
        vision.stopped.set()
        self.assertFalse(vision.snapshot()['fresh'])
        self.assertIsNone(vision.snapshot()['count'])

    def test_api_does_not_forward_local_paths_or_process_metadata(self):
        data=self.data();data.update(project='C:/private',pid=123,error='internal error')
        with patch('vision_stream.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(data).encode())):
            result=vision_stream.vision_status()
        self.assertNotIn('project', result)
        self.assertNotIn('pid', result)
        self.assertNotIn('error', result)

    def test_tracking_groups_and_zones_are_cleared_when_result_expires(self):
        data=self.data()
        data.update(groups=[dict(id=1,ids=[1,2,3],duration_seconds=10)],near_pairs=[dict(a=1,b=2,distance_ratio=.1)],zone_counts=[dict(id='feeder',count=3,ids=[1,2,3])],captured_at=time.time()-10)
        result=vision_stream.normalize(data)
        self.assertEqual(result['groups'],[])
        self.assertEqual(result['zone_counts'],[])
        self.assertEqual(result['near_pairs'],[])
        self.assertIsNone(result['confirmed_count'])

    def test_zone_counts_are_derived_from_confirmed_boxes_not_arbitrary_upstream_counts(self):
        data=self.data()
        data['detections'][0].update(track_id=1,confirmed=True,trail=[])
        data['configuration']=dict(vision_stream.DEFAULT,zones=[dict(id='feeder',x=0,y=0,width=1,height=1)])
        data.update(configuration_revision=0,zone_counts=[dict(id='feeder',count=90,ids=[1])])
        result=vision_stream.normalize(data)
        self.assertEqual(result['zone_counts'][0]['count'],1)
        self.assertEqual(result['detections'][0]['track_id'],1)
