# -*- coding: utf-8 -*-

from __future__ import annotations

from ggis.core.app import settings as _settings
import logging
_log = logging.getLogger("gmagis")

RAMP_PREFIX = "user:"

_KEY = "user_ramps"

KIND_CONTINUOUS = "continuous"
KIND_DISCRETE = "discrete"

_DISCRETE_EPS = 1e-4


def is_user(code):
    return str(code or "").startswith(RAMP_PREFIX)


def _load():
    try:
        data = _settings.get_disk(_KEY, {}) or {}
    except Exception:
        _log.exception("silent exception in _load")
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for code, ent in data.items():
        if not isinstance(ent, dict):
            continue
        stops = []
        for pair in (ent.get("stops") or []):
            try:
                pos, col = float(pair[0]), str(pair[1])
            except Exception:
                _log.exception("silent exception in _load")
                continue
            stops.append((max(0.0, min(1.0, pos)), col))
        if len(stops) < 2:
            continue
        stops.sort(key=lambda t: t[0])
        kind = str(ent.get("kind") or "")
        out[str(code)] = {
            "name": str(ent.get("name") or ""),
            "stops": stops,
            "kind": (KIND_DISCRETE if kind == KIND_DISCRETE
                     else KIND_CONTINUOUS),
        }
    return out


def _store(data):
    try:
        _settings.set(_KEY, data, persist=True)
    except Exception:
        _log.exception("silent exception in _store")


def _code_for(name):
    return RAMP_PREFIX + str(name or "").strip()


def entries():
    out = []
    for code, ent in _load().items():
        out.append((code, ent.get("name") or code[len(RAMP_PREFIX):],
                    list(ent.get("stops") or [])))
    out.sort(key=lambda t: t[1])
    return out


def label_of(code):
    ent = _load().get(str(code or ""))
    if ent is None:
        return ""
    return ent.get("name") or str(code)[len(RAMP_PREFIX):]


def kind_of(code):
    ent = _load().get(str(code or ""))
    if not ent:
        return KIND_CONTINUOUS
    return ent.get("kind") or KIND_CONTINUOUS


def stops_of(code):
    ent = _load().get(str(code or ""))
    return list(ent.get("stops") or []) if ent else []


def control_points(code):
    stops = stops_of(code)
    if len(stops) < 2:
        return None
    if kind_of(code) == KIND_DISCRETE:
        stops = _steps(stops)
    out = []
    for pos, col in stops:
        try:
            c = _hex_rgb(col)
        except Exception:
            _log.exception("silent exception in control_points")
            return None
        out.append((float(pos), c))
    return tuple(out)


def hex_stops(code, n=32):
    stops = stops_of(code)
    if len(stops) < 2:
        return []
    if kind_of(code) == KIND_DISCRETE:
        out = []
        for i in range(n):
            t = i / max(1, n - 1)
            out.append("#%02X%02X%02X" % _step_color(stops, t))
        return out
    pts = control_points(code)
    if not pts:
        return []
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        r, g, b = _sample(pts, t)
        out.append("#%02X%02X%02X" % (r, g, b))
    return out


def band_edges(stops):
    xs = [float(p) for p, _c in stops]
    if len(xs) < 2:
        return [0.0, 1.0]
    edges = [0.0]
    for i in range(len(xs) - 1):
        edges.append((xs[i] + xs[i + 1]) / 2.0)
    edges.append(1.0)
    return edges


def _steps(stops):
    edges = band_edges(stops)
    n = len(edges)
    out = []
    for i, (_pos, col) in enumerate(stops):
        x0 = float(edges[i])
        x1 = float(edges[min(i + 1, n - 1)])
        out.append((x0, col))
        if x1 > x0:
            out.append((max(x0, x1 - _DISCRETE_EPS), col))
    if out and out[-1][0] < 1.0:
        out.append((1.0, out[-1][1]))
    return out


def _step_color(stops, t):
    edges = band_edges(stops)
    t = min(1.0, max(0.0, float(t)))
    n = len(stops)
    for i in range(n):
        if t < edges[i + 1] or i == n - 1:
            return _hex_rgb(stops[i][1])
    return _hex_rgb(stops[-1][1])


def save(name, stops, kind=KIND_CONTINUOUS):
    name = str(name or "").strip()
    clean = []
    for pair in (stops or []):
        try:
            pos = max(0.0, min(1.0, float(pair[0])))
            col = str(pair[1])
            _hex_rgb(col)
        except Exception:
            _log.exception("silent exception in save")
            continue
        clean.append((pos, col.upper() if col.startswith("#") else col))
    if not name or len(clean) < 2:
        return ""
    clean.sort(key=lambda t: t[0])
    uniq = []
    for pos, col in clean:
        if uniq and abs(pos - uniq[-1][0]) < 1e-6:
            uniq[-1] = (pos, col)
        else:
            uniq.append((pos, col))
    if len(uniq) < 2:
        return ""
    code = _code_for(name)
    data = _load()
    data[code] = {
        "name": name,
        "kind": (KIND_DISCRETE if str(kind or "") == KIND_DISCRETE
                 else KIND_CONTINUOUS),
        "stops": [[p, c] for p, c in uniq],
    }
    _store(data)
    return code


def remove(code):
    code = str(code or "")
    data = _load()
    if code in data:
        data.pop(code)
        _store(data)
        return True
    return False


def clear():
    _store({})


def _hex_rgb(col):
    s = str(col).lstrip("#")
    if len(s) == 8:
        s = s[2:]
    if len(s) != 6:
        raise ValueError("bad hex: %r" % (col,))
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _sample(pts, t):
    t = min(1.0, max(0.0, float(t)))
    prev = pts[0]
    for pos, col in pts:
        if t <= pos:
            if pos <= prev[0]:
                return tuple(int(v) for v in col)
            k = (t - prev[0]) / (pos - prev[0])
            return tuple(int(round(prev[1][i] + (col[i] - prev[1][i]) * k))
                         for i in range(3))
        prev = (pos, col)
    return tuple(int(v) for v in pts[-1][1])
