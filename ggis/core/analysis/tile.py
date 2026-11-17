# -*- coding: utf-8 -*-

import hashlib
import math
import re

from ggis.core.crs.extent import GgsRectangle
import logging
_log = logging.getLogger("gmagis")

__all__ = ["GgsTileMatrix", "GgsTileSource", "BUILTIN_BASEMAPS",
           "basemap", "basemap_choices", "missing_placeholders",
           "WEBMERCATOR", "LONGLAT", "WORLD_HALF_WIDTH"]

WORLD_HALF_WIDTH = 20037508.342789244
_CIRCUMFERENCE = 2.0 * WORLD_HALF_WIDTH

LAT_LIMIT = 85.05112877980659

WEBMERCATOR = "EPSG:3857"
LONGLAT = "EPSG:4326"

DEFAULT_TILE_SIZE = 256

_PLACEHOLDERS = ("{z}", "{x}", "{y}")


def _norm_crs(text):
    return str(text or "").strip().upper().replace(" ", "")


_CRS_CODE_RE = re.compile(
    r"(EPSG\s*:\s*\d{3,6}|OGC\s*:\s*CRS84|CRS\s*:\s*84|CRS84)", re.I)


def _is_lonlat(crs_text):
    text = str(crs_text or "")
    m = _CRS_CODE_RE.search(text)
    if m is not None:
        text = m.group(1)
    try:
        from ggis.core.crs import GgsCoordinateReferenceSystem as _Crs
        obj = _Crs.from_user_input(text)
        if obj is not None and obj.is_valid():
            return bool(obj.is_geographic())
    except Exception:
        _log.exception("silent exception in _is_lonlat")
    t = _norm_crs(text)
    return ("4326" in t) or ("CRS:84" in t) or ("CRS84" in t) or ("4490" in t)


def _default_world(crs_text):
    if _is_lonlat(crs_text):
        return (-180.0, -90.0, 180.0, 90.0)
    return (-WORLD_HALF_WIDTH, -WORLD_HALF_WIDTH,
            WORLD_HALF_WIDTH, WORLD_HALF_WIDTH)


def _url_key(url):
    return hashlib.md5(str(url or "").encode("utf-8")).hexdigest()[:12]


def missing_placeholders(url):
    text = str(url or "")
    if not text:
        return _PLACEHOLDERS
    miss = []
    for p in _PLACEHOLDERS:
        if p == "{y}":
            if "{y}" not in text and "{-y}" not in text:
                miss.append(p)
            continue
        if p not in text:
            miss.append(p)
    return tuple(miss)


class GgsTileMatrix:

    __slots__ = ("crs", "tile_size", "_world")

    def __init__(self, crs=WEBMERCATOR, tile_size=DEFAULT_TILE_SIZE,
                 world=None):
        self.crs = str(crs or WEBMERCATOR)
        self.tile_size = max(1, int(tile_size or DEFAULT_TILE_SIZE))
        w = _default_world(self.crs) if world is None else world
        self._world = GgsRectangle(float(w[0]), float(w[1]),
                                   float(w[2]), float(w[3]))

    def world(self):
        return self._world.copy()

    def is_lonlat(self):
        return _is_lonlat(self.crs)

    def tile_count(self, z):
        z = max(0, int(z))
        return 1 << z

    def units_per_pixel(self, z):
        n = self.tile_count(z)
        return self._world.width() / float(self.tile_size * n)

    def zoom_for_resolution(self, resolution, min_zoom=0, max_zoom=24):
        try:
            res = float(resolution)
        except Exception:
            _log.exception("silent exception in zoom_for_resolution")
            return int(min_zoom or 0)
        if not (res > 0):
            return int(max_zoom or 0)
        n = self._world.width() / (float(self.tile_size) * res)
        if not (n > 0):
            return int(min_zoom or 0)
        z = int(math.floor(math.log2(n) + 0.5))
        lo = int(min_zoom or 0)
        hi = int(max_zoom or 0)
        if z < lo:
            z = lo
        if hi and z > hi:
            z = hi
        return z

    def unit_to_meters(self):
        if self.is_lonlat():
            return 111319.49079327358
        return 1.0

    def scale_denominator(self, z):
        upx = self.units_per_pixel(z)
        return upx * self.unit_to_meters() / 0.00028

    def zoom_for_scale(self, scale, min_zoom=0, max_zoom=24):
        try:
            s = float(scale)
        except Exception:
            _log.exception("silent exception in zoom_for_scale")
            return int(min_zoom or 0)
        if not (s > 0):
            return int(max_zoom or 0)
        return self.zoom_for_resolution(
            s * 0.00028 / max(1e-9, self.unit_to_meters()),
            min_zoom, max_zoom)

    def tile_bounds(self, z, x, y):
        n = self.tile_count(z)
        w = self._world
        span_x = w.width() / n
        span_y = w.height() / n
        xmin = w.xmin + int(x) * span_x
        ymax = w.ymax - int(y) * span_y
        return GgsRectangle(xmin, ymax - span_y, xmin + span_x, ymax)

    def tile_range(self, z, extent):
        n = self.tile_count(z)
        w = self._world
        if extent is None or extent.is_empty():
            return (0, 0, -1, -1)
        span_x = w.width() / n
        span_y = w.height() / n
        if not (span_x > 0 and span_y > 0):
            return (0, 0, -1, -1)

        def _clamp(v):
            return 0 if v < 0 else (n - 1 if v > n - 1 else v)

        x0 = _clamp(int(math.floor((extent.xmin - w.xmin) / span_x)))
        x1 = _clamp(int(math.floor((extent.xmax - w.xmin) / span_x)))
        y0 = _clamp(int(math.floor((w.ymax - extent.ymax) / span_y)))
        y1 = _clamp(int(math.floor((w.ymax - extent.ymin) / span_y)))
        return (x0, y0, x1, y1)

    def parent_of(self, z, x, y, parent_zoom):
        k = 1 << max(0, int(z) - int(parent_zoom))
        if k <= 1:
            return (int(x), int(y), 1, 0, 0)
        return (int(x) >> (z - parent_zoom), int(y) >> (z - parent_zoom),
                k, int(x) & (k - 1), int(y) & (k - 1))

    def __repr__(self):
        return "<GgsTileMatrix %s %dpx %r>" % (self.crs, self.tile_size,
                                               self._world)


class GgsTileSource:

    def __init__(self, url="", name="", title="", icon="xyz_tile",
                 subdomains=(), min_zoom=0, max_zoom=19,
                 crs=WEBMERCATOR, tile_size=DEFAULT_TILE_SIZE,
                 tms=False, attribution="", headers=None, key=""):
        self.url = str(url or "")
        self.name = str(name or "")
        self.title = str(title or name or "")
        self.icon = str(icon or "xyz_tile")
        self.subdomains = tuple(str(s) for s in (subdomains or ()))
        self.min_zoom = max(0, int(min_zoom or 0))
        self.max_zoom = max(0, int(max_zoom or 0))
        self.crs = str(crs or WEBMERCATOR)
        self.tile_size = max(1, int(tile_size or DEFAULT_TILE_SIZE))
        self.tms = bool(tms)
        self.attribution = str(attribution or "")
        self.headers = dict(headers or {})
        self.key = str(key or "") or _url_key(self.url)
        self._matrix = None

    def is_valid(self):
        if not self.url or missing_placeholders(self.url):
            return False
        if self.max_zoom and self.max_zoom < self.min_zoom:
            return False
        return True

    def matrix(self):
        if self._matrix is None:
            self._matrix = GgsTileMatrix(self.crs, self.tile_size)
        return self._matrix

    def clamp_zoom(self, z):
        z = int(z)
        if z < self.min_zoom:
            z = self.min_zoom
        if self.max_zoom and z > self.max_zoom:
            z = self.max_zoom
        return z

    def display_name(self):
        return self.title or self.name or self.key

    def subdomain_for(self, x, y):
        if not self.subdomains:
            return ""
        n = len(self.subdomains)
        return self.subdomains[(int(x) + int(y)) % n]

    def url_for(self, z, x, y):
        z = int(z)
        x = int(x)
        y = int(y)
        n = 1 << max(0, z)
        flip = n - 1 - y
        text = self.url
        text = text.replace("{-y}", str(flip))
        text = text.replace("{z}", str(z))
        text = text.replace("{x}", str(x))
        text = text.replace("{y}", str(n - 1 - y if self.tms else y))
        if "{s}" in text:
            text = text.replace("{s}", self.subdomain_for(x, y))
        return text

    def to_dict(self):
        d = {
            "url": self.url,
            "name": self.name,
            "title": self.title,
            "crs": self.crs,
            "tile_size": self.tile_size,
            "min_zoom": self.min_zoom,
            "max_zoom": self.max_zoom,
            "key": self.key,
        }
        if self.subdomains:
            d["subdomains"] = list(self.subdomains)
        if self.tms:
            d["tms"] = True
        if self.attribution:
            d["attribution"] = self.attribution
        if self.headers:
            d["headers"] = dict(self.headers)
        return d

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            return None
        try:
            return cls(
                url=d.get("url", ""), name=d.get("name", ""),
                title=d.get("title", ""),
                subdomains=d.get("subdomains") or (),
                min_zoom=d.get("min_zoom", 0), max_zoom=d.get("max_zoom", 19),
                crs=d.get("crs", WEBMERCATOR),
                tile_size=d.get("tile_size", DEFAULT_TILE_SIZE),
                tms=d.get("tms", False),
                attribution=d.get("attribution", ""),
                headers=d.get("headers") or {},
                key=d.get("key", ""))
        except Exception:
            _log.exception("silent exception in from_dict")
            return None

    def __repr__(self):
        return "<GgsTileSource %s %r>" % (self.key, self.url)


def _esri(service):
    return ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "%s/MapServer/tile/{z}/{y}/{x}" % service)


BUILTIN_BASEMAPS = (
    GgsTileSource(
        key="esri_imagery", title="Esri 影像", icon="map_satellite",
        url=_esri("World_Imagery"), max_zoom=19,
        attribution="Esri / Maxar / Earthstar Geographics"),
    GgsTileSource(
        key="esri_topo", title="Esri 地形图", icon="map_terrain",
        url=_esri("World_Topo_Map"), max_zoom=19,
        attribution="Esri"),
    GgsTileSource(
        key="esri_light", title="Esri 浅色地图", icon="map_light",
        url=_esri("Canvas/World_Light_Gray_Base"), max_zoom=16,
        attribution="Esri"),
    GgsTileSource(
        key="esri_dark", title="Esri 暗黑地图", icon="map_dark",
        url=_esri("Canvas/World_Dark_Gray_Base"), max_zoom=16,
        attribution="Esri"),
    GgsTileSource(
        key="osm_street", title="OSM 街道地图", icon="map_street",
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=19,
        attribution="© OpenStreetMap contributors"),
    GgsTileSource(
        key="otm_topo", title="OTM 等高线地形图", icon="map_topo",
        url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        subdomains=("a", "b", "c"), max_zoom=17,
        attribution="© OpenTopoMap (CC-BY-SA)"),
    GgsTileSource(
        key="amap_imagery", title="高德影像（有偏）", icon="map_satellite",
        url="https://webst0{s}.is.autonavi.com/appmaptile"
            "?style=6&x={x}&y={y}&z={z}",
        subdomains=("1", "2", "3", "4"), max_zoom=18,
        attribution="© 高德地图",
        headers={"Referer": "https://www.amap.com/"}),
    GgsTileSource(
        key="amap_street", title="高德街道（有偏）", icon="map_street",
        url="https://webrd0{s}.is.autonavi.com/appmaptile"
            "?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        subdomains=("1", "2", "3", "4"), max_zoom=18,
        attribution="© 高德地图",
        headers={"Referer": "https://www.amap.com/"}),
)

_BY_KEY = {s.key: s for s in BUILTIN_BASEMAPS}


def basemap(key):
    return _BY_KEY.get(str(key or ""))


def basemap_choices():
    return [(s.key, s) for s in BUILTIN_BASEMAPS]
