import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ai/comp_vision/chick-monitor'))
from tracking.temporary import TemporaryTracker, distance
from behavior.configuration import Configuration, Conflict, DEFAULT, validate
from behavior.spatial import SpatialAnalysis


def box(x, y=.3, track_id=None):
    data=dict(x=x,y=y,width=.04,height=.06,confidence=.9)
    if track_id is not None:
        data.update(track_id=track_id,confirmed=True)
    return data


class TrackingTests(unittest.TestCase):
    def test_stable_one_to_one_ids_despite_detection_order_and_small_motion(self):
        tracker=TemporaryTracker()
        first=tracker.update([box(.1),box(.7)],100,320,240)
        self.assertFalse(first[0]['confirmed'])
        second=tracker.update([box(.69),box(.11)],100.25,320,240)
        self.assertEqual([b['track_id'] for b in second],[first[1]['track_id'],first[0]['track_id']])
        self.assertTrue(all(b['confirmed'] and len(b['trail'])==2 for b in second))

    def test_missing_detection_never_creates_ghost_boxes_or_immediate_confirmation(self):
        tracker=TemporaryTracker()
        initial=tracker.update([box(.2)],100,320,240)[0]['track_id']
        tracker.update([box(.2)],100.25,320,240)
        self.assertEqual(tracker.update([],100.5,320,240),[])
        again=tracker.update([box(.21)],100.75,320,240)[0]
        self.assertEqual(again['track_id'],initial)
        self.assertFalse(again['confirmed'])
        after_gap=tracker.update([box(.21)],102,320,240)[0]
        self.assertGreater(after_gap['track_id'],initial)
        self.assertEqual(len(after_gap['trail']),1)

    def test_trails_are_bounded_and_geometry_or_clock_changes_do_not_reuse_ids(self):
        tracker=TemporaryTracker()
        for i in range(80):
            result=tracker.update([box(.2)],100+i*.25,320,240)[0]
        self.assertLessEqual(len(result['trail']),24)
        self.assertLessEqual(result['trail'][-1]['timestamp']-result['trail'][0]['timestamp'],6)
        changed=tracker.update([box(.2)],120,640,480)[0]
        self.assertGreater(changed['track_id'],result['track_id'])
        backwards=tracker.update([box(.2)],119,640,480)[0]
        self.assertGreater(backwards['track_id'],changed['track_id'])

    def test_image_distance_accounts_for_pixel_aspect_not_just_normalized_xy(self):
        self.assertAlmostEqual(distance((0,0),(.1,0),320,240),.08)
        self.assertAlmostEqual(distance((0,0),(0,.1),320,240),.06)


class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.settings=copy.deepcopy(DEFAULT)
        self.boxes=[box(.1,track_id=1),box(.17,track_id=2),box(.24,track_id=3)]

    def test_group_requires_minimum_size_and_continuous_wall_time(self):
        spatial=SpatialAnalysis()
        self.assertFalse(spatial.update(self.boxes,100,320,240,self.settings)['groups'][0]['persistent'])
        self.assertFalse(spatial.update(self.boxes,100.75,320,240,self.settings)['groups'][0]['persistent'])
        for i in range(1,21):
            result=spatial.update(self.boxes,100.75+i*.25,320,240,self.settings)
        self.assertTrue(result['groups'][0]['persistent'])
        self.assertEqual(spatial.update(self.boxes[:2],106,320,240,self.settings)['groups'],[])
        returned=spatial.update(self.boxes,106.25,320,240,self.settings)['groups'][0]
        self.assertEqual(returned['duration_seconds'],0)
        self.assertFalse(returned['persistent'])

    def test_group_duration_does_not_bridge_missing_time_or_changed_criteria(self):
        spatial=SpatialAnalysis()
        spatial.update(self.boxes,100,320,240,self.settings)
        result=spatial.update(self.boxes,110,320,240,self.settings)
        self.assertEqual(result['groups'][0]['duration_seconds'],0)
        changed=dict(self.settings,revision=1)
        result=spatial.update(self.boxes,110.25,320,240,changed)
        self.assertEqual(result['groups'][0]['duration_seconds'],0)

    def test_connected_chain_group_and_nearest_neighbors_have_explicit_relative_distance(self):
        spatial=SpatialAnalysis()
        settings=dict(self.settings,near_ratio=.06)
        result=spatial.update(self.boxes,100,320,240,settings)
        self.assertEqual(len(result['groups']),1)
        self.assertEqual(len(result['near_pairs']),2)
        self.assertEqual(len(result['nearest_neighbors']),3)
        self.assertAlmostEqual(result['nearest_neighbors'][0]['distance_ratio'],.056)

    def test_zones_count_centers_of_visible_confirmed_tracks_and_allow_overlap(self):
        settings=dict(self.settings,zones=[dict(id='feeder',x=.1,y=.2,width=.15,height=.3),dict(id='drinker',x=0,y=0,width=.3,height=1)])
        result=SpatialAnalysis().update(self.boxes,100,320,240,settings)
        self.assertEqual(result['zone_counts'][0]['ids'],[1,2])
        self.assertEqual(result['zone_counts'][1]['ids'],[1,2,3])
        self.boxes[0]['confirmed']=False
        result=SpatialAnalysis().update(self.boxes,100,320,240,settings)
        self.assertEqual(result['zone_counts'][0]['ids'],[2])
        self.assertEqual(result['groups'],[])


class ConfigurationTests(unittest.TestCase):
    def test_persistence_revision_conflict_and_failed_write_preserve_previous_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'vision.json'
            store=Configuration(path)
            payload=dict(store.get(),zones=[dict(id='heater',x=.2,y=.2,width=.3,height=.3)])
            saved=store.save(payload)
            self.assertEqual(Configuration(path).get(),saved)
            with self.assertRaises(Conflict): store.save(payload)
            before=path.read_text()
            with patch.object(Path,'replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): store.save(dict(saved,near_ratio=.15))
            self.assertEqual(store.get(),saved)
            self.assertEqual(path.read_text(),before)

    def test_corrupt_existing_file_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'vision.json';path.write_text('broken')
            store=Configuration(path)
            with self.assertRaises(ValueError): store.save(store.get())
            self.assertEqual(path.read_text(),'broken')

    def test_invalid_numbers_duplicate_zones_and_outside_rectangles_are_rejected(self):
        cases=[dict(DEFAULT,near_ratio=float('nan')),dict(DEFAULT,min_group_size=True),
            dict(DEFAULT,zones=[dict(id='feeder',x=.9,y=0,width=.5,height=.5)]),
            dict(DEFAULT,zones=[dict(id='feeder',x=0,y=0,width=.5,height=.5)]*2)]
        for payload in cases:
            with self.assertRaises(ValueError): validate(payload)
