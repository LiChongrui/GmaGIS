# -*- coding: utf-8 -*-

import io
import json
import logging
import os

from ..core.crs import GgsCoordinateReferenceSystem as GgsCrs
from .registry import load_file

_log = logging.getLogger("gmagis")

from ..exec import guard as _guard

__all__ = ["PROJECT_SUFFIXES", "PROJECT_FORMAT_VERSION",
           "project_to_dict", "save_project", "read_project_dict",
           "load_project", "describe_project",
           "layer_to_dict", "layer_from_snapshot",
           "tile_layer_from_snapshot"]

PROJECT_SUFFIXES = {".ggs"}
PROJECT_FORMAT_VERSION = 3

APP_SIGNATURE = "GmaGIS project"


def _rel_source(src, base_dir):
    if not src or not base_dir:
        return src
    if os.path.isabs(src):
        try:
            if os.path.splitdrive(src)[0].lower() != \
                    os.path.splitdrive(os.path.abspath(base_dir))[0].lower():
                return src
        except Exception:
            _log.exception("silent exception in _rel_source")
    try:
        if os.path.isabs(src):
            rel = os.path.relpath(src, base_dir)
            if not rel.startswith(".." + os.sep) and \
                    rel.count("..") <= 2:
                return rel
    except Exception:
        _log.exception("silent exception in _rel_source")
    return src


def _embed_vector(layer):
    try:
        geoms_src = list(layer.geoms())
    except Exception:
        _log.exception("silent exception in _embed_vector")
        return None
    geoms = []
    for g in geoms_src:
        if g is None:
            geoms.append("")
            continue
        try:
            geoms.append(str(g.wkt))
        except Exception:
            _log.exception("silent exception in _embed_vector")
            geoms.append("")
    try:
        attrs = [dict(a) for a in (layer.attrs() or [])]
    except Exception:
        _log.exception("silent exception in _embed_vector")
        attrs = []
    try:
        fields = [[str(n), str(t)] for n, t in (layer.fields() or [])]
    except Exception:
        _log.exception("silent exception in _embed_vector")
        fields = []
    return {
        "geometry_type": str(layer.geometry_type() or ""),
        "fields": fields,
        "geoms": geoms,
        "attrs": attrs,
    }


def _layer_from_embedded(snap, emb):
    from ggis.core.model.layer import GgsVectorLayer
    from shapely import wkt as _wkt
    geoms = []
    for t in (emb.get("geoms") or []):
        if not t:
            geoms.append(None)
            continue
        try:
            geoms.append(_wkt.loads(str(t)))
        except Exception:
            _log.exception("silent exception in _layer_from_embedded")
            geoms.append(None)
    attrs = [dict(a) for a in (emb.get("attrs") or [])]
    fields = [(str(n), str(t)) for n, t in (emb.get("fields") or [])]
    crs = None
    try:
        aid = str(snap.get("crs") or "")
        if aid:
            crs = GgsCrs.from_user_input(aid)
    except Exception:
        _log.exception("silent exception in _layer_from_embedded")
        crs = None
    name = str(snap.get("name") or "")
    lyr = GgsVectorLayer(
        name, "", crs,
        str(emb.get("geometry_type") or snap.get("geometry_type") or ""),
        geoms, attrs, fields)
    try:
        lyr._valid = True
    except Exception:
        _log.exception("silent exception in _layer_from_embedded")
    return lyr


def layer_to_dict(layer, base_dir=""):
    d = {
        "name": str(layer.name() or ""),
        "source": _rel_source(str(layer.source() or ""), base_dir),
        "type": ("tile" if layer.is_tile()
                 else "table" if layer.is_table()
                 else "raster" if layer.is_raster() else "vector"),
        "visible": bool(layer.is_visible()),
        "opacity": float(layer.opacity()),
        "min_scale": float(layer.scale_range()[0] or 0.0),
        "max_scale": float(layer.scale_range()[1] or 0.0),
        "sub_layer": str(layer.sub_layer()) if hasattr(layer, "sub_layer") else "",
    }
    try:
        crs = layer.crs()
        if crs is not None and crs.is_valid():
            d["crs"] = crs.authid()
    except Exception:
        _log.exception("silent exception in layer_to_dict")

    if layer.is_tile():
        try:
            src = layer.tile_source()
            d["source"] = str(src.url if src is not None else "")
            if src is not None:
                d["tile_source"] = src.to_dict()
        except Exception:
            _log.exception("silent exception in layer_to_dict")
        return d

    if layer.is_table():
        return d

    if layer.is_vector():
        if not d["source"]:
            d["geometry_type"] = str(layer.geometry_type() or "")
            emb = _embed_vector(layer)
            if emb is not None:
                d["embedded"] = emb
        try:
            from ..render.renderers import get_renderer
            d["renderer"] = get_renderer(layer).to_dict()
        except Exception:
            _log.exception("silent exception in layer_to_dict")
        try:
            from ..render.labeling import get_label_style
            d["labels"] = get_label_style(layer).to_dict()
        except Exception:
            _log.exception("silent exception in layer_to_dict")
        try:
            _expr = str(layer.subset_expression() or "").strip()
            if _expr:
                d["filter"] = _expr
        except Exception:
            _log.exception("silent exception in layer_to_dict")
    elif layer.is_raster():
        try:
            from ggis.core.style.raster_display import get_display
            d["raster_display"] = get_display(layer).to_dict()
        except Exception:
            _log.exception("silent exception in layer_to_dict")
    return d




def _resolve_sub_layer(src, snap):
    sub = str(snap.get("sub_layer") or "")
    if sub:
        return sub
    name = str(snap.get("name") or "")
    if not name or not src or not os.path.exists(src):
        return ""
    try:
        from ggis.io.registry import is_vector_path
        from ggis.io.table_io import is_table_path
        if is_table_path(src) or not is_vector_path(src):
            return ""
        from ggis.io.vector_io import list_vector_layers
        names = [str(n) for n, _g in list_vector_layers(src)]
        if len(names) > 1 and name in names:
            return name
    except Exception:
        _log.exception("silent exception in _resolve_sub_layer")
    return ""


def _apply_snapshot(lyr, snap):
    try:
        if snap.get("name"):
            lyr.setName(str(snap["name"]))
        lyr.set_visible(bool(snap.get("visible", True)))
        if snap.get("opacity") is not None:
            lyr.set_opacity(float(snap["opacity"]))
        lyr.set_scale_range(float(snap.get("min_scale", 0.0) or 0.0),
                            float(snap.get("max_scale", 0.0) or 0.0))
    except Exception:
        _log.exception("silent exception in _apply_snapshot")
    if lyr.is_raster():
        _apply_raster_display(lyr, snap.get("raster_display"))
        return
    if not lyr.is_vector():
        return
    if lyr.is_table():
        return
    rd = snap.get("renderer")
    if rd:
        try:
            from ..render.renderers import (GgsFeatureRenderer,
                                            set_renderer)
            _r = GgsFeatureRenderer.from_dict(rd)
            _ensure = getattr(_r, "ensure_others", None)
            if callable(_ensure):
                try:
                    _ensure(lyr)
                except Exception:
                    _log.exception("silent exception in _apply_snapshot")
            set_renderer(lyr, _r)
        except Exception:
            _log.exception("silent exception in _apply_snapshot")
    lsd = snap.get("labels")
    if lsd:
        try:
            from ..render.labeling import LabelStyle, set_label_style
            set_label_style(lyr, LabelStyle.from_dict(lsd))
        except Exception:
            _log.exception("silent exception in _apply_snapshot")
    _apply_filter(lyr, snap.get("filter"))


def _apply_raster_display(lyr, data):
    if not data:
        return False
    try:
        from ggis.core.style.raster_display import GgsRasterDisplay, set_display
    except Exception:
        _log.exception("silent exception in _apply_raster_display")
        return False
    try:
        set_display(lyr, GgsRasterDisplay.from_dict(data))
        return True
    except Exception:
        _log.exception("silent exception in _apply_raster_display")
        return False


def _apply_filter(lyr, expr):
    text = str(expr or "").strip()
    if not text:
        return False
    try:
        from ggis.core.expr.expression import compile_expression
        from ggis.core.model.field import fields_from_layer
        from ggis.core.expr.query import features_by_expression
        node = compile_expression(text, fields_from_layer(lyr))
        fids = list(features_by_expression(lyr, node))
    except Exception as e:
        _log_filter_problem(lyr, text, e)
        try:
            lyr.clear_subset()
        except Exception:
            _log.exception("silent exception in _apply_filter")
        return False
    try:
        lyr.set_subset(fids, text)
        return True
    except Exception as e:
        _log_filter_problem(lyr, text, e)
        return False


def _log_filter_problem(lyr, expr, exc):
    try:
        import logging
        name = ""
        try:
            name = str(lyr.name() or "")
        except Exception:
            _log.exception("silent exception in _log_filter_problem")
            name = ""
        logging.getLogger("gmagis").warning(
            "工程里的过滤条件无法重建（图层「%s」）：%s ｜ 表达式：%s",
            name, exc, expr)
    except Exception:
        _log.exception("silent exception in _log_filter_problem")


def tile_layer_from_snapshot(snap):
    if not isinstance(snap, dict) or snap.get("type") != "tile":
        return None
    from ggis.core.model.layer import GgsTileLayer
    from ggis.core.analysis.tile import GgsTileSource

    src = GgsTileSource.from_dict(snap.get("tile_source"))
    if src is None or not src.is_valid():
        src = GgsTileSource(url=snap.get("source") or "",
                            name=snap.get("name") or "")
    if not src.is_valid():
        return None
    return GgsTileLayer(source_obj=src)


def layer_from_snapshot(snap, base_dir=""):
    if not isinstance(snap, dict):
        return None
    if snap.get("type") == "tile":
        lyr = tile_layer_from_snapshot(snap)
        if lyr is None:
            return None
        _apply_snapshot(lyr, snap)
        return lyr
    src = _abs_source(snap.get("source"), base_dir)
    if not src or not os.path.exists(src):
        emb = snap.get("embedded")
        if snap.get("type") == "vector" and isinstance(emb, dict):
            lyr = _layer_from_embedded(snap, emb)
            _apply_snapshot(lyr, snap)
            return lyr
        return None
    lyr = load_file(src, layer=_resolve_sub_layer(src, snap) or None)
    if lyr is None or not lyr.is_valid():
        return None
    _apply_snapshot(lyr, snap)
    return lyr




def project_to_dict(project, base_dir="", views=None, session=None):
    if views is None:
        views = getattr(project, "_views", None)
    if not views:
        try:
            views = [{
                "id": "map",
                "title": (project.title() if hasattr(project, "title")
                          else "") or "",
                "crs": None,
                "extent": None,
                "layers": [(l, True) for l in list(project.layers())],
            }]
        except Exception:
            _log.exception("silent exception in project_to_dict")
            views = []

    out_views = []
    unsaved = []
    pool = []
    pool_keys = {}

    def _tree_refs(node, id_lid, id_vis):
        if not isinstance(node, dict):
            return None
        if str(node.get("kind") or "") == "group":
            kids = []
            for c in (node.get("children") or []):
                r = _tree_refs(c, id_lid, id_vis)
                if r is not None:
                    kids.append(r)
            return {"kind": "group",
                    "name": str(node.get("name") or ""),
                    "visible": bool(node.get("visible", True)),
                    "expanded": bool(node.get("expanded", True)),
                    "children": kids}
        key = str(node.get("id") or "")
        lid = id_lid.get(key)
        if lid is None:
            return None
        own = node.get("visible")
        vis = bool(own) if own is not None else bool(id_vis.get(key, True))
        return {"lid": lid, "visible": vis}

    for v in views:
        vid = str(v.get("id") or "map")
        vtitle = str(v.get("title") or "")
        vcrs = v.get("crs")
        vext = v.get("extent")
        layer_objs = v.get("layers") or []
        id_lid = {}
        id_vis = {}
        for entry in layer_objs:
            if isinstance(entry, (tuple, list)) and len(entry) == 2:
                lyr, vis = entry
            else:
                lyr, vis = entry, True
            try:
                _lid_key = str(lyr.id())
            except Exception:
                _log.exception("silent exception in project_to_dict")
                _lid_key = None
            id_vis[_lid_key] = bool(vis)
            try:
                snap = layer_to_dict(lyr, base_dir)
                if (not str(lyr.source() or "")
                        and "embedded" not in snap):
                    unsaved.append(str(lyr.name() or ""))
                    id_lid[_lid_key] = None
                    continue
                key = (str(snap.get("type") or ""),
                       str(snap.get("source") or ""),
                       str(snap.get("sub_layer") or ""),
                       str(snap.get("name") or ""))
                emb = snap.get("embedded")
                if isinstance(emb, dict):
                    key = key + (str(emb.get("wkt")
                                     or emb.get("geometry") or ""),)
                lid = pool_keys.get(key)
                if lid is None:
                    lid = len(pool)
                    pool_keys[key] = lid
                    snap.pop("visible", None)
                    try:
                        snap["id"] = str(lyr.id())
                    except Exception:
                        _log.exception("silent exception in project_to_dict")
                    pool.append(snap)
                id_lid[_lid_key] = lid
            except Exception:
                _log.exception("silent exception in project_to_dict")
                id_lid[_lid_key] = None
                continue
        tree = v.get("tree")
        layer_refs = []
        if isinstance(tree, list) and tree:
            for node in tree:
                r = _tree_refs(node, id_lid, id_vis)
                if r is not None:
                    layer_refs.append(r)
            if not any(isinstance(r, dict)
                       and str(r.get("kind") or "") == "group"
                       for r in layer_refs):
                layer_refs.reverse()
        else:
            for entry in layer_objs:
                if isinstance(entry, (tuple, list)) and len(entry) == 2:
                    lyr, vis = entry
                else:
                    lyr, vis = entry, True
                try:
                    _lid_key = str(lyr.id())
                except Exception:
                    _log.exception("silent exception in project_to_dict")
                    continue
                lid = id_lid.get(_lid_key)
                if lid is None:
                    continue
                layer_refs.append({"lid": lid, "visible": bool(vis)})
        vd = {"id": vid, "title": vtitle, "layers": layer_refs}
        if vcrs:
            vd["crs"] = str(vcrs)
            if vext and len(vext) == 4:
                vd["extent"] = [float(x) for x in vext]
        _disp = v.get("display")
        if isinstance(_disp, dict) and _disp:
            vd["display"] = dict(_disp)
        out_views.append(vd)

    out = {
        "signature": APP_SIGNATURE,
        "version": PROJECT_FORMAT_VERSION,
        "title": str(project.title() or "") if hasattr(project, "title")
                 else "",
        "views": out_views,
    }
    try:
        out["layouts"] = project.layouts_to_dict()
    except Exception:
        _log.exception("silent exception in project_to_dict")
        out["layouts"] = []
    try:
        models = project.models_to_dict()
        if models:
            out["models"] = models
    except Exception:
        _log.exception("silent exception in project_to_dict")
    out["_unsaved_layers"] = unsaved
    out["layers_pool"] = pool
    if session and isinstance(session, dict):
        _vids = {str(vd.get("id") or "") for vd in out_views}
        _pages = session.get("pages")
        if isinstance(_pages, list):
            _kept = [p for p in _pages
                     if not (isinstance(p, dict) and p.get("kind") == "map")
                     or str(p.get("id") or "") in _vids]
            if len(_kept) != len(_pages):
                session = dict(session)
                session["pages"] = _kept
        out["session"] = session
    return out


class _FrozenProject(object):

    def __init__(self, project, views=None):
        from ggis.core.model.layer import freeze_layer
        try:
            self._title = project.title()
        except Exception:
            _log.exception("silent exception in __init__")
            self._title = ""
        try:
            self._file = str(project.file_name() or "")
        except Exception:
            _log.exception("silent exception in __init__")
            self._file = ""
        try:
            self._layouts = project.layouts_to_dict()
        except Exception:
            _log.exception("silent exception in __init__")
            self._layouts = []
        try:
            self._view_extent = project.view_extent()
        except Exception:
            _log.exception("silent exception in __init__")
            self._view_extent = None
        try:
            self._map_views = project.map_views_extent() or {}
        except Exception:
            _log.exception("silent exception in __init__")
            self._map_views = {}
        try:
            self._models = project.models_to_dict()
        except Exception:
            _log.exception("silent exception in __init__")
            self._model = {}
        try:
            self._layers = [freeze_layer(l) for l in list(project.layers())]
        except Exception:
            _log.exception("silent exception in __init__")
            self._layers = []
        self._views = list(views) if views is not None else []


    def layers(self):
        return list(self._layers)

    def title(self):
        return self._title

    def layouts_to_dict(self):
        return list(self._layouts)

    def view_extent(self):
        _e = self._view_extent
        try:
            if _e and len(_e) == 4:
                return [float(v) for v in _e]
        except Exception:
            _log.exception("silent exception in view_extent")
        return None

    def map_views_extent(self):
        try:
            return {str(k): [float(x) for x in e]
                    for k, e in (self._map_views or {}).items()
                    if e and len(e) == 4}
        except Exception:
            _log.exception("silent exception in map_views_extent")
            return {}

    def models_to_dict(self):
        try:
            return [dict(m) for m in (self._models or [])]
        except Exception:
            _log.exception("silent exception in models_to_dict")
            return []

    def snapshot_sig(self):
        out = []
        for lyr in self._layers:
            try:
                out.append((str(lyr.__dict__.get("_id", "")),
                            int(lyr.__dict__.get("_data_version", 0))))
            except Exception:
                _log.exception("silent exception in snapshot_sig")
                out.append(("", -1))
        return (self._file, tuple(sorted(out)))


def _norm_project_target(path):
    target = str(path or "").strip()
    if not target:
        raise ValueError("没有指定工程文件路径")
    if not os.path.splitext(target)[1]:
        target += ".ggs"
    parent = os.path.dirname(os.path.abspath(target))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    return target


def _write_project_file(project_like, target, views=None, session=None):
    _guard.assert_off_ui("io.project_io.save_project")
    data = project_to_dict(project_like, base_dir=os.path.dirname(
        os.path.abspath(target)), views=views, session=session)
    unsaved = data.pop("_unsaved_layers", [])
    try:
        _sig_fn = getattr(project_like, "snapshot_sig", None)
        sig = _sig_fn() if callable(_sig_fn) else None
    except Exception:
        _log.exception("silent exception in _write_project_file")
        sig = None

    tmp = target + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, target)
    _n_layers = 0
    for _v in (data.get("views") or []):
        _n_layers += len(_v.get("layers") or [])
    return {"path": target, "layers": _n_layers,
            "unsaved": unsaved, "sig": sig}


def save_project(project, path, views=None, session=None):
    _guard.assert_off_ui("io.project_io.save_project")
    target = _norm_project_target(path)
    if _guard.ui_mode() and _guard.on_ui_thread():
        from ..exec import task as _et
        frozen = _FrozenProject(project, views=views)
        return _et.submit(_write_project_file, frozen, target, views=views,
                          session=session, kind="io", name="保存工程",
                          protect=True)
    return _write_project_file(project, target, views=views, session=session)


def read_project_dict(path):
    src = str(path or "")
    if not os.path.exists(src):
        raise OSError("文件不存在：%s" % src)
    with io.open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("不是有效的工程文件")
    sig = data.get("signature")
    if sig and sig != APP_SIGNATURE:
        raise ValueError("不是本程序的工程文件：%s" % sig)
    if data.get("version") != PROJECT_FORMAT_VERSION:
        raise ValueError(
            "工程文件格式不兼容（版本 v%s）。请用新版 GmaGIS 重新打开并另存为 .ggs。"
            % (data.get("version"),))
    return data


def _abs_source(src, base_dir):
    if not src:
        return ""
    s = str(src)
    if os.path.isabs(s):
        return s
    return os.path.normpath(os.path.join(base_dir or "", s))


def _build_one_layer(ld, base_dir, missing_ok, errors, seen):
    from ..core.model.layer import assign_layer_id
    src = _abs_source(ld.get("source"), base_dir)
    name = str(ld.get("name") or os.path.basename(src))
    emb = ld.get("embedded")
    key = (str(ld.get("type") or ""),
           str(ld.get("source") or ""),
           str(ld.get("sub_layer") or ""),
           name)
    if isinstance(emb, dict):
        key = key + (str(emb.get("wkt") or emb.get("geometry") or ""),)
    lid = str(ld.get("id") or "")
    if key in seen:
        return seen[key]

    if ld.get("type") == "tile":
        lyr = tile_layer_from_snapshot(ld)
        if lyr is None:
            errors.append("%s：瓦片服务描述无效" % name)
            return None
        snap = dict(ld)
        snap["name"] = name
        try:
            _apply_snapshot(lyr, snap)
        except Exception as e:
            _log.exception("silent exception in _build_one_layer")
            errors.append("%s：显示状态未能恢复（%s）" % (name, e))
        if lid:
            try:
                assign_layer_id(lyr, lid)
            except Exception:
                _log.exception("silent exception in _build_one_layer")
        seen[key] = lyr
        return lyr

    if not src:
        if ld.get("type") == "vector" and isinstance(emb, dict):
            try:
                lyr = _layer_from_embedded(ld, emb)
            except Exception as e:
                _log.exception("silent exception in _build_one_layer")
                errors.append("%s：内嵌要素还原失败（%s）" % (name, e))
                return None
            snap = dict(ld)
            snap["name"] = name
            try:
                _apply_snapshot(lyr, snap)
            except Exception as e:
                _log.exception("silent exception in _build_one_layer")
                errors.append("%s：显示状态未能恢复（%s）" % (name, e))
            if lid:
                try:
                    assign_layer_id(lyr, lid)
                except Exception:
                    _log.exception("silent exception in _build_one_layer")
            seen[key] = lyr
            return lyr
        errors.append("%s：没有数据源路径" % name)
        return None

    if not os.path.exists(src):
        errors.append("%s：数据源不存在（%s）" % (name, src))
        if not missing_ok:
            return None
        return None
    try:
        lyr = load_file(src, layer=_resolve_sub_layer(src, ld) or None)
    except Exception as e:
        _log.exception("silent exception in _build_one_layer")
        errors.append("%s：加载异常 %s: %s" % (name, type(e).__name__, e))
        return None
    if lyr is None:
        errors.append("%s：不支持的数据源类型" % name)
        return None
    if not lyr.is_valid():
        errors.append("%s：%s" % (name, lyr.error()))
        return None

    snap = dict(ld)
    snap["name"] = name
    try:
        _apply_snapshot(lyr, snap)
    except Exception as e:
        _log.exception("silent exception in _build_one_layer")
        errors.append("%s：显示状态 / 样式未能恢复（%s）" % (name, e))
    if lid:
        try:
            assign_layer_id(lyr, lid)
        except Exception:
            _log.exception("silent exception in _build_one_layer")
    seen[key] = lyr
    return lyr


def _build_project_layers(path, missing_ok=True, on_step=None):
    base_dir = os.path.dirname(os.path.abspath(str(path)))
    data = read_project_dict(path)

    errors = []
    built_views = {}
    view_meta = {}
    total = 0
    seen = {}
    pool_snaps = data.get("layers_pool") or []
    pool_lyrs = {}

    raw_views = data.get("views")
    if not isinstance(raw_views, list) or not raw_views:
        # 不兜底：工程文件没有视图定义即损坏，直接报错（打开失败路径
        # 会弹条；启动期装载失败直接退出）。旧格式工程不再静默造空地图。
        raise ValueError(
            "工程文件缺少视图定义（views）：%s" % os.path.basename(str(path)))

    def _build_node(ld):
        nonlocal total
        if isinstance(ld, dict) and str(ld.get("kind") or "") == "group":
            kids = []
            for c in (ld.get("children") or []):
                n = _build_node(c)
                if n is not None:
                    kids.append(n)
            return {"kind": "group",
                    "name": str(ld.get("name") or ""),
                    "visible": bool(ld.get("visible", True)),
                    "expanded": bool(ld.get("expanded", True)),
                    "children": kids}
        total += 1
        if not (isinstance(ld, dict) and "lid" in ld and "name" not in ld):
            _log.warning("跳过非 v3 引用条目（旧格式工程不再支持）：%r", ld)
            return None
        try:
            lid = int(ld.get("lid"))
        except Exception:
            _log.exception("silent exception in _build_project_layers")
            return None
        ps = pool_snaps[lid] if 0 <= lid < len(pool_snaps) else None
        if not isinstance(ps, dict):
            return None
        nm = str(ps.get("name") or "")
        if on_step is not None:
            try:
                on_step(total - 1, total, nm)
            except Exception:
                _log.exception("silent exception in _build_project_layers")
        if lid not in pool_lyrs:
            pool_lyrs[lid] = _build_one_layer(
                ps, base_dir, missing_ok, errors, seen)
        lyr = pool_lyrs.get(lid)
        if lyr is None:
            return None
        return (lyr, nm, bool(ld.get("visible", True)))

    for v in raw_views:
        vid = str(v.get("id") or "map")
        view_meta[vid] = {
            "title": str(v.get("title") or ""),
            "crs": v.get("crs"),
            "extent": v.get("extent"),
            "display": v.get("display"),
        }
        built = []
        for ld in (v.get("layers") or []):
            node = _build_node(ld)
            if node is not None:
                built.append(node)
        built_views[vid] = built

    if on_step is not None:
        try:
            on_step(total, total, "")
        except Exception:
            _log.exception("silent exception in _build_project_layers")

    return {"built_views": built_views, "view_meta": view_meta,
            "errors": errors, "total": total, "data": data}


def _leaf_entries(nodes):
    out = []
    for nd in (nodes or []):
        if isinstance(nd, dict):
            out.extend(_leaf_entries(nd.get("children") or []))
        elif isinstance(nd, (tuple, list)) and nd and nd[0] is not None:
            out.append(nd)
    return out


def _apply_built(proj, res, path):
    built_views = res.pop("built_views", None)
    if built_views is None:
        return res
    proj.remove_all()
    proj.clear_layouts()
    view_meta = res.pop("view_meta", {}) or {}
    errors = res["errors"]
    loaded = 0
    seen_obj = set()
    for vid, built in built_views.items():
        leaves = _leaf_entries(built)
        seq = (reversed(leaves) if any(isinstance(e, dict)
                                       for e in (built or []))
               else leaves)
        for lyr, name, _vis in seq:
            if lyr is None or id(lyr) in seen_obj:
                continue
            seen_obj.add(id(lyr))
            try:
                proj.add_layer(lyr)
                loaded += 1
            except Exception as e:
                _log.exception("silent exception in _apply_built")
                errors.append("%s：加入工程失败（%s）" % (name, e))

    data = res.pop("data", {}) or {}
    res["session"] = data.get("session")


    try:
        proj.set_view_extent(data.get("extent"))
    except Exception as exc:
        _log.warning("工程视图范围恢复失败：%s", exc)
    try:
        proj.set_map_views_extent(data.get("map_views"))
    except Exception as exc:
        _log.warning("工程多视图范围恢复失败：%s", exc)
    try:
        if data.get("title"):
            proj.set_title(str(data["title"]))
    except Exception as exc:
        _log.warning("工程标题恢复失败：%s", exc)
    try:
        proj.load_layouts(data.get("layouts") or [])
    except Exception as e:
        _log.exception("silent exception in _apply_built")
        errors.append("出图版面未能恢复：%s" % e)
    try:
        _raw_models = data.get("models")
        if _raw_models:
            proj.load_models(_raw_models)
        elif data.get("model"):
            proj.load_models(
                [{"id": "model", "name": "模型",
                  "graph": data["model"]}])
    except Exception as e:
        _log.exception("silent exception in _apply_built")
        errors.append("模型构建器的图未能恢复：%s" % e)
    try:
        proj.set_file_name(os.path.abspath(str(path)))
    except Exception as exc:
        _log.warning("工程文件名恢复失败：%s", exc)
    try:
        proj.set_dirty(False)
    except Exception as exc:
        _log.warning("工程 dirty 标志复位失败：%s", exc)

    res["loaded"] = loaded
    res["built_views"] = built_views
    res["view_meta"] = view_meta
    return res


def load_project(path, project=None, missing_ok=True, progress=None):
    from ggis.core.model.project import GgsProject

    proj = project or GgsProject.instance()
    if _guard.ui_mode() and _guard.on_ui_thread():
        from ..exec import task as _et
        t = _et.submit(_build_project_layers, str(path), missing_ok=missing_ok,
                       kind="io", name="打开工程")
        t.on_done(lambda ev: _apply_built(proj, ev.get("result"), path))
        return t
    return _apply_built(proj, _build_project_layers(
        path, missing_ok=missing_ok, on_step=progress), path)


def describe_project(path):
    data = read_project_dict(path)
    n_layers = 0
    for v in (data.get("views") or []):
        n_layers += len(v.get("layers") or [])
    return {
        "title": str(data.get("title") or ""),
        "version": data.get("version"),
        "layers": n_layers,
        "layouts": len(data.get("layouts") or []),
        "crs": str(data.get("crs") or ""),
    }
