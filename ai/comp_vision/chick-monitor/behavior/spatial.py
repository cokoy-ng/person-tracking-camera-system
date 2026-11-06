from tracking.temporary import center, distance


class SpatialAnalysis:
    def __init__(self):
        self.previous = {}
        self.next_id = 1
        self.revision = None

    def clear(self):
        self.previous.clear()

    def update(self, tracks, timestamp, width, height, configuration):
        if configuration['revision'] != self.revision:
            self.clear()
            self.revision = configuration['revision']
        observed = {box['track_id']: box for box in tracks if box['confirmed']}
        graph = {key: set() for key in observed}
        pairs, nearest = [], {}
        keys = sorted(observed)
        for i, a in enumerate(keys):
            for b in keys[i+1:]:
                separation = distance(center(observed[a]), center(observed[b]), width, height)
                for node, neighbor in ((a, b), (b, a)):
                    if node not in nearest or separation < nearest[node]['distance_ratio']:
                        nearest[node] = dict(track_id=node, neighbor_id=neighbor, distance_ratio=round(separation, 5))
                if separation <= configuration['near_ratio']:
                    graph[a].add(b)
                    graph[b].add(a)
                    pairs.append(dict(a=a, b=b, distance_ratio=round(separation, 5)))
        components, visited = [], set()
        for key in keys:
            if key in visited:
                continue
            stack, component = [key], set()
            while stack:
                node = stack.pop()
                if node in component:
                    continue
                component.add(node)
                stack.extend(graph[node]-component)
            visited |= component
            if len(component) >= configuration['min_group_size']:
                components.append(component)
        used, current, groups = set(), {}, []
        for component in sorted(components, key=lambda c: (-len(c), min(c))):
            candidates = []
            for key, old in self.previous.items():
                overlap = len(component & old['ids'])/len(component | old['ids'])
                if key not in used and 0 < timestamp-old['last'] <= 1 and overlap >= 0.5:
                    candidates.append((-overlap, key))
            if candidates:
                group_id = min(candidates)[1]
                started = self.previous[group_id]['started']
            else:
                group_id = self.next_id
                self.next_id += 1
                started = timestamp
            used.add(group_id)
            current[group_id] = dict(ids=component, started=started, last=timestamp)
            members = [observed[key] for key in component]
            x, y = min(b['x'] for b in members), min(b['y'] for b in members)
            right, bottom = max(b['x']+b['width'] for b in members), max(b['y']+b['height'] for b in members)
            duration = timestamp-started
            groups.append(dict(id=group_id, ids=sorted(component), count=len(component),
                duration_seconds=round(duration, 1), persistent=duration >= configuration['persistence_seconds'],
                x=x, y=y, width=right-x, height=bottom-y))
        self.previous = current
        zones = []
        for zone in configuration['zones']:
            ids = []
            for key, box in observed.items():
                cx, cy = center(box)
                if zone['x'] <= cx < zone['x']+zone['width'] and zone['y'] <= cy < zone['y']+zone['height']:
                    ids.append(key)
            zones.append(dict(id=zone['id'], count=len(ids), ids=sorted(ids)))
        return dict(groups=groups, near_pairs=sorted(pairs, key=lambda p: p['distance_ratio'])[:200],
                    nearest_neighbors=list(nearest.values()), zone_counts=zones, confirmed_count=len(observed))
