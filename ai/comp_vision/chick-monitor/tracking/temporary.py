from collections import deque
import math
import uuid


def center(box):
    return box['x']+box['width']/2, box['y']+box['height']/2


def distance(a, b, width, height):
    return math.hypot((a[0]-b[0])*width, (a[1]-b[1])*height)/math.hypot(width, height)


def iou(a, b):
    intersection = max(0, min(a['x']+a['width'], b['x']+b['width'])-max(a['x'], b['x'])) * max(
        0, min(a['y']+a['height'], b['y']+b['height'])-max(a['y'], b['y']))
    return intersection/(a['width']*a['height']+b['width']*b['height']-intersection) if intersection else 0


class TemporaryTracker:
    """One-to-one geometric association with short retention; not biological identity."""
    max_lost = 1.0

    def __init__(self):
        self.session = uuid.uuid4().hex[:8]
        self.next_id = 1
        self.tracks = {}
        self.last_time = None
        self.geometry = None

    def clear(self):
        self.tracks.clear()
        self.last_time = None
        self.geometry = None

    def update(self, detections, timestamp, width, height):
        geometry = (width, height)
        if self.last_time is not None and (timestamp <= self.last_time or
                timestamp-self.last_time > self.max_lost or geometry != self.geometry):
            self.clear()
        self.last_time, self.geometry = timestamp, geometry
        self.tracks = {key: value for key, value in self.tracks.items() if timestamp-value['last'] <= self.max_lost}
        candidates = []
        for track_id, track in self.tracks.items():
            dt = timestamp-track['last']
            predicted = (track['center'][0]+track['velocity'][0]*dt,
                         track['center'][1]+track['velocity'][1]*dt)
            for index, box in enumerate(detections):
                ratio = box['width']*box['height']/(track['box']['width']*track['box']['height'])
                separation = distance(predicted, center(box), width, height)
                gate = min(0.22, 0.04+0.35*dt)
                if 0.3 <= ratio <= 3.3 and separation <= gate:
                    candidates.append((separation/gate+0.25*(1-iou(track['box'], box)), track_id, index))
        assigned, used = {}, set()
        for _, track_id, index in sorted(candidates):
            if index not in assigned and track_id not in used:
                assigned[index] = track_id
                used.add(track_id)
        output = []
        for index, box in enumerate(detections):
            point = center(box)
            track_id = assigned.get(index)
            if track_id is None:
                track_id = self.next_id
                self.next_id += 1
                track = dict(box=box, center=point, velocity=(0, 0), last=timestamp,
                             hits=0, consecutive=0, trail=deque(maxlen=24))
                self.tracks[track_id] = track
            else:
                track = self.tracks[track_id]
                dt = max(0.001, timestamp-track['last'])
                track['velocity'] = tuple((point[i]-track['center'][i])/dt for i in (0, 1))
                if dt > 0.75:
                    track['consecutive'] = 0
            track.update(box=box, center=point, last=timestamp, hits=track['hits']+1,
                         consecutive=track['consecutive']+1)
            track['trail'].append(dict(x=point[0], y=point[1], timestamp=timestamp))
            while track['trail'] and timestamp-track['trail'][0]['timestamp'] > 6:
                track['trail'].popleft()
            output.append(dict(box, track_id=track_id, confirmed=track['consecutive'] >= 2,
                               trail=list(track['trail'])))
        for track_id, track in self.tracks.items():
            if track['last'] != timestamp:
                track['consecutive'] = 0
        return output
