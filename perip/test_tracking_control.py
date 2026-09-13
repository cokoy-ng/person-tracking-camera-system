import unittest
from tracking_control import FaceServo


class FaceServoTests(unittest.TestCase):
    def test_detection_must_persist_before_moving(self):
        c = FaceServo()
        self.assertIsNone(c.update(1, 0))
        self.assertIsNone(c.update(1, .2))
        self.assertIsNone(c.update(None, .4))
        self.assertIsNone(c.update(1, .6))
        self.assertIsNone(c.update(1, .8))
        self.assertEqual(c.update(1, 1), 'SET 50')

    def test_rate_steps_and_bounds(self):
        c = FaceServo()
        previous = c.angle
        for i in range(300):
            command = c.update(2, i * .05)
            if command:
                self.assertLessEqual(c.angle - previous, 5)
                previous = c.angle
            self.assertLessEqual(c.angle, 90)
        self.assertEqual(c.angle, 90)

    def test_lost_face_stops_once_and_reacquires(self):
        c = FaceServo()
        for t in (0, .2, .4):
            c.update(.5, t)
        self.assertIsNone(c.update(None, .7))
        self.assertEqual(c.update(None, 1.5), 'STOP')
        self.assertIsNone(c.update(None, 2))
        for t in (2.2, 2.4):
            self.assertIsNone(c.update(.5, t))
        self.assertEqual(c.update(.5, 2.6), 'SET 45')

    def test_reverse_and_deadband(self):
        c = FaceServo(reverse=True)
        for t in (0, .2):
            c.update(1, t)
        self.assertEqual(c.update(1, .4), 'SET 40')
        self.assertIsNone(c.update(1, .41))
        self.assertIsNone(c.update(1 - 40 / 90, .6))

    def test_invalid_range(self):
        for limits in ((90, 0), (-1, 90), (0, 181)):
            with self.assertRaises(ValueError):
                FaceServo(*limits)


if __name__ == '__main__':
    unittest.main()
