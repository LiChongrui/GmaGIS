# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from ggis.core.crs import convert_bounds, crs_transformer, crs_valid_extent, GgsCrs
from ggis.core.crs.extent import GgsRectangle
import logging
_log = logging.getLogger("gmagis")

__all__ = ["GgsProject", "GgsLayerCommand"]


class GgsLayerCommand(QUndoCommand):

    def __init__(self, text, do, undo, parent=None):
        super().__init__(text, parent)
        self._do = do
        self._undo = undo

    def redo(self):
        if self._do is not None:
            try:
                self._do()
            except Exception:
                _log.exception("silent exception in GgsLayerCommand.redo")

    def undo(self):
        if self._undo is not None:
            try:
                self._undo()
            except Exception:
                _log.exception("silent exception in GgsLayerCommand.undo")


class GgsProject(QObject):

    layerAdded = Signal(object)
    layerWillBeRemoved = Signal(str)
    layerRemoved = Signal(str)
    layerVisibilityChanged = Signal(object)
    layerOrderChanged = Signal()
    layersChanged = Signal()
    layoutsChanged = Signal()
    modelsChanged = Signal()

    _inst = None

    def __init__(self):
        super().__init__()
        self._layers = []
        self._title = ""
        self._file = ""
        self._dirty = False
        self._saved_fingerprint = None
        self._fingerprint_provider = None
        self._layouts = []
        self._models = []
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(100)

    @classmethod
    def instance(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def undo_stack(self):
        return self._undo_stack

    def push_layer_command(self, text, do, undo):
        self._undo_stack.push(GgsLayerCommand(text, do, undo))

    def clear_undo(self):
        try:
            self._undo_stack.clear()
        except Exception:
            _log.exception("silent exception in clear_undo")

    def layers(self):
        return list(self._layers)

    def layer_tree_layers(self):
        return list(reversed(self._layers))

    def count(self):
        return len(self._layers)

    def layer_by_id(self, layer_id):
        for lyr in self._layers:
            if lyr.id() == layer_id:
                return lyr
        return None

    def layer_by_name(self, name):
        for lyr in self._layers:
            if lyr.name() == name:
                return lyr
        return None

    def visible_layers(self):
        return [l for l in self._layers if l.is_visible() and l.is_valid()]

    def add_layer(self, layer, index=None, basemap=False):
        if layer is None:
            return None
        if index is None or index >= len(self._layers):
            self._layers.append(layer)
        else:
            self._layers.insert(max(0, int(index)), layer)
        self._dirty = True
        try:
            self.layerAdded.emit(layer)
            self.layersChanged.emit()
        except Exception:
            _log.exception("silent exception in add_layer")
        return layer

    def remove_layer(self, layer_or_id, close=True):
        lyr = layer_or_id if hasattr(layer_or_id, "id") \
            else self.layer_by_id(layer_or_id)
        if lyr is None or lyr not in self._layers:
            return False
        lid = lyr.id()
        try:
            self.layerWillBeRemoved.emit(lid)
        except Exception:
            _log.exception("silent exception in remove_layer")
        try:
            self._layers.remove(lyr)
        except ValueError:
            exc_note("remove_layer @ ggis/core/model/project.py:224")
            return False
        if close:
            _close = getattr(lyr, "close", None)
            if callable(_close):
                try:
                    _close()
                except Exception:
                    _log.exception("silent exception in remove_layer")
        try:
            from .selection import GgsSelection
            GgsSelection.instance().forget(lyr)
        except Exception:
            _log.exception("silent exception in remove_layer")
        self._dirty = True
        try:
            self.layerRemoved.emit(lid)
            self.layersChanged.emit()
        except Exception:
            _log.exception("silent exception in remove_layer")
        return True

    def remove_all(self, close=True):
        for lyr in list(self._layers):
            self.remove_layer(lyr, close=close)

    clear = remove_all

    def move_layer(self, layer, delta):
        try:
            i = self._layers.index(layer)
        except ValueError:
            exc_note("move_layer @ ggis/core/model/project.py:263")
            return False
        j = i + int(delta)
        if not (0 <= j < len(self._layers)):
            return False
        self._layers.pop(i)
        self._layers.insert(j, layer)
        self._dirty = True
        try:
            self.layerOrderChanged.emit()
            self.layersChanged.emit()
        except Exception:
            _log.exception("silent exception in move_layer")
        return True

    def reorder_by_ids(self, ids):
        by_id = {l.id(): l for l in self._layers}
        new = [by_id[i] for i in ids if i in by_id]
        for l in self._layers:
            if l not in new:
                new.append(l)
        if new == self._layers:
            return False
        self._layers = new
        self._dirty = True
        try:
            self.layerOrderChanged.emit()
            self.layersChanged.emit()
        except Exception:
            _log.exception("silent exception in reorder_by_ids")
        return True

    def set_layer_visible(self, layer, on):
        if layer is None:
            return False
        try:
            changed = bool(layer.is_visible()) != bool(on)
        except Exception:
            _log.exception("silent exception in set_layer_visible")
            changed = True
        try:
            layer.set_visible(bool(on))
        except Exception:
            _log.exception("silent exception in set_layer_visible")
            return False
        if not changed:
            return True
        self._dirty = True
        try:
            self.layerVisibilityChanged.emit(layer)
        except Exception:
            _log.exception("silent exception in set_layer_visible")
        return True

    def full_extent(self, visible_only=False, dst_crs=None, include_tiles=True):
        r = GgsRectangle()
        src = self.visible_layers() if visible_only else self._layers
        return self.extent_of_layers(src, dst_crs, include_tiles=include_tiles)

    def extent_of_layers(self, layers, dst_crs=None, include_tiles=True):
        r = GgsRectangle()
        for lyr in (layers or ()):
            if not lyr.is_valid():
                continue
            if lyr.is_table():
                continue
            if not include_tiles:
                fn = getattr(lyr, "is_tile", None)
                if callable(fn) and fn():
                    continue
            try:
                e = lyr.extent()
            except Exception:
                _log.exception("silent exception in extent_of_layers")
                continue
            if e is None or e.is_empty():
                continue
            if dst_crs is not None:
                try:
                    src_crs = lyr.crs()
                except Exception:
                    _log.exception("silent exception in extent_of_layers")
                    src_crs = None
                b = convert_bounds((e.xmin, e.ymin, e.xmax, e.ymax),
                                   crs_transformer(src_crs, dst_crs))
                if b is None:
                    continue
                e = GgsRectangle(b[0], b[1], b[2], b[3])
            r.combine_extent_with(e)
        if r.is_empty() and dst_crs is not None:
            aou = crs_valid_extent(dst_crs)
            if aou is not None:
                try:
                    geo = GgsCrs.from_epsg(4326)
                    b = convert_bounds(aou, crs_transformer(geo, dst_crs))
                    if b is not None:
                        r = GgsRectangle(b[0], b[1], b[2], b[3])
                except Exception:
                    _log.exception("silent exception in extent_of_layers")
        return r

    def layer_extent(self, layer, dst_crs=None):
        from ggis.core.crs.extent import layer_extent as _impl
        r = _impl(layer, dst_crs)
        return r if r is not None else GgsRectangle()

    @staticmethod
    def _is_tile_layer(layer):
        try:
            fn = getattr(layer, "is_tile", None)
            return bool(fn()) if callable(fn) else False
        except Exception:
            _log.exception("silent exception in _is_tile_layer")
            return False

    def title(self):
        return self._title

    def set_title(self, t):
        self._title = str(t or "")
        self._dirty = True

    def file_name(self):
        return self._file

    def set_file_name(self, p):
        self._file = str(p or "")

    def is_dirty(self):
        if not self._dirty:
            return False
        fp = self._saved_fingerprint
        if fp is None:
            return True
        fn = self._fingerprint_provider
        if fn is None:
            return True
        try:
            cur = fn()
        except Exception:
            _log.exception("silent exception in is_dirty")
            return True
        if cur is None:
            return True
        return cur != fp

    def set_dirty(self, on):
        self._dirty = bool(on)

    def set_fingerprint_provider(self, fn):
        self._fingerprint_provider = fn

    def set_saved_fingerprint(self, fp):
        self._saved_fingerprint = fp

    def saved_fingerprint(self):
        return self._saved_fingerprint

    def layouts(self):
        return list(self._layouts)

    def layout_count(self):
        return len(self._layouts)

    def layout_by_id(self, layout_id):
        for lay in self._layouts:
            if lay.id == layout_id:
                return lay
        return None

    def layout_by_name(self, name):
        for lay in self._layouts:
            if lay.name == name:
                return lay
        return None

    def add_layout(self, layout, index=None):
        if layout is None:
            return None
        if self.layout_by_id(getattr(layout, "id", None)) is not None:
            return layout
        if index is None:
            self._layouts.append(layout)
        else:
            self._layouts.insert(max(0, int(index)), layout)
        self._dirty = True
        try:
            self.layoutsChanged.emit()
        except Exception:
            _log.exception("silent exception in add_layout")
        return layout

    def remove_layout(self, layout_or_id):
        lid = layout_or_id if isinstance(layout_or_id, str) \
            else getattr(layout_or_id, "id", None)
        for i, lay in enumerate(self._layouts):
            if lay.id == lid:
                self._layouts.pop(i)
                self._dirty = True
                try:
                    self.layoutsChanged.emit()
                except Exception:
                    _log.exception("silent exception in remove_layout")
                return True
        return False

    def clear_layouts(self):
        if not self._layouts:
            return
        self._layouts = []
        try:
            self.layoutsChanged.emit()
        except Exception:
            _log.exception("silent exception in clear_layouts")

    def layouts_to_dict(self):
        out = []
        for lay in self._layouts:
            try:
                out.append(lay.to_dict())
            except Exception:
                _log.exception("silent exception in layouts_to_dict")
                continue
        return out

    def load_layouts(self, raw):
        from ggis.core.model.layout_model import Layout
        self._layouts = []
        for d in raw or []:
            try:
                self._layouts.append(Layout.from_dict(d))
            except Exception:
                _log.exception("silent exception in load_layouts")
                continue
        try:
            self.layoutsChanged.emit()
        except Exception:
            _log.exception("silent exception in load_layouts")
        return len(self._layouts)

    def view_extent(self):
        return getattr(self, "_view_extent", None)

    def set_view_extent(self, ext):
        v = None
        try:
            v = [float(x) for x in (ext or ())]
        except Exception:
            _log.exception("silent exception in set_view_extent")
            v = None
        if v is not None and len(v) != 4:
            v = None
        self._view_extent = v

    def map_views_extent(self):
        v = getattr(self, "_map_views_extent", None)
        if not isinstance(v, dict):
            return {}
        out = {}
        for k, e in v.items():
            try:
                out[str(k)] = [float(x) for x in e]
            except Exception:
                _log.exception("silent exception in map_views_extent")
                continue
        return out

    def set_map_views_extent(self, d):
        if not d:
            self._map_views_extent = {}
            return
        try:
            self._map_views_extent = {
                str(k): [float(x) for x in e]
                for k, e in d.items()
                if e and len(e) == 4
            }
        except Exception:
            _log.exception("silent exception in set_map_views_extent")
            self._map_views_extent = {}

    def model_dict(self):
        try:
            first = self._models[0] if self._models else None
            return dict(first["graph"]) if first else {}
        except Exception:
            _log.exception("silent exception in model_dict")
            return {}

    def set_model_dict(self, raw):
        try:
            if self._models:
                self._models[0]["graph"] = dict(raw or {})
            else:
                self.add_model("model", "模型", raw)
            return len((raw or {}).get("nodes") or [])
        except Exception:
            _log.exception("silent exception in set_model_dict")
            return 0

    def models(self):
        return list(self._models)

    def model_by_id(self, mid):
        for m in self._models:
            if m.get("id") == mid:
                return m
        return None

    def add_model(self, mid, name, graph=None, index=None):
        if self.model_by_id(mid) is not None:
            return self.model_by_id(mid)
        entry = {"id": str(mid), "name": str(name or "模型"),
                 "graph": dict(graph or {})}
        if index is None:
            self._models.append(entry)
        else:
            self._models.insert(max(0, int(index)), entry)
        self._dirty = True
        try:
            self.modelsChanged.emit()
        except Exception:
            _log.exception("silent exception in add_model")
        return entry

    def remove_model(self, mid):
        for i, m in enumerate(self._models):
            if m.get("id") == mid:
                self._models.pop(i)
                self._dirty = True
                try:
                    self.modelsChanged.emit()
                except Exception:
                    _log.exception("silent exception in remove_model")
                return True
        return False

    def rename_model(self, mid, name):
        m = self.model_by_id(mid)
        if m is not None:
            m["name"] = str(name or m.get("name") or "模型")
            self._dirty = True

    def model_graph(self, mid):
        m = self.model_by_id(mid)
        return dict(m["graph"]) if m else {}

    def set_model_graph(self, mid, graph):
        m = self.model_by_id(mid)
        if m is not None:
            m["graph"] = dict(graph or {})

    def clear_models(self):
        if not self._models:
            return
        self._models = []
        self._dirty = True
        try:
            self.modelsChanged.emit()
        except Exception:
            _log.exception("silent exception in clear_models")

    def models_to_dict(self):
        return [dict(m) for m in self._models]

    def load_models(self, raw):
        self._models = []
        for d in raw or []:
            try:
                self._models.append({
                    "id": str(d.get("id") or "模型"),
                    "name": str(d.get("name") or "模型"),
                    "graph": dict(d.get("graph") or {}),
                })
            except Exception:
                _log.exception("silent exception in load_models")
                continue
        try:
            self.modelsChanged.emit()
        except Exception:
            _log.exception("silent exception in load_models")
