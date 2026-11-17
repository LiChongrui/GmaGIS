# -*- coding: utf-8 -*-

from __future__ import annotations

import weakref

from PySide6.QtCore import QObject, Signal

from ggis.core.crs.extent import GgsRectangle
import logging
_log = logging.getLogger("gmagis")

__all__ = ["GgsSelection"]


class _SelBus(QObject):
    anyChanged = Signal()


_bus = _SelBus()


class GgsSelection(QObject):

    changed = Signal()
    layerSelectionChanged = Signal(str)

    _active = None
    _instances = weakref.WeakSet()

    def __init__(self):
        super().__init__()
        self._layers = {}
        self._data = {}
        GgsSelection._instances.add(self)

    @classmethod
    def any_changed_signal(cls):
        return _bus.anyChanged

    @classmethod
    def instance(cls):
        if cls._active is None or cls._active not in cls._instances:
            inst = cls()
            cls._active = inst
        return cls._active

    @classmethod
    def set_active(cls, inst):
        if inst is None or not isinstance(inst, GgsSelection):
            return
        cls._instances.add(inst)
        if cls._active is inst:
            return
        cls._active = inst
        try:
            _bus.anyChanged.emit()
        except Exception:
            _log.exception("silent exception in set_active")

    @classmethod
    def _all_instances(cls):
        return list(cls._instances)

    def dispose(self):
        GgsSelection._instances.discard(self)
        if GgsSelection._active is self:
            rest = [i for i in GgsSelection._instances if i is not self]
            GgsSelection._active = rest[0] if rest else None
            try:
                _bus.anyChanged.emit()
            except Exception:
                _log.exception("silent exception in dispose")

    def _fids_of(self, layer):
        lid = layer.id()
        s = self._data.get(lid)
        if s is None:
            s = set()
            self._data[lid] = s
        return s

    def register(self, layer):
        if layer is not None:
            self._layers[layer.id()] = layer

    def forget(self, layer_or_id):
        lid = layer_or_id if isinstance(layer_or_id, str) else \
            layer_or_id.id()
        for inst in list(GgsSelection._instances):
            inst._layers.pop(lid, None)
            inst._data.pop(lid, None)
        try:
            _bus.anyChanged.emit()
        except Exception:
            _log.exception("silent exception in forget")

    def fids(self, layer) -> set:
        return set(self._fids_of(layer))

    def count(self, layer) -> int:
        return len(self._fids_of(layer))

    def total(self) -> int:
        return sum(len(s) for s in self._data.values())

    def is_selected(self, layer, fid) -> bool:
        return fid in self._fids_of(layer)

    def selected_layers(self):
        return [l for l in self._layers.values() if self._fids_of(l)]

    def _notify(self, layer):
        try:
            self.layerSelectionChanged.emit(layer.id())
            self.changed.emit()
            _bus.anyChanged.emit()
        except Exception:
            _log.exception("silent exception in _notify")

    def set_fids(self, layer, fids):
        if layer is None:
            return
        self.register(layer)
        s = self._fids_of(layer)
        new = {int(f) for f in fids}
        if new == s:
            return
        s.clear()
        s.update(new)
        self._notify(layer)

    def add_fids(self, layer, fids):
        if layer is None:
            return
        self.register(layer)
        s = self._fids_of(layer)
        new = {int(f) for f in fids} - s
        if not new:
            return
        s.update(new)
        self._notify(layer)

    def remove_fids(self, layer, fids):
        if layer is None:
            return
        s = self._fids_of(layer)
        gone = {int(f) for f in fids} & s
        if not gone:
            return
        s.difference_update(gone)
        self._notify(layer)

    def toggle_fids(self, layer, fids):
        if layer is None:
            return
        self.register(layer)
        s = self._fids_of(layer)
        for f in fids:
            f = int(f)
            if f in s:
                s.discard(f)
            else:
                s.add(f)
        self._notify(layer)

    @staticmethod
    def _visible_fids(layer):
        n = int(layer.feature_count() or 0)
        try:
            return layer.filter_fids(range(n))
        except Exception:
            _log.exception("silent exception in _visible_fids")
            return range(n)

    def select_all(self, layer):
        if layer is None:
            return
        self.set_fids(layer, self._visible_fids(layer))

    def invert(self, layer):
        if layer is None:
            return
        cur = self._fids_of(layer)
        self.set_fids(layer, [i for i in self._visible_fids(layer)
                              if i not in cur])

    def clear(self, layer=None):
        if layer is not None:
            self.register(layer)
            self._fids_of(layer).clear()
            self._notify(layer)
            return
        for lyr in list(self._layers.values()):
            self._fids_of(lyr).clear()
            try:
                self.layerSelectionChanged.emit(lyr.id())
            except Exception:
                _log.exception("silent exception in clear")
        try:
            self.changed.emit()
            _bus.anyChanged.emit()
        except Exception:
            _log.exception("silent exception in clear")

    def features(self, layer):
        out = []
        if layer is None:
            return out
        s = self._fids_of(layer)
        if not s:
            return out
        for fid in sorted(s):
            try:
                out.append((fid,) + tuple(layer.feature(fid)))
            except Exception:
                _log.exception("silent exception in features")
                continue
        return out

    def extent(self, layer=None):
        rect = GgsRectangle()
        layers = [layer] if layer is not None else list(self._layers.values())
        for lyr in layers:
            try:
                geoms = lyr.geoms()
            except Exception:
                _log.exception("silent exception in extent")
                continue
            for fid in self._fids_of(lyr):
                if 0 <= fid < len(geoms):
                    g = geoms[fid]
                    if g is None or getattr(g, "is_empty", True):
                        continue
                    try:
                        rect.combine_extent_with(GgsRectangle.from_shapely(g))
                    except Exception:
                        _log.exception("silent exception in extent")
                        continue
        return rect

    def summary(self):
        return [(l.name(), self.count(l))
                for l in self.selected_layers()]
