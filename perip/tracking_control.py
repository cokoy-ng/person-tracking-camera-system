"""Decisiones del servo sin dependencias de cámara, IA o USB."""


class FaceServo:
    def __init__(self, minimum=0, maximum=90, reverse=False):
        if not 0 <= minimum < maximum <= 180:
            raise ValueError('Se requiere 0 <= mínimo < máximo <= 180')
        self.minimum, self.maximum, self.reverse = minimum, maximum, reverse
        self.angle = round((minimum + maximum) / 2)
        self.last_seen = None
        self.last_sent = float('-inf')
        self.streak = 0
        self.active = False

    def update(self, center, now):
        if center is None:
            self.streak = 0
            if self.active and now - self.last_seen >= 1.0:
                self.active = False
                return 'STOP'
            return None
        self.last_seen = now
        self.streak += 1
        if self.streak < 3 or now - self.last_sent < 0.15:
            return None
        center = max(0.0, min(1.0, center))
        if self.reverse:
            center = 1 - center
        target = round(self.minimum + center * (self.maximum - self.minimum))
        difference = target - self.angle
        if self.active and abs(difference) < 3:
            return None
        self.angle += max(-5, min(5, difference))
        self.angle = max(self.minimum, min(self.maximum, self.angle))
        self.last_sent, self.active = now, True
        return f'SET {self.angle}'
