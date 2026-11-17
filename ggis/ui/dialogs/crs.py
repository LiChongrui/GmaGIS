# -*- coding: utf-8 -*-

from __future__ import annotations

import os

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
                               QDialogButtonBox,
                               QFormLayout,
                               QFrame,
                               QGridLayout,
                               QHBoxLayout,
                               QLabel,
                               QLineEdit,
                               QMenu,
                               QScrollArea,
                               QSizePolicy,
                               QTreeWidgetItem,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n
from ggis.core.crs import proj_methods as _pm
from ggis.core.app import settings as _settings
from ggis.core.model.project import GgsProject
from ...core.crs import (GgsCoordinateReferenceSystem as GgsCrs,
                        crs_proj_string)
from ggis.common.styling import themes
from ggis.core.crs.world_outline import draw_extent, draw_world
from ggis.common.widgets.itemviews import GgsTreeWidget
from ggis.common.widgets.buttons import GgsSmallMenuButtonStyle1
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.base.dialog import GgsDialog, GgsMsgBox
from ggis.common.widgets.displays import GgsDimLabel
from ggis.common.widgets.inputs import GgsSearchEdit
from ggis.common.widgets.separators import GgsGroupCard
from ggis.ui.dialogs.about import GgsAboutCard
from ggis.ui.dialogs.about import GgsAboutCardTitle
from ggis.ui.dialogs.about import GgsAboutKey
from ggis.ui.dialogs.about import GgsAboutNote
from ggis.ui.dialogs.about import GgsAboutVal
import logging
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QPlainTextEdit
_log = logging.getLogger("gmagis")

_tr = i18n.tr

MAX_SEARCH = 400
MAX_GROUP = 2000

_MRU_KEY = "crs/recent"
_MRU_MAX = 8
_CUSTOM_KEY = "crs/custom"
_CUSTOM_MAX = 40

_ENTRIES = None
_INDEX = None

_METHOD_RULES = (
    ("横轴墨卡托 / 高斯-克吕格", ("transverse mercator",)),
    ("斜轴墨卡托", ("hotine oblique mercator", "oblique mercator")),
    ("伪墨卡托（Web 墨卡托）", ("pseudo mercator", "popular visualisation")),
    ("墨卡托", ("mercator",)),
    ("兰勃特等角圆锥", ("lambert conic conformal",)),
    ("兰勃特等积方位", ("lambert azimuthal",)),
    ("阿尔伯斯等积", ("albers",)),
    ("极地立体投影", ("polar stereographic",)),
    ("斜轴立体投影", ("stereographic",)),
    ("方位等距", ("azimuthal equidistant",)),
    ("卡西尼-索尔德纳", ("cassini",)),
    ("多圆锥", ("polyconic",)),
    ("克罗瓦克", ("krovak",)),
    ("摩尔魏特等积", ("mollweide",)),
    ("圆柱等积", ("cylindrical equal area", "equal area cylindrical")),
    ("哥伦比亚城市网格", ("colombia urban",)),
    ("等距圆柱", ("equidistant cylindrical", "plate carree")),
    ("世界与伪圆柱投影", ("eckert", "wagner", "winkel", "aitoff", "loximuthal",
                          "ortelius", "grinten", "fahey", "foucaut",
                          "ginsburg", "urmaev", "lagrange", "larriv",
                          "healpix", "hammer", "robinson", "times", "natural earth")),
)

_GEO_GROUPS = (
    ("WGS 84", ("wgs 84", "wgs84", "world geodetic system 1984")),
    ("CGCS2000", ("cgcs2000", "china geodetic coordinate system 2000")),
    ("北京 1954", ("beijing 1954",)),
    ("西安 1980", ("xian 1980",)),
    ("NAD83", ("nad83",)),
    ("NAD27", ("nad27",)),
    ("ETRS89", ("etrs89",)),
    ("ED50", ("ed50", "european datum 1950")),
    ("GDA94 / GDA2020", ("gda94", "gda2020")),
    ("日本 JGD", ("jgd2000", "jgd2011", "japan geodetic")),
)

_GEO_OTHER = "其他基准"


def geo_group(name):
    n = str(name or "").lower()
    for label, keys in _GEO_GROUPS:
        for k in keys:
            if k in n:
                return label
    return _GEO_OTHER


_KIND = Qt.ItemDataRole.UserRole + 1
_PAYLOAD = Qt.ItemDataRole.UserRole + 2
_FILLED = Qt.ItemDataRole.UserRole + 3
_AUTHID = Qt.ItemDataRole.UserRole
_ICON = Qt.ItemDataRole.UserRole + 4


def crs_entries():
    global _ENTRIES
    if _ENTRIES is not None:
        return _ENTRIES
    out = []
    try:
        from pyproj import database as _db
        from pyproj.enums import PJType
        for info in _db.query_crs_info(auth_name="EPSG"):
            try:
                authid = "%s:%s" % (info.auth_name, info.code)
                name = str(info.name or "")
                is_proj = (getattr(info, "type") == PJType.PROJECTED_CRS)
                method = str(getattr(info, "projection_method_name", "")
                             or "") if is_proj else ""
                area = None
                aou = getattr(info, "area_of_use", None)
                if aou is not None:
                    try:
                        area = (str(aou.name or ""), float(aou.west),
                                float(aou.south), float(aou.east),
                                float(aou.north))
                    except Exception:
                        _log.exception("silent exception in crs_entries")
                        area = None
            except Exception:
                _log.exception("silent exception in crs_entries")
                continue
            out.append((authid, name, is_proj, method, area))
    except Exception:
        _log.exception("silent exception in crs_entries")
        out = []

    def _code(t):
        try:
            return int(str(t[0]).split(":")[1])
        except Exception:
            _log.exception("silent exception in _code")
            return 0

    out.sort(key=_code)
    _ENTRIES = out
    return out


def crs_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = {e[0]: e for e in crs_entries()}
    return _INDEX


def method_group(method):
    m = str(method or "").lower()
    for label, keys in _METHOD_RULES:
        for k in keys:
            if k in m:
                return label
    return "其他投影方法"


def recent_crs():
    r = _settings.get(_MRU_KEY)
    if isinstance(r, (list, tuple)):
        return [str(x) for x in r if x][:_MRU_MAX]
    return []


def push_recent(authid):
    a = str(authid or "").strip()
    if not a:
        return recent_crs()
    r = [x for x in recent_crs() if x != a]
    r.insert(0, a)
    r = r[:_MRU_MAX]
    try:
        _settings.set(_MRU_KEY, r)
    except Exception:
        _log.exception("silent exception in push_recent")
    return r


def custom_crs():
    raw = _settings.get(_CUSTOM_KEY)
    out = []
    if isinstance(raw, (list, tuple)):
        for e in raw:
            if not isinstance(e, dict):
                continue
            wkt = str(e.get("wkt") or "")
            if not wkt:
                continue
            out.append((str(e.get("name") or ""), wkt))
    return out[:_CUSTOM_MAX]


def push_custom(name, wkt):
    n = str(name or "").strip()
    w = str(wkt or "").strip()
    if not w:
        return custom_crs()
    rest = [e for e in _settings.get(_CUSTOM_KEY) or []
            if isinstance(e, dict) and str(e.get("name") or "") != n]
    rest.insert(0, {"name": n, "wkt": w})
    try:
        _settings.set(_CUSTOM_KEY, rest[:_CUSTOM_MAX])
    except Exception:
        _log.exception("silent exception in push_custom")
    return custom_crs()


def remove_recent(authid):
    a = str(authid or "").strip()
    if not a:
        return recent_crs()
    r = [x for x in recent_crs() if x != a]
    try:
        _settings.set(_MRU_KEY, r)
    except Exception:
        _log.exception("silent exception in remove_recent")
    return r


def remove_custom(wkt):
    w = str(wkt or "").strip()
    if not w:
        return custom_crs()
    rest = [e for e in _settings.get(_CUSTOM_KEY) or []
            if isinstance(e, dict) and str(e.get("wkt") or "").strip() != w]
    try:
        _settings.set(_CUSTOM_KEY, rest[:_CUSTOM_MAX])
    except Exception:
        _log.exception("silent exception in remove_custom")
    return custom_crs()


def _crs_prefill(entry):
    authid, name, projected, _method, _area = entry
    try:
        cust = {w for _n, w in custom_crs()}
        c = (custom_crs_object(authid) if authid in cust
             else GgsCrs.from_user_input(authid))
        if c is None or not c.is_valid():
            return None
        s = crs_proj_string(c) or ""
        d = {}
        for tok in s.split():
            if tok.startswith("+") and "=" in tok:
                k, v = tok[1:].split("=", 1)
                d[k.strip().lower()] = v.strip()
        if not d:
            return None
    except Exception:
        _log.exception("silent exception in _crs_prefill")
        return None
    kind = "proj" if projected else "geo"
    out = {"name": str(name or ""), "kind": kind, "params": {}}
    dtok = ""
    for _label, token in _DATUMS:
        kk, vv = token[1:].split("=", 1)
        if str(d.get(kk, "")).lower() == vv.lower():
            dtok = token
            break
    if dtok:
        out["datum"] = dtok
    else:
        try:
            a = float(d.get("a", ""))
            rf = float(d.get("rf", ""))
            if a > 0 and rf > 0:
                out["datum"] = "__custom__"
                out["ellps"] = (a, rf)
            else:
                raise ValueError
        except Exception:
            _log.exception("silent exception in _crs_prefill")
            out["datum"] = _DATUMS[0][1]
    pm = str(d.get("pm", "")).strip()
    ptok = ""
    if pm:
        try:
            out["pm_value"] = float(pm)
            ptok = "__custom__"
        except Exception:
            _log.exception("silent exception in _crs_prefill")
            for _label, token in _PRIME_MERIDIANS:
                if token and token != "__custom__" \
                        and token.lower() == pm.lower():
                    ptok = token
                    break
    out["pm"] = ptok
    un = str(d.get("units", "")).strip().lower()
    if kind == "geo":
        out["ang"] = "+units=radians" if un == "radians" else ""
    else:
        out["len"] = un if un in {t for _l, t in _LEN_UNITS} else "m"
    if kind == "proj":
        mk = str(d.get("proj", "")).lower()
        if mk not in {_k for _k, _l, _p in _pm.PROJ_METHODS}:
            mk = "tmerc"
        out["method"] = mk
        pd = {}
        for pname, _default in _method_defaults(mk):
            if pname in d:
                try:
                    pd[pname] = float(d[pname])
                except Exception:
                    _log.exception("silent exception in _crs_prefill")
                    continue
        out["params"] = pd
    return out


def _crs_geo_rows(pj, projected):
    rows = []
    gcs = pj
    try:
        _gc = pj.geodetic_crs
        if _gc is not None:
            gcs = _gc
    except Exception:
        _log.exception("silent exception in _crs_geo_rows")
    try:
        axes = getattr(gcs, "axis_info", None)
        if axes:
            ax = axes[0]
            un = str(getattr(ax, "unit_name", "") or "")
            fac = getattr(ax, "unit_conversion_factor", None)
            if un == "degree":
                un = _tr("度")
            if un and fac is not None:
                rows.append((_tr("角度单位"),
                             "%s（%.12g）" % (un, float(fac))))
            elif un:
                rows.append((_tr("角度单位"), un))
    except Exception:
        _log.exception("silent exception in _crs_geo_rows")
    for label, obj in ((_tr("基准面"), getattr(pj, "datum", None)),
                       (_tr("椭球体"), getattr(pj, "ellipsoid", None))):
        try:
            val = str(getattr(obj, "name", "") or "")
        except Exception:
            _log.exception("silent exception in _crs_geo_rows")
            val = ""
        if val:
            rows.append((label, val))
    el = getattr(pj, "ellipsoid", None)
    if el is not None:
        try:
            a = getattr(el, "semi_major_metre", None)
            b = getattr(el, "semi_minor_metre", None)
            inv = getattr(el, "inverse_flattening", None)
            if a is not None and b is not None:
                rows.append((_tr("长短半轴"),
                             "%.4f / %.4f m" % (float(a), float(b))))
            if inv is not None:
                rows.append((_tr("反扁率"), "%.6f" % float(inv)))
        except Exception:
            _log.exception("silent exception in _crs_geo_rows")
    pm = getattr(pj, "prime_meridian", None)
    if pm is not None:
        try:
            nm = str(getattr(pm, "name", "") or "")
            lon = float(getattr(pm, "longitude", 0.0))
            rows.append((_tr("本初子午线"),
                         ("%s（%.4f°）" % (nm, lon)) if nm
                         else "%.4f°" % lon))
        except Exception:
            _log.exception("silent exception in _crs_geo_rows")
    if projected:
        try:
            op = getattr(pj, "coordinate_operation", None)
            params = (list(getattr(op, "params", None) or [])
                      if op is not None else [])
            if params:
                from .app import _CRS_PARAM_ZH, _crs_param_text
                for p in params:
                    try:
                        pn = str(getattr(p, "name", "") or "")
                        pv = getattr(p, "value", None)
                    except Exception:
                        _log.exception("silent exception in _crs_geo_rows")
                        continue
                    if not pn or pv is None:
                        continue
                    rows.append((_tr(_CRS_PARAM_ZH.get(pn, pn)),
                                 _crs_param_text(pv, p)))
        except Exception:
            _log.exception("silent exception in _crs_geo_rows")
    return rows


_CUSTOM_OBJ_CACHE = {}

_CUSTOM_ENTRIES = None
_CUSTOM_SIG = None


def custom_crs_object(wkt):
    key = str(wkt or "")
    hit = _CUSTOM_OBJ_CACHE.get(key)
    if hit is not None:
        return hit
    c = None
    try:
        c = GgsCrs.from_user_input(key)
    except Exception:
        _log.exception("silent exception in custom_crs_object")
        c = None
    if c is None or not c.is_valid():
        try:
            c2 = GgsCrs.from_wkt(key)
            if c2 is not None and c2.is_valid():
                c = c2
        except Exception:
            _log.exception("silent exception in custom_crs_object")
    out = c if (c is not None and c.is_valid()) else GgsCrs()
    if len(_CUSTOM_OBJ_CACHE) >= 64:
        _CUSTOM_OBJ_CACHE.clear()
    _CUSTOM_OBJ_CACHE[key] = out
    return out


def _entry_label(authid, name):
    a = str(authid or "")
    n = str(name or "")
    if a and len(a) <= 24 and ":" in a and " " not in a:
        return ("%s - %s" % (a, n)) if n else a
    return n or a


def _fmt_deg(v):
    try:
        return "%.2f°" % float(v)
    except Exception:
        _log.exception("silent exception in _fmt_deg")
        return str(v)


def _blend(c1, c2, t):
    t = max(0.0, min(1.0, float(t)))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t))




class _CrsMapPreview(QWidget):

    RATIO = 2.0
    MIN_H = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsCrsPreview")
        self.setMinimumWidth(240)
        self._area = None
        self._valid = False
        self._sync_ratio()

    def heightForWidth(self, w):
        return max(self.MIN_H, int(round(float(w) / self.RATIO)))

    def hasHeightForWidth(self):
        return True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_ratio()

    def _sync_ratio(self):
        try:
            h = self.heightForWidth(self.width())
            if abs(self.height() - h) > 1:
                self.setFixedHeight(h)
        except Exception:
            _log.exception("silent exception in _sync_ratio")

    def set_area(self, area, valid=True):
        self._area = area
        self._valid = bool(valid)
        self.update()

    def paintEvent(self, event):
        try:
            pal = themes.theme_colors(_settings.get("theme"))
        except Exception:
            _log.exception("silent exception in paintEvent")
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        if r.width() <= 2 or r.height() <= 2:
            p.end()
            return

        window = QColor(pal.get("window") or "#f3f4f7")
        panel = QColor(pal.get("panel") or "#ffffff")
        text = QColor(pal.get("text") or "#202020")
        border = QColor(pal.get("border") or "#c9cdd4")
        soft = QColor(pal.get("border_soft") or "#e3e5e8")
        accent = QColor(pal.get("accent") or "#0078d4")

        dark = panel.lightness() < 128
        ocean = _blend(window, accent, 0.10 if dark else 0.18)
        land = _blend(panel, text, 0.14 if dark else 0.0)

        if r.width() > r.height() * self.RATIO:
            w = r.height() * self.RATIO
            inner = QRectF(r.left() + (r.width() - w) / 2.0, r.top(),
                           w, r.height())
        else:
            h = r.width() / self.RATIO
            inner = QRectF(r.left(), r.top() + (r.height() - h) / 2.0,
                           r.width(), h)

        p.fillRect(r, window)
        p.fillRect(inner, ocean)
        grid = QColor(soft)
        grid.setAlpha(70)
        emph = QColor(border)
        emph.setAlpha(150)
        box = inner.adjusted(0.5, 0.5, -0.5, -0.5)
        draw_world(p, box, land, border, grid, 15,
                   sea_brush=ocean, emph_pen=emph)

        if self._area is not None:
            _desc, w, s, e, n = self._area
            min_deg = 9.0 * 360.0 / max(1.0, box.width())
            fill = QColor(accent)
            fill.setAlpha(70)
            pen = QPen(accent)
            pen.setWidthF(1.6)
            draw_extent(p, box, w, s, e, n, fill, pen, min_span=min_deg)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(border)
        p.drawRect(inner)
        p.end()


_DATUMS = (
    ("WGS 84", "+datum=WGS84"),
    ("CGCS2000（GRS80 椭球）", "+ellps=GRS80"),
    ("西安 1980（IAG-75 椭球）", "+ellps=IAU76"),
    ("北京 1954（克拉索夫斯基椭球）", "+ellps=krass"),
)

_PRIME_MERIDIANS = (
    ("格林尼治（0°）", ""),
    ("巴黎（2.3372°E）", "paris"),
    ("雅典（23.4259°E）", "athens"),
    ("伯尔尼（7.2623°E）", "bern"),
    ("波哥大（74.0451°W）", "bogota"),
    ("布鲁塞尔（4.2205°E）", "brussels"),
    ("哥本哈根（12.3440°E）", "copenhagen"),
    ("费罗（17.4°W）", "ferro"),
    ("雅加达（106.4828°E）", "jakarta"),
    ("里斯本（9.0755°W）", "lisbon"),
    ("马德里（3.4115°W）", "madrid"),
    ("奥斯陆（10.4323°E）", "oslo"),
    ("罗马（12.4523°E）", "rome"),
    ("斯德哥尔摩（18.0583°E）", "stockholm"),
    ("自定义经度…", "__custom__"),
)


def _row_host(widget):
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(widget)
    lay.addStretch(1)
    return host


_ANG_UNITS = (
    ("度", ""),
    ("弧度", "+units=radians"),
)

_LEN_UNITS = (
    ("米", "m"),
    ("千米", "km"),
    ("英尺", "ft"),
    ("美制英尺", "us-ft"),
)

_PARAM_INFO = {
    "lat_0": ("原点纬度", "°", -90.0, 90.0, 6, 0.0),
    "lon_0": ("中央经线", "°", -180.0, 180.0, 6, 0.0),
    "lat_1": ("第一标准纬线", "°", -90.0, 90.0, 6, 0.0),
    "lat_2": ("第二标准纬线", "°", -90.0, 90.0, 6, 0.0),
    "lat_ts": ("真比例纬线", "°", -90.0, 90.0, 6, 0.0),
    "lon_1": ("第一点经度", "°", -180.0, 180.0, 6, 0.0),
    "lon_2": ("第二点经度", "°", -180.0, 180.0, 6, 0.0),
    "lonc": ("斜轴中心经线", "°", -180.0, 180.0, 6, 0.0),
    "alpha": ("斜轴方位角", "°", -360.0, 360.0, 6, 0.0),
    "gamma": ("斜轴偏转角", "°", -360.0, 360.0, 6, 0.0),
    "azi": ("方位角", "°", -360.0, 360.0, 6, 0.0),
    "k": ("比例因子", "", 0.0001, 100.0, 8, 0.0),
    "x_0": ("东偏移（假东）", "m", -100000000.0, 100000000.0, 4, 0.0),
    "y_0": ("北偏移（假北）", "m", -100000000.0, 100000000.0, 4, 0.0),
    "zone": ("UTM 带号（1–60）", "", 1.0, 60.0, 0, 1.0),
    "tilt": ("倾斜角", "°", -90.0, 90.0, 6, 0.0),
    "n": ("n 参数", "", -10.0, 10.0, 6, 0.0),
    "m": ("m 参数", "", -10.0, 10.0, 6, 0.0),
    "q": ("q 参数", "", -10.0, 10.0, 6, 0.0),
    "path": ("路径号", "", -100.0, 100.0, 0, 1.0),
    "h": ("卫星高度", "m", 1000.0, 100000000.0, 2, 0.0),
}

_METHODS = tuple(
    (label, key, _pm.method_defaults(key))
    for key, label, _pset in _pm.PROJ_METHODS
)


_WEBMERCATOR = ("+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 "
                "+y_0=0 +k=1 +units=m +nadgrids=@null")


def build_proj4(kind, datum_token, method_key, params, len_unit, ang_token,
                pm_token="", ellps_token=""):
    d = str(datum_token or "")
    if d == "__custom__":
        d = ""
    pm = str(pm_token or "")
    el = str(ellps_token or "")
    if kind == "geo":
        ell = el.split() if el else ([d] if d else [])
        return (" ".join(p for p in ("+proj=longlat", *ell, pm,
                                     str(ang_token or ""), "+no_defs")
                         if p.strip()).strip())
    if method_key == "webmerc":
        return _WEBMERCATOR
    parts = ["+proj=%s" % str(method_key or "tmerc")]
    for name, _default in _method_defaults(method_key):
        try:
            v = float(params.get(name, _default))
        except Exception:
            _log.exception("silent exception in build_proj4")
            v = float(_default)
        parts.append("+%s=%s" % (name, ("%.10g" % v)))
    if el:
        parts.extend(el.split())
    elif d:
        parts.append(d)
    if pm:
        parts.append(pm)
    parts.append("+units=%s" % str(len_unit or "m"))
    parts.append("+no_defs")
    return " ".join(p for p in parts if p.strip())


def _method_defaults(method_key):
    for _label, key, defaults in _METHODS:
        if key == method_key:
            return defaults
    return _METHODS[0][2]


def crs_from_proj4(proj4, name):
    n = str(name or "").strip() or _tr("自定义坐标系")
    try:
        import pyproj
        p = pyproj.CRS.from_proj4(str(proj4))
        wkt = p.to_wkt(version="WKT1_GDAL")
        wkt = wkt.replace('"unknown"', '"%s"' % n.replace('"', ""), 1)
        c = GgsCrs.from_wkt(wkt)
        if c is not None and c.is_valid():
            return c, wkt
    except Exception:
        _log.exception("silent exception in crs_from_proj4")
    try:
        c2 = GgsCrs.from_proj(str(proj4))
        if c2 is not None and c2.is_valid():
            return c2, str(proj4)
    except Exception:
        _log.exception("silent exception in crs_from_proj4")
    return GgsCrs(), ""


def crs_from_text(text, name):
    t = str(text or "").strip()
    if not t:
        return GgsCrs(), ""
    n = str(name or "").strip()
    try:
        import pyproj
        p = pyproj.CRS.from_user_input(t)
        wkt = p.to_wkt(version="WKT1_GDAL")
        if n:
            import re
            wkt = re.sub(r'"[^"]*"', '"%s"' % n.replace('"', ""), wkt, count=1)
        c = GgsCrs.from_wkt(wkt)
        if c is not None and c.is_valid():
            return c, wkt
    except Exception:
        _log.exception("silent exception in crs_from_text")
    try:
        c2 = GgsCrs.from_user_input(t)
        if c2 is not None and c2.is_valid():
            return c2, t
    except Exception:
        _log.exception("silent exception in crs_from_text")
    return GgsCrs(), ""


class _CrsFromStringDialog(GgsDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsCrsFromStringDialog")
        self.setWindowTitle(_tr("从字符串新建坐标系"))
        try:
            from ggis.common.styling import icons as _icons
            self.setWindowIcon(_icons.icon("input_file", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        self.setMinimumWidth(540)
        self._name = ""
        self._wkt = ""
        self._crs = GgsCrs()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        self.ed_name = GgsNewCrsName()
        self.ed_name.setPlaceholderText("")
        form.addRow(_tr("名称"), self.ed_name)
        root.addLayout(form)

        self.ed_text = GgsCrsWkt()
        self.ed_text.setPlaceholderText(
            "")
        self.ed_text.setMinimumHeight(120)
        root.addWidget(self.ed_text, 1)


        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._on_ok)
        box.rejected.connect(self.reject)
        try:
            from ggis.common.styling import icons as _icons
            bok = box.button(QDialogButtonBox.StandardButton.Ok)
            if bok is not None:
                bok.setIcon(_icons.icon("confirm", size=16))
            bc = box.button(QDialogButtonBox.StandardButton.Cancel)
            if bc is not None:
                bc.setIcon(_icons.icon("clear", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        root.addWidget(box)

    def _on_ok(self):
        text = self.ed_text.toPlainText() or ""
        crs, wkt = crs_from_text(text, self.ed_name.text())
        if not crs.is_valid() or not wkt:
            GgsMsgBox.warn(self, _tr("字符串无法解析"),
                           _tr("无法识别"))
            return
        name = (self.ed_name.text() or "").strip() or crs.description() \
            or _tr("自定义坐标系")
        self._name, self._wkt, self._crs = name, wkt, crs
        self.accept()

    def result_name(self):
        return self._name

    def result_wkt(self):
        return self._wkt

    def result_crs(self):
        return self._crs


class _NewCrsDialog(GgsDialog):

    def __init__(self, parent=None, kind="proj", prefill=None):
        super().__init__(parent)
        self.setObjectName("GgsNewCrsDialog")
        self._kind_fixed = "geo" if str(kind) == "geo" else "proj"
        self.setWindowTitle(_tr("新建地理坐标系") if self._kind_fixed == "geo"
                            else _tr("新建投影坐标系"))
        try:
            from ggis.common.styling import icons as _icons
            self.setWindowIcon(_icons.icon("new_crs", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        self.setMinimumWidth(520)
        self._name = ""
        self._wkt = ""
        self._crs = GgsCrs()
        self._spin = {}
        self._build()
        self._on_kind_changed()
        self._on_method_changed()
        self._on_datum_changed()
        if prefill:
            try:
                self._apply_prefill(prefill)
            except Exception:
                _log.exception("silent exception in __init__")

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        head = QFormLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        self.ed_name = GgsNewCrsName()
        self.ed_name.setPlaceholderText("")
        head.addRow(_tr("名称"), self.ed_name)


        self.cmb_datum = GgsNewCrsDatum()
        for label, token in _DATUMS:
            self.cmb_datum.addItem(_tr(label), token)
        self.cmb_datum.addItem(_tr("自定义椭球…"), "__custom__")
        self.cmb_datum.currentIndexChanged.connect(
            lambda *_: self._on_datum_changed())
        head.addRow(_tr("基准（椭球）"), self.cmb_datum)
        self.spn_a = GgsNewCrsEllpsA()
        self.spn_a.setRange(1.0, 100000000.0)
        self.spn_a.setDecimals(4)
        self.spn_a.setValue(6378137.0)
        self.spn_a.setSuffix(" m")
        self.spn_rf = GgsNewCrsEllpsRf()
        self.spn_rf.setRange(1.0, 100000.0)
        self.spn_rf.setDecimals(9)
        self.spn_rf.setValue(298.257222101)
        for _w in (self.spn_a, self.spn_rf):
            _w.valueChanged.connect(lambda *_: self._refresh_proj())
        self._row_a = _row_host(self.spn_a)
        self._row_rf = _row_host(self.spn_rf)
        head.addRow(_tr("长半轴"), self._row_a)
        head.addRow(_tr("扁率倒数"), self._row_rf)
        self.lbl_a = head.labelForField(self._row_a)
        self.lbl_rf = head.labelForField(self._row_rf)
        root.addLayout(head)

        self.unit_box = QWidget()
        ub = QFormLayout(self.unit_box)
        ub.setContentsMargins(0, 0, 0, 0)
        ub.setSpacing(6)
        self.cmb_ang = GgsNewCrsAngUnit()
        for label, token in _ANG_UNITS:
            self.cmb_ang.addItem(_tr(label), token)
        ub.addRow(_tr("角度单位"), self.cmb_ang)
        self.cmb_pm = GgsNewCrsPrimeMeridian()
        for label, token in _PRIME_MERIDIANS:
            self.cmb_pm.addItem(_tr(label), token)
        self.cmb_pm.currentIndexChanged.connect(
            lambda *_: self._on_pm_changed())
        ub.addRow(_tr("本初子午线"), self.cmb_pm)
        self.spn_pm = GgsNewCrsPmValue()
        self.spn_pm.setRange(-180.0, 180.0)
        self.spn_pm.setDecimals(8)
        self.spn_pm.setSuffix(" °")
        self.spn_pm.setToolTip("")
        self.spn_pm.valueChanged.connect(lambda *_: self._refresh_proj())
        self._row_pm = _row_host(self.spn_pm)
        ub.addRow(_tr("子午线经度"), self._row_pm)
        self.cmb_len = GgsNewCrsLenUnit()
        for label, token in _LEN_UNITS:
            self.cmb_len.addItem(_tr(label), token)
        ub.addRow(_tr("长度单位"), self.cmb_len)
        self.lbl_ang = ub.labelForField(self.cmb_ang)
        self.lbl_len = ub.labelForField(self.cmb_len)
        self.lbl_pm = ub.labelForField(self.cmb_pm)
        self.lbl_pm_val = ub.labelForField(self._row_pm)
        root.addWidget(self.unit_box)

        self.proj_box = QWidget()
        pb = QVBoxLayout(self.proj_box)
        pb.setContentsMargins(0, 0, 0, 0)
        pb.setSpacing(6)
        gc = GgsGroupCard(_tr("投影参数"), "crs_proj")
        self.cmb_method = GgsNewCrsMethod()
        common = [k for k in _pm.COMMON]
        order = common + [k for k, _l, _p in _pm.PROJ_METHODS
                          if k not in set(common)]
        for key in order:
            self.cmb_method.addItem(_tr(_pm.method_label(key)), key)
        self.cmb_method.setMaxVisibleItems(18)
        i0 = self.cmb_method.findData("tmerc")
        if i0 >= 0:
            self.cmb_method.setCurrentIndex(i0)
        gc.addRow(_tr("投影方法"), self.cmb_method)
        host_lay = QHBoxLayout()
        host_lay.setContentsMargins(0, 0, 0, 0)
        host_lay.setSpacing(0)
        gc.addRow(host_lay)
        self._proj_lay = host_lay
        self.param_host = QWidget()
        host_lay.addWidget(self.param_host)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(gc.card)
        scroll.setMaximumHeight(360)
        pb.addWidget(scroll)
        root.addWidget(self.proj_box)


        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._on_ok)
        box.rejected.connect(self.reject)
        try:
            from ggis.common.styling import icons as _icons
            bok = box.button(QDialogButtonBox.StandardButton.Ok)
            if bok is not None:
                bok.setIcon(_icons.icon("confirm", size=16))
            bc = box.button(QDialogButtonBox.StandardButton.Cancel)
            if bc is not None:
                bc.setIcon(_icons.icon("clear", size=16))
        except Exception:
            _log.exception("silent exception in _build")
        root.addWidget(box)

        self.cmb_method.currentIndexChanged.connect(
            lambda *_: self._on_method_changed())
        for w in (self.cmb_datum, self.cmb_ang, self.cmb_len, self.ed_name):
            try:
                if isinstance(w, QLineEdit):
                    w.textChanged.connect(lambda *_: self._refresh_proj())
                else:
                    w.currentIndexChanged.connect(lambda *_: self._refresh_proj())
            except Exception:
                _log.exception("silent exception in _build")

    def _kind(self):
        return getattr(self, "_kind_fixed", "proj")

    def _method_key(self):
        return str(self.cmb_method.currentData() or "tmerc")

    def _on_kind_changed(self):
        proj = (self._kind() == "proj")
        self.proj_box.setVisible(proj)
        self.lbl_ang.setVisible(not proj)
        self.cmb_ang.setVisible(not proj)
        self.lbl_len.setVisible(proj)
        self.cmb_len.setVisible(proj)
        self.lbl_pm.setVisible(not proj)
        self.cmb_pm.setVisible(not proj)
        self._on_pm_changed()
        self._refresh_proj()

    def _on_datum_changed(self):
        custom = str(self.cmb_datum.currentData() or "") == "__custom__"
        for w in (self._row_a, self._row_rf, self.lbl_a, self.lbl_rf):
            try:
                w.setVisible(custom)
            except Exception:
                _log.exception("silent exception in _on_datum_changed")
        self._refresh_proj()

    def _on_pm_changed(self):
        custom = str(self.cmb_pm.currentData() or "") == "__custom__"
        try:
            self._row_pm.setVisible(custom)
            if self.lbl_pm_val is not None:
                self.lbl_pm_val.setVisible(custom)
        except Exception:
            _log.exception("silent exception in _on_pm_changed")
        self._refresh_proj()

    def _pm_token(self):
        try:
            tok = str(self.cmb_pm.currentData() or "")
        except Exception:
            _log.exception("silent exception in _pm_token")
            return ""
        if not tok:
            return ""
        if tok == "__custom__":
            return "+pm=%.8f" % float(self.spn_pm.value())
        return "+pm=%s" % tok

    def _ellps_token(self):
        try:
            if str(self.cmb_datum.currentData() or "") != "__custom__":
                return ""
            a = float(self.spn_a.value())
            rf = float(self.spn_rf.value())
        except Exception:
            _log.exception("silent exception in _ellps_token")
            return ""
        if a <= 0 or rf <= 0:
            return ""
        return "+a=%.10g +rf=%.10g" % (a, rf)

    def _on_method_changed(self):
        keep = {}
        for name, sp in self._spin.items():
            try:
                keep[name] = float(sp.value())
            except Exception:
                _log.exception("silent exception in _on_method_changed")
                continue
        old = self.param_host
        if old is not None:
            try:
                self._proj_lay.removeWidget(old)
                old.hide()
                old.setParent(None)
                old.deleteLater()
            except Exception:
                _log.exception("silent exception in _on_method_changed")
        self.param_host = QWidget()
        self._proj_lay.addWidget(self.param_host)
        self._spin = {}
        key = self._method_key()
        defaults = (() if key in ("webmerc", "longlat", "lonlat", "latlon")
                    else _method_defaults(key))
        form = QFormLayout(self.param_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        if not defaults:
            pass
        for name, default in defaults:
            info = _PARAM_INFO.get(name)
            if info is None:
                continue
            label, suffix, lo, hi, dec, step = info
            sp = GgsNewCrsParam()
            sp.setDecimals(int(dec))
            sp.setRange(float(lo), float(hi))
            if step:
                sp.setSingleStep(float(step))
            sp.setValue(float(keep.get(name, default)))
            sp.setSuffix((" " + suffix) if suffix else "")
            sp.valueChanged.connect(lambda *_: self._refresh_proj())
            self._spin[name] = sp
            form.addRow(_tr(label), sp)
        self._refresh_proj()

    def _params(self):
        out = {}
        for name, sp in self._spin.items():
            try:
                out[name] = float(sp.value())
            except Exception:
                _log.exception("silent exception in _params")
                continue
        return out

    def proj4(self):
        return build_proj4(
            self._kind(), str(self.cmb_datum.currentData() or ""),
            self._method_key(),
            self._params(), str(self.cmb_len.currentData() or "m"),
            str(self.cmb_ang.currentData() or ""),
            self._pm_token(), self._ellps_token())

    def _refresh_proj(self):
        return

    def _default_name(self):
        if self._kind() == "geo":
            return _tr("新建地理坐标系")
        return _tr(_pm.method_label(self._method_key())) \
            or _tr("自定义坐标系")

    def _apply_prefill(self, pf):
        if not isinstance(pf, dict):
            return
        if pf.get("name"):
            self.ed_name.setText(str(pf["name"]))
        mk = str(pf.get("method") or "")
        if mk:
            i = self.cmb_method.findData(mk)
            if i >= 0:
                self.cmb_method.setCurrentIndex(i)
        for pname, v in (pf.get("params") or {}).items():
            sp = self._spin.get(pname)
            if sp is None:
                continue
            try:
                sp.setValue(float(v))
            except Exception:
                _log.exception("silent exception in _apply_prefill")
                continue
        dtok = str(pf.get("datum") or "")
        if dtok:
            i = self.cmb_datum.findData(dtok)
            if i >= 0:
                self.cmb_datum.setCurrentIndex(i)
        el = pf.get("ellps")
        if dtok == "__custom__" and el:
            try:
                self.spn_a.setValue(float(el[0]))
                self.spn_rf.setValue(float(el[1]))
            except Exception:
                _log.exception("silent exception in _apply_prefill")
        ang = pf.get("ang")
        if ang is not None:
            i = self.cmb_ang.findData(ang)
            if i >= 0:
                self.cmb_ang.setCurrentIndex(i)
        ln = pf.get("len")
        if ln:
            i = self.cmb_len.findData(ln)
            if i >= 0:
                self.cmb_len.setCurrentIndex(i)
        pm = pf.get("pm")
        if pm:
            i = self.cmb_pm.findData(pm)
            if i >= 0:
                self.cmb_pm.setCurrentIndex(i)
            if pm == "__custom__" and pf.get("pm_value") is not None:
                try:
                    self.spn_pm.setValue(float(pf["pm_value"]))
                except Exception:
                    _log.exception("silent exception in _apply_prefill")
        self._on_datum_changed()
        self._on_pm_changed()

    def _on_ok(self):
        name = (self.ed_name.text() or "").strip() or self._default_name()
        crs, wkt = crs_from_proj4(self.proj4(), name)
        if not crs.is_valid() or not wkt:
            GgsMsgBox.warn(self, _tr("坐标系无效"),
                           _tr("按当前参数建不出有效的坐标系，"
                               "请检查投影方法与各参数。"))
            return
        self._name, self._wkt, self._crs = name, wkt, crs
        self.accept()

    def result_name(self):
        return self._name

    def result_wkt(self):
        return self._wkt

    def result_crs(self):
        return self._crs




class GgsCrsDialog(GgsDialog):


    def __init__(self, parent=None, current="", title=None):
        super().__init__(parent)
        self.setObjectName("GgsCrsDialog")
        self.setWindowTitle(title or _tr("选择坐标系"))
        try:
            from ggis.common.styling import icons as _icons
            self.setWindowIcon(_icons.icon("crs", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        self.setMinimumSize(860, 580)
        self._authid = str(current or "")
        self._loaded = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.ed_search = GgsSearchEdit()
        self.ed_search.setPlaceholderText(
            "")
        self.ed_search.setClearButtonEnabled(True)
        try:
            from ggis.common.styling import icons as _icons
            self.ed_search.addAction(
                _icons.icon("search", size=16),
                QLineEdit.ActionPosition.LeadingPosition)
        except Exception:
            _log.exception("silent exception in __init__")
        top.addWidget(self.ed_search, 1)
        self.btn_new = GgsSmallMenuButtonStyle1(
            "new_crs", menu=self._build_new_menu(),
            tip=_tr("新建坐标系"))
        top.addWidget(self.btn_new)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(10)

        self.tree = GgsTreeWidget()
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setIndentation(16)
        body.addWidget(self.tree, 1)

        self.right_host = GgsCrsRight()
        self.right_host.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Expanding)
        right = QVBoxLayout(self.right_host)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        range_row = QHBoxLayout()
        range_row.setContentsMargins(0, 0, 0, 0)
        range_row.setSpacing(8)
        lbl_prev = GgsCrsSection(_tr("使用范围"))
        range_row.addWidget(lbl_prev)
        self.range_val = GgsAboutVal("")
        self.range_val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        range_row.addWidget(self.range_val, 1)
        right.addLayout(range_row)
        self.preview = _CrsMapPreview()
        right.addWidget(self.preview)
        card = GgsAboutCard()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(2)
        t = GgsAboutCardTitle(_tr("坐标系信息"))
        title_row.addWidget(t)
        title_row.addStretch(1)
        title_row.addWidget(self._build_copy_button(), 0,
                            Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(self._build_export_button(), 0,
                            Qt.AlignmentFlag.AlignVCenter)
        cl.addLayout(title_row)
        self.info_grid = QGridLayout()
        self.info_grid.setContentsMargins(0, 2, 0, 0)
        self.info_grid.setHorizontalSpacing(8)
        self.info_grid.setVerticalSpacing(3)
        self.info_grid.setColumnStretch(1, 1)
        self.lbl_note = GgsAboutNote("")
        self.lbl_note.setWordWrap(True)
        info_host = QWidget()
        il = QVBoxLayout(info_host)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(4)
        il.addLayout(self.info_grid)
        il.addWidget(self.lbl_note)
        il.addStretch(1)
        info_scroll = QScrollArea()
        info_scroll.setWidgetResizable(True)
        info_scroll.setFrameShape(QFrame.Shape.NoFrame)
        info_scroll.setWidget(info_host)
        cl.addWidget(info_scroll, 1)
        right.addWidget(card, 1)
        body.addWidget(self.right_host, 1)
        root.addLayout(body, 1)


        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        try:
            from ggis.common.styling import icons as _icons
            bok = box.button(QDialogButtonBox.StandardButton.Ok)
            if bok is not None:
                bok.setIcon(_icons.icon("confirm", size=16))
            bcancel = box.button(QDialogButtonBox.StandardButton.Cancel)
            if bcancel is not None:
                bcancel.setIcon(_icons.icon("clear", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        self.buttons = box
        root.addWidget(box)

        self.ed_search.textChanged.connect(lambda *_: self._refresh())
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_menu)
        self.tree.itemExpanded.connect(self._on_expanded)
        self.tree.currentItemChanged.connect(lambda *_: self._update_current())
        self.tree.itemDoubleClicked.connect(self._on_double_click)

        self._set_info(None)
        QTimer.singleShot(0, self._ensure_loaded)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_tree_height()

    def _sync_tree_height(self):
        pass

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        self._refresh()

    def _build_new_menu(self):
        m = QMenu(self)
        try:
            from ggis.common.styling import icons as _icons
        except Exception:
            _log.exception("silent exception in _build_new_menu")
            _icons = None
        items = ((_tr("新建地理坐标系…"), "geo", "crs_geo"),
                 (_tr("新建投影坐标系…"), "proj", "crs_proj"),
                 (_tr("导入坐标系…"), "import", "add_vector"),
                 (_tr("从字符串创建…"), "text", "input_file"))
        for label, kind, ic in items:
            a = (m.addAction(_icons.icon(ic, size=16), label)
                 if _icons is not None else m.addAction(label))
            if kind == "import":
                a.triggered.connect(
                    lambda _c=False: self._on_import_crs())
            else:
                a.triggered.connect(
                    lambda _c=False, k=kind: self._on_new(k))
        return m

    _IMPORT_FILTER = ("栅格与矢量数据 (*.tif *.tiff *.img *.vrt *.shp "
                      "*.geojson *.json *.gpkg *.gdb *.kml *.dxf *.tab "
                      "*.mif);;坐标系文件 (*.wkt *.prj *.txt)")

    def _on_import_crs(self):
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                self, _tr("导入坐标系"), "", _tr(self._IMPORT_FILTER))
        except Exception:
            _log.exception("silent exception in _on_import_crs")
            return
        if not path:
            return
        ext = os.path.splitext(str(path))[1].lower()
        crs_text = ""
        if ext in (".wkt", ".prj", ".txt"):
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    crs_text = f.read().strip()
            except Exception as e:
                _log.exception("silent exception in _on_import_crs")
                self._tip(_tr("读取失败：{0}").format(e))
                return
        else:
            crs_text = self._crs_of_dataset(path)
        if not crs_text:
            self._tip(_tr("没能从该文件读出坐标系"))
            return
        c = GgsCrs.from_user_input(crs_text)
        if c is None or not c.is_valid():
            self._tip(_tr("没能解析出有效的坐标系"))
            return
        try:
            wkt = crs_proj_string(c) or c.to_wkt()
        except Exception:
            _log.exception("silent exception in _on_import_crs")
            wkt = c.to_wkt() if c is not None else ""
        if not wkt:
            self._tip(_tr("没能解析出有效的坐标系"))
            return
        name = os.path.splitext(os.path.basename(str(path)))[0]
        desc = (c.description() or "").strip()
        if desc and desc != name:
            name = "%s - %s" % (name, desc)
        push_custom(name, wkt)
        self.ed_search.setText("")
        self._authid = wkt
        self._build_roots()
        self._locate(wkt)
        self._update_current()
        self._tip(_tr("已导入坐标系：{0}").format(name))

    @staticmethod
    def _crs_of_dataset(path):
        s = str(path or "")
        ext = os.path.splitext(s)[1].lower()
        try:
            if ext in (".tif", ".tiff", ".img", ".vrt", ".vrt.ovr",
                       ".png", ".jpg", ".jpeg", ".bmp", ".ecw", ".sid"):
                import rasterio
                with rasterio.open(s) as ds:
                    crs = ds.crs
                    return crs.to_wkt() if crs is not None else ""
            import pyogrio
            info = pyogrio.read_info(s)
            return str(info.get("crs") or "")
        except Exception:
            _log.exception("silent exception in _crs_of_dataset")
            return ""

    def _on_new(self, kind="proj", entry=None):
        prefill = None
        if entry is not None and str(kind) != "text":
            prefill = _crs_prefill(entry)
        try:
            dlg = (_CrsFromStringDialog(self) if str(kind) == "text"
                   else _NewCrsDialog(self, kind=kind, prefill=prefill))
        except Exception as e:
            GgsMsgBox.warn(self, _tr("无法打开新建坐标系"),
                           _tr("原因：{0}").format(e))
            return
        if not dlg.exec():
            return
        wkt = dlg.result_wkt()
        if not wkt:
            return
        name = dlg.result_name()
        push_custom(name, wkt)
        self.ed_search.setText("")
        self._authid = wkt
        self._build_roots()
        self._locate(wkt)
        self._update_current()

    def _top_of(self, item):
        it = item
        while it is not None and it.parent() is not None:
            it = it.parent()
        if it is None:
            return None, None
        return (str(it.data(0, _KIND) or ""),
                it.data(0, _PAYLOAD))

    def _on_tree_menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None:
            return
        if str(it.data(0, _KIND) or "") != "crs":
            return
        authid = str(it.data(0, _AUTHID) or "")
        if not authid:
            return
        top_kind, top_payload = self._top_of(it)
        entry = crs_index().get(authid)
        if entry is None:
            for e in self._custom_entries():
                if e[0] == authid:
                    entry = e
                    break
        m = QMenu(self)
        a_cm = (m.addAction(_tr("复制并修改"))
                if entry is not None else None)
        a_del = a_mru = None
        if top_payload == ("custom",):
            a_del = m.addAction(_tr("删除此坐标系"))
        elif top_payload == ("mru",):
            a_mru = m.addAction(_tr("从最近使用中移除"))
        chosen = m.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is a_cm:
            kind = "proj" if bool(entry[2]) else "geo"
            self._on_new(kind, entry=entry)
        elif chosen is a_del:
            remove_custom(authid)
            self._after_list_change(it)
        elif chosen is a_mru:
            remove_recent(authid)
            self._after_list_change(it)

    def _drop_empty_group(self, node):
        try:
            i = self.tree.indexOfTopLevelItem(node)
            if i >= 0:
                self.tree.takeTopLevelItem(i)
            else:
                par = node.parent()
                if par is not None:
                    par.removeChild(node)
            payload = node.data(0, _PAYLOAD)
            if payload is not None:
                self._top.pop(str(payload[0]), None)
        except Exception:
            _log.exception("silent exception in _drop_empty_group")

    def _after_list_change(self, item):
        parent = item.parent() if item is not None else None
        if parent is None:
            return
        idx = parent.indexOfChild(item)
        if idx < 0:
            return
        parent.takeChild(idx)
        top = parent
        while top.parent() is not None:
            top = top.parent()
        payload = top.data(0, _PAYLOAD)
        if payload == ("custom",):
            base, n = _tr("自定义坐标系"), len(self._custom_entries())
        elif payload == ("mru",):
            base, n = _tr("最近使用"), len(recent_crs())
        else:
            return
        if n <= 0:
            i = self.tree.indexOfTopLevelItem(top)
            if i >= 0:
                self.tree.takeTopLevelItem(i)
            try:
                self._top.pop(payload[0], None)
            except Exception:
                _log.exception("silent exception in _after_list_change")
        else:
            top.setText(0, "%s (%d)" % (base, n))

    def _node(self, text, kind, payload=None, count=None, lazy=True,
              icon=None):
        it = QTreeWidgetItem([text if count is None
                              else "%s (%d)" % (text, count)])
        it.setData(0, _KIND, kind)
        it.setData(0, _PAYLOAD, payload)
        it.setData(0, _AUTHID, "")
        it.setData(0, _FILLED, not lazy)
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if icon:
            self._set_node_icon(it, icon)
        if lazy:
            it.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            it.addChild(QTreeWidgetItem([""]))
        return it

    def _set_node_icon(self, item, name):
        try:
            item.setData(0, _ICON, name)
        except Exception:
            _log.exception("silent exception in _set_node_icon")
            return
        try:
            from ggis.common.styling import icons as _icons
            item.setIcon(0, _icons.icon(name, size=16))
        except Exception:
            _log.exception("silent exception in _set_node_icon")

    def retheme(self):
        def _walk(item):
            name = item.data(0, _ICON)
            if name:
                try:
                    from ggis.common.styling import icons as _icons
                    item.setIcon(0, _icons.icon(name, size=16))
                except Exception:
                    _log.exception("silent exception in _walk")
            for i in range(item.childCount()):
                _walk(item.child(i))
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            _walk(root.child(i))

    def _crs_node(self, entry):
        authid, name, projected, method, area = entry
        it = QTreeWidgetItem([_entry_label(authid, name)])
        it.setData(0, _AUTHID, authid)
        it.setData(0, _KIND, "crs")
        it.setData(0, _PAYLOAD, None)
        it.setData(0, _FILLED, True)
        it.setToolTip(0, _entry_label(authid, name))
        it.setFlags(Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable)
        self._set_node_icon(it, "crs_proj" if projected else "crs_geo")
        return it

    def _select_inside(self, node):
        want = str(getattr(self, "_authid", "") or "")
        if not want:
            return
        for i in range(node.childCount()):
            ch = node.child(i)
            if ch.data(0, _AUTHID) == want:
                self.tree.setCurrentItem(ch)
                self.tree.scrollToItem(ch)
                return

    def _fill_entries(self, node, entries):
        want = str(getattr(self, "_authid", "") or "")
        if want:
            entries = sorted(entries, key=lambda e: 0 if e[0] == want else 1)
        shown = entries[:MAX_GROUP]
        node.addChildren([self._crs_node(e) for e in shown])
        if len(entries) > MAX_GROUP:
            more = QTreeWidgetItem(
                [_tr("共 {0} 条，仅显示前 {1} 条")
                 .format(len(entries), MAX_GROUP)])
            more.setFlags(Qt.ItemFlag.NoItemFlags)
            node.addChild(more)

    def _custom_entries(self):
        global _CUSTOM_ENTRIES, _CUSTOM_SIG
        raw = custom_crs()
        sig = tuple(raw)
        if _CUSTOM_ENTRIES is not None and _CUSTOM_SIG == sig:
            return _CUSTOM_ENTRIES
        out = []
        for name, wkt in raw:
            c = custom_crs_object(wkt)
            if not c.is_valid():
                continue
            out.append((wkt, name or c.description() or _tr("自定义坐标系"),
                        bool(c.is_projected()), c.description(), None))
        _CUSTOM_ENTRIES = out
        _CUSTOM_SIG = sig
        return out

    def _mru_entries(self):
        idx = crs_index()
        cust = {e[0]: e for e in self._custom_entries()}
        out = []
        seen = set()
        for a in recent_crs():
            if a in seen:
                continue
            e = idx.get(a)
            if e is None:
                e = cust.get(a)
            if e is None:
                continue
            seen.add(a)
            out.append(e)
        return out

    def _layer_crs_entries(self):
        try:
            layers = GgsProject.instance().layers()
        except Exception:
            _log.exception("silent exception in _layer_crs_entries")
            return []
        seen = set()
        out = []
        for lyr in (layers or []):
            try:
                c = lyr.crs()
            except Exception:
                _log.exception("silent exception in _layer_crs_entries")
                c = None
            if c is None or not c.is_valid():
                continue
            a = (c.authid() or "").strip()
            if not a or a in seen:
                continue
            seen.add(a)
            name = c.display_name() or a
            out.append((a, name, not c.is_geographic(), "", None))
        return out

    def _build_roots(self):
        self.tree.clear()
        self._top = {}
        cust_wkts = {w for _n, w in custom_crs()}
        idx = crs_index()
        rec = [a for a in recent_crs()
               if a in idx or a in cust_wkts]
        if rec:
            it = self._node(_tr("最近使用"), "list", ("mru",),
                            count=len(rec), icon="recent")
            self.tree.addTopLevelItem(it)
            self._top["mru"] = it
        cust = self._custom_entries()
        if cust:
            it = self._node(_tr("自定义坐标系"), "list", ("custom",),
                            count=len(cust), icon="bookmark")
            self.tree.addTopLevelItem(it)
            self._top["custom"] = it

        lay_crs = self._layer_crs_entries()
        if lay_crs:
            it = self._node(_tr("图层坐标系"), "list", ("layers",),
                            count=len(lay_crs), icon="crs")
            self.tree.addTopLevelItem(it)
            self._top["layers"] = it

        geo = [e for e in crs_entries() if not e[2]]
        proj = [e for e in crs_entries() if e[2]]
        it = self._node(_tr("地理坐标系"), "geo", None, count=len(geo),
                        icon="crs_geo")
        self.tree.addTopLevelItem(it)
        self._top["geo"] = it
        it = self._node(_tr("投影坐标系"), "methods", None, count=len(proj),
                        icon="crs_proj")
        self.tree.addTopLevelItem(it)
        self._top["proj"] = it

    def _on_expanded(self, it):
        if it is None or it.data(0, _FILLED):
            return
        it.setData(0, _FILLED, True)
        it.takeChildren()
        kind = it.data(0, _KIND)
        payload = it.data(0, _PAYLOAD)
        if kind == "methods":
            self._fill_methods(it)
        elif kind == "geo":
            self._fill_geo_groups(it)
        elif kind == "list":
            self._fill_list(it, payload)
        else:
            return
        self._select_inside(it)

    def _fill_methods(self, node):
        buckets = {}
        for e in crs_entries():
            if not e[2]:
                continue
            buckets.setdefault(method_group(e[3]), []).append(e)
        for label in sorted(buckets, key=lambda k: (-len(buckets[k]), k)):
            node.addChild(self._node(_tr(label), "list", ("proj", label),
                                     count=len(buckets[label]),
                                     icon="crs_proj"))

    def _fill_geo_groups(self, node):
        buckets = {}
        for e in crs_entries():
            if e[2]:
                continue
            buckets.setdefault(geo_group(e[1]), []).append(e)
        labels = sorted(buckets,
                        key=lambda k: (k == _GEO_OTHER, -len(buckets[k]), k))
        for label in labels:
            node.addChild(self._node(_tr(label), "list", ("geo", label),
                                     count=len(buckets[label]), icon="crs_geo"))

    def _fill_list(self, node, payload):
        kind = (payload or ("geo",))[0]
        idx = crs_index()
        if kind == "layers":
            entries = self._layer_crs_entries()
        elif kind == "mru":
            entries = self._mru_entries()
        elif kind == "custom":
            entries = self._custom_entries()
            if not entries:
                QTimer.singleShot(0, lambda n=node: self._drop_empty_group(n))
                return
        elif kind == "proj":
            label = payload[1]
            entries = [e for e in crs_entries()
                       if e[2] and method_group(e[3]) == label]
        elif kind == "geo":
            label = payload[1]
            entries = [e for e in crs_entries()
                       if not e[2] and geo_group(e[1]) == label]
        else:
            entries = [e for e in crs_entries() if not e[2]]
        self._fill_entries(node, entries)

    def _refresh(self):
        if not self._loaded:
            return
        term = (self.ed_search.text() or "").strip().lower()
        if term:
            self._show_search(term)
        else:
            self._build_roots()
            self._locate(self._authid)
        self._update_current()

    def _show_search(self, term):
        items = crs_entries()
        t = term.replace("epsg:", "").replace("epsg", "")
        hits = [e for e in items
                if (t and t in e[0].lower().split(":")[-1])
                or (term in e[1].lower())
                or (term in e[0].lower())]
        custom = [e for e in self._custom_entries()
                  if (term in str(e[1]).lower()) or (term in e[0].lower())]

        self.tree.clear()
        node = self._node(_tr("搜索结果"), "plain", None,
                          count=len(hits) + len(custom), lazy=False)
        self.tree.addTopLevelItem(node)
        self._fill_entries(node, hits[:MAX_SEARCH])
        for e in custom:
            node.addChild(self._crs_node(e))
        node.setExpanded(True)


    def _locate(self, authid):
        want = str(authid or "")
        if not want:
            return
        top = getattr(self, "_top", {})
        cust = {w for _n, w in custom_crs()}
        mru = set(recent_crs())

        node = None
        parent = None
        entry = crs_index().get(want)
        if want in mru and top.get("mru") is not None:
            node = top["mru"]
        elif want in cust and top.get("custom") is not None:
            node = top["custom"]
        elif entry is None:
            return
        elif not entry[2]:
            geo = top.get("geo")
            if geo is not None:
                self._on_expanded(geo)
                label = geo_group(entry[1])
                for i in range(geo.childCount()):
                    ch = geo.child(i)
                    if ch.data(0, _PAYLOAD) == ("geo", label):
                        node = ch
                        parent = geo
                        break
        else:
            proj = top.get("proj")
            if proj is not None:
                self._on_expanded(proj)
                label = method_group(entry[3])
                for i in range(proj.childCount()):
                    ch = proj.child(i)
                    if ch.data(0, _PAYLOAD) == ("proj", label):
                        node = ch
                        parent = proj
                        break
        if node is None:
            return
        self._on_expanded(node)
        for i in range(node.childCount()):
            ch = node.child(i)
            if ch.data(0, _AUTHID) == want:
                if parent is not None:
                    parent.setExpanded(True)
                node.setExpanded(True)
                self.tree.setCurrentItem(ch)
                self.tree.scrollToItem(ch)
                return

    def _current_authid(self):
        it = self.tree.currentItem()
        if it is None:
            return ""
        return str(it.data(0, _AUTHID) or "")

    def _candidate_from_input(self):
        text = (self.ed_search.text() or "").strip()
        if not text:
            return ""
        c = GgsCrs.from_user_input(text)
        if c is not None and c.is_valid():
            return c.authid()
        return ""

    def _set_info_rows(self, pairs):
        grid = getattr(self, "info_grid", None)
        if grid is None:
            return
        while grid.count():
            it = grid.takeAt(0)
            w = it.widget()
            if w is None:
                continue
            try:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            except Exception:
                _log.exception("silent exception in _set_info_rows")
        self._info_rows = []
        for row, (key, val) in enumerate(pairs or []):
            k = GgsAboutKey(str(key))
            k.setAlignment(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignTop)
            v = GgsAboutVal(str(val))
            v.setWordWrap(True)
            v.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(k, row, 0)
            grid.addWidget(v, row, 1)
            self._info_rows.append((k, v))

    def _set_info(self, entry):
        note = getattr(self, "lbl_note", None)
        if entry is None:
            self.preview.set_area(None, valid=False)
            self._set_range(None)
            self._set_info_rows([])
            if note is not None:
                note.setText(_tr("（未选择坐标系）"))
            self._sync_copy_button()
            return
        authid, name, projected, method, area = entry
        self.preview.set_area(area, valid=True)
        self._set_range(area)
        try:
            is_custom = authid in {w for _n, w in custom_crs()}
        except Exception:
            _log.exception("silent exception in _set_info")
            is_custom = False
        rows = [(_tr("名称"), name),
                (_tr("编号"), _tr("自定义") if is_custom else authid),
                (_tr("类型"),
                 _tr("投影坐标系") if projected else _tr("地理坐标系"))]
        if projected and method:
            rows.append((_tr("投影方法"), _tr(method_group(method))))
        c = None
        try:
            c = (custom_crs_object(authid) if is_custom
                 else GgsCrs.from_user_input(authid))
        except Exception:
            _log.exception("silent exception in _set_info")
            c = None
        if c is not None and c.is_valid():
            rows.append((_tr("单位"),
                         c.unit_abbreviation() or c.map_units()))
            try:
                pj = c.to_pyproj()
            except Exception:
                _log.exception("silent exception in _set_info")
                pj = None
            if pj is not None:
                try:
                    rows.extend(_crs_geo_rows(pj, bool(projected)))
                except Exception:
                    _log.exception("silent exception in _set_info")
        self._set_info_rows(rows)
        if note is not None:
            note.setText("")
        self._sync_copy_button()

    def _set_range(self, area):
        vv = getattr(self, "range_val", None)
        if vv is None:
            return
        if area is None:
            vv.setText("")
            return
        _desc, w, s, e, n = area
        vv.setText("W: %s   E: %s   S: %s   N: %s"
                   % (_fmt_deg(w), _fmt_deg(e),
                      _fmt_deg(s), _fmt_deg(n)))

    @staticmethod
    def _copy_formats():
        return (("wkt", _tr("WKT")),
                ("proj", _tr("PROJ 串"),))

    def _build_copy_button(self):
        btn = GgsSmallButtonStyle1(
            "copy_features", _tr("复制坐标系定义（WKT）"),
            slot=lambda _c=False: self._on_copy_crs("wkt", anchor=btn))
        btn.setEnabled(False)
        self.btn_copy = btn
        return btn

    def _build_export_button(self):
        btn = GgsSmallButtonStyle1(
            "save", _tr("导出坐标系到文件（WKT）"),
            slot=lambda _c=False: self._on_export_crs())
        btn.setEnabled(False)
        self.btn_export = btn
        return btn

    def _on_export_crs(self):
        a = self.selected_authid()
        if not a:
            return
        text = self._crs_text(a, "wkt")
        if not text:
            self._tip(_tr("这个坐标系没有 WKT 形式"))
            return
        try:
            from PySide6.QtWidgets import QFileDialog
            default = "%s.wkt" % (self._crs_file_stem(a) or "crs")
            path, _ = QFileDialog.getSaveFileName(
                self, _tr("导出坐标系到文件"), default,
                _tr("WKT 文件 (*.wkt *.prj *.txt)"))
        except Exception:
            _log.exception("silent exception in _on_export_crs")
            return
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            _log.exception("silent exception in _on_export_crs")
            self._tip(_tr("导出失败：{0}").format(e))
            return
        self._tip(_tr("已导出坐标系定义到：{0}").format(
            os.path.basename(str(path))), anchor=self.btn_export)

    @staticmethod
    def _crs_file_stem(authid):
        s = str(authid or "")
        for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|'):
            s = s.replace(ch, "_")
        return s.strip("._") or "crs"

    def _sync_copy_button(self):
        has = bool(self.selected_authid())
        for nm in ("btn_copy", "btn_export"):
            btn = getattr(self, nm, None)
            if btn is None:
                continue
            try:
                btn.setEnabled(has)
            except Exception:
                _log.exception("silent exception in _sync_copy_button")

    @staticmethod
    def _crs_text(authid, fmt):
        a = str(authid or "")
        if not a:
            return ""
        if fmt == "epsg":
            try:
                c = GgsCrs.from_user_input(a)
                code = c.to_epsg() if c is not None else None
            except Exception:
                _log.exception("silent exception in _crs_text")
                code = None
            if code:
                return "EPSG:%d" % int(code)
            s = a.strip()
            return s if s.upper().startswith("EPSG:") else ""
        if fmt == "proj":
            try:
                return crs_proj_string(GgsCrs.from_user_input(a))
            except Exception:
                _log.exception("silent exception in _crs_text")
                return ""
        try:
            _c, wkt = crs_from_text(a, "")
            if wkt:
                return wkt
        except Exception:
            _log.exception("silent exception in _crs_text")
        return a if "[" in a else ""

    def _on_copy_crs(self, fmt="wkt", anchor=None):
        a = self.selected_authid()
        if not a:
            return
        text = self._crs_text(a, fmt)
        names = dict(self._copy_formats())
        if not text:
            self._tip(_tr("这个坐标系没有 {0} 形式").format(
                names.get(fmt, "")), anchor=anchor)
            return
        try:
            from PySide6.QtWidgets import QApplication
            cb = QApplication.clipboard()
            if cb is None:
                return
            cb.setText(text)
        except Exception:
            _log.exception("silent exception in _on_copy_crs")
            return
        self._tip(_tr("已复制{0}到剪贴板").format(
            names.get(fmt, _tr("坐标系定义"))), anchor=anchor)

    def _tip(self, text, anchor=None):
        try:
            from PySide6.QtGui import QCursor
            from PySide6.QtWidgets import QToolTip
            if anchor is not None:
                try:
                    p = anchor.mapToGlobal(
                        anchor.rect().bottomLeft())
                    p.setY(p.y() + 6)
                    QToolTip.showText(p, text, self)
                    return
                except Exception:
                    _log.exception("silent exception in _tip")
            QToolTip.showText(QCursor.pos(), text, self)
        except Exception:
            _log.exception("silent exception in _tip")

    def _update_current(self):
        a = self._current_authid()
        if a:
            self._authid = a
            self._set_info(self._entry_of(a))
            return
        cand = self._candidate_from_input()
        if cand:
            self._authid = cand
            self._set_info(self._entry_of(cand))
        else:
            self._set_info(None)

    def _entry_of(self, authid):
        e = crs_index().get(authid)
        if e is not None:
            return e
        for c in self._custom_entries():
            if c[0] == authid:
                return c
        return None

    def _on_double_click(self, it, _col):
        if it is not None and it.data(0, _AUTHID):
            self.accept()

    def _on_accept(self):
        if self.selected_authid():
            try:
                push_recent(self.selected_authid())
            except Exception:
                _log.exception("silent exception in _on_accept")
            self.accept()
            return
        GgsMsgBox.warn(self, _tr("请先选择一个坐标系"), "")

    def selected_authid(self):
        a = self._current_authid()
        if a:
            return a
        return self._candidate_from_input() or ""

    def selected_crs(self):
        a = self.selected_authid()
        if not a:
            return GgsCrs()
        c = GgsCrs.from_user_input(a)
        return c if c is not None else GgsCrs()


class GgsCrsRight(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCrsRight")
class GgsCrsSection(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCrsSection")
class GgsCrsWkt(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCrsWkt")
class GgsNewCrsAngUnit(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsAngUnit")
class GgsNewCrsDatum(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsDatum")
class GgsNewCrsEllpsA(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsEllpsA")
class GgsNewCrsEllpsRf(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsEllpsRf")
class GgsNewCrsLenUnit(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsLenUnit")
class GgsNewCrsMethod(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsMethod")
class GgsNewCrsName(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsName")
class GgsNewCrsParam(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsParam")
class GgsNewCrsPmValue(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsPmValue")
class GgsNewCrsPrimeMeridian(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNewCrsPrimeMeridian")
