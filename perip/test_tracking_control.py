import unittest
from tracking_control import FaceServo, PresenceLight, select_target


class PresenceLightTests(unittest.TestCase):
    def test_presence_renews_lease_and_absence_does_not_cancel_sound(self):
        light = PresenceLight()
        self.assertIsNone(light.update(False, 0))
        self.assertEqual(light.update(True, .1), 'LIGHT PERSON')
        self.assertIsNone(light.update(True, .2))
        self.assertEqual(light.update(True, .7), 'LIGHT PERSON')
        self.assertEqual(light.update(False, 5), 'LIGHT PERSON')
        self.assertIsNone(light.update(False, 5.1))
        self.assertEqual(light.update(True, 6), 'LIGHT PERSON')

    def test_continuous_person_and_full_grace_after_disappearance(self):
        light = PresenceLight()
        sent = []
        for i in range(1201):
            now = i / 10
            if light.update(True, now):
                sent.append(now)
        self.assertGreater(len(sent), 200)
        self.assertLessEqual(max(b - a for a, b in zip(sent, sent[1:])), .6)
        self.assertEqual(light.update(False, 120.1), 'LIGHT PERSON')
        for now in (121, 140, 150.1, 180):
            self.assertIsNone(light.update(False, now))


class TargetTests(unittest.TestCase):
    def test_face_has_priority_over_larger_body(self):
        face = (10, 10, 40, 40)
        self.assertEqual(select_target([face], [(0, 0, 640, 480)]), (face, 'Rostro'))

    def test_body_moves_servo_without_a_face_then_loss_stops(self):
        target, kind = select_target([], [(0, 0, 10, 10), (400, 0, 640, 480)])
        self.assertEqual(kind, 'Persona')
        c = FaceServo()
        for t in (0, .2, .4):
            command = c.update((target[0] + target[2]) / 1280, t)
        self.assertEqual(command, 'SET 50')
        self.assertEqual(select_target([], []), (None, 'Sin objetivo'))
        self.assertEqual(c.update(None, 1.5), 'STOP')


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
