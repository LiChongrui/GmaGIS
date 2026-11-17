# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from ggis.core.app.i18n import tr as _tr
from .field import GgsField
from .layer import bump_data_version as _bump_data_version
from .layer import data_version as _data_version
from .layer import freeze_layer as _freeze_layer
from ggis.core.analysis.spatial import GgsEditableIndex, install_editable_index
import logging
_log = logging.getLogger("gmagis")

__all__ = ["EditSession", "TopologyIssue", "TOPOLOGY_OK",
           "TOPOLOGY_SELF_INTERSECTION", "TOPOLOGY_INVALID",
           "TOPOLOGY_ZERO_LENGTH", "TOPOLOGY_DUPLICATE_POINT",
           "TOPOLOGY_EMPTY"]


TOPOLOGY_OK = "ok"
TOPOLOGY_EMPTY = "empty"
TOPOLOGY_INVALID = "invalid"
TOPOLOGY_SELF_INTERSECTION = "self_intersection"
TOPOLOGY_ZERO_LENGTH = "zero_length"
TOPOLOGY_DUPLICATE_POINT = "duplicate_point"

_TOPOLOGY_LABELS = {
    TOPOLOGY_EMPTY: "空几何",
    TOPOLOGY_INVALID: "几何无效",
    TOPOLOGY_SELF_INTERSECTION: "自相交",
    TOPOLOGY_ZERO_LENGTH: "长度或面积为 0",
    TOPOLOGY_DUPLICATE_POINT: "存在重复顶点",
}


@dataclass
class TopologyIssue:

    fid: int
    kind: str
    message: str
    location: Optional[Tuple[float, float]] = None

    def label(self):
        return _TOPOLOGY_LABELS.get(self.kind, self.kind)

    def __str__(self):
        loc = ""
        if self.location:
            loc = " @(%.4f, %.4f)" % self.location
        return "要素 %d：%s%s" % (self.fid + 1, self.message, loc)


_UNSET = object()


class _CmdBase(QUndoCommand):

    def __init__(self, session, text):
        super().__init__(text)
        self.session = session
        self.changed_fids: List[int] = []
        self.removed_fids: List[int] = []
        self.structural = False

    def _redo_body(self):
        raise NotImplementedError

    def _undo_body(self):
        raise NotImplementedError

    def redo(self):
        self.changed_fids = []
        self.removed_fids = []
        self.structural = False
        self._redo_body()
        self._finish()

    def undo(self):
        self.changed_fids = []
        self.removed_fids = []
        self.structural = False
        self._undo_body()
        self._finish()

    def _finish(self):
        self.session._after_change(self.changed_fids, self.removed_fids,
                                   self.structural)


class _AddFeatureCommand(_CmdBase):
    def __init__(self, session, geom, attrs):
        super().__init__(session, _tr("添加要素"))
        self.geom = geom
        self.attrs = dict(attrs or {})
        self.fid = -1

    def _redo_body(self):
        s = self.session
        if self.fid < 0:
            s._geoms.append(self.geom)
            s._attrs.append(self.attrs)
            self.fid = len(s._geoms) - 1
        else:
            s._geoms.insert(self.fid, self.geom)
            s._attrs.insert(self.fid, self.attrs)
        self.changed_fids = [self.fid]
        self.structural = True

    def _undo_body(self):
        s = self.session
        if 0 <= self.fid < len(s._geoms):
            del s._geoms[self.fid]
            del s._attrs[self.fid]
        self.removed_fids = [self.fid]
        self.structural = True


class _DeleteFeaturesCommand(_CmdBase):
    def __init__(self, session, fids):
        fids = sorted({int(f) for f in fids})
        super().__init__(session, _tr("删除 %d 个要素").format(len(fids)))
        self.fids = fids
        self.saved: List[Tuple[int, Any, Dict[str, Any]]] = []

    def _redo_body(self):
        s = self.session
        if not self.saved:
            self.saved = [(f, s._geoms[f], s._attrs[f]) for f in self.fids
                          if 0 <= f < len(s._geoms)]
        for f in sorted(self.fids, reverse=True):
            if 0 <= f < len(s._geoms):
                del s._geoms[f]
                del s._attrs[f]
        self.removed_fids = list(self.fids)
        self.structural = True

    def _undo_body(self):
        s = self.session
        for f, g, a in self.saved:
            s._geoms.insert(f, g)
            s._attrs.insert(f, a)
        self.changed_fids = [f for f, _g, _a in self.saved]
        self.structural = True


class _SetGeometryCommand(_CmdBase):
    def __init__(self, session, fid, geom, text=None):
        super().__init__(session, text or _tr("修改几何"))
        self.fid = int(fid)
        self.new = geom
        self.old = _UNSET

    def _redo_body(self):
        s = self.session
        if not (0 <= self.fid < len(s._geoms)):
            return
        if self.old is _UNSET:
            self.old = s._geoms[self.fid]
        s._geoms[self.fid] = self.new
        self.changed_fids = [self.fid]

    def _undo_body(self):
        s = self.session
        if self.old is _UNSET or not (0 <= self.fid < len(s._geoms)):
            return
        s._geoms[self.fid] = self.old
        self.changed_fids = [self.fid]


class _SetAttributeCommand(_CmdBase):
    def __init__(self, session, fid, name, value):
        super().__init__(session,
                         _tr("修改属性 {0}").format(str(name)))
        self.fid = int(fid)
        self.name = str(name)
        self.value = value
        self.old = _UNSET
        self.existed = False

    def _redo_body(self):
        s = self.session
        if not (0 <= self.fid < len(s._attrs)):
            return
        a = s._attrs[self.fid]
        if self.old is _UNSET:
            self.existed = self.name in a
            self.old = a.get(self.name)
        a[self.name] = self.value
        self.changed_fids = [self.fid]

    def _undo_body(self):
        s = self.session
        if self.old is _UNSET or not (0 <= self.fid < len(s._attrs)):
            return
        a = s._attrs[self.fid]
        if self.existed:
            a[self.name] = self.old
        else:
            a.pop(self.name, None)
        self.changed_fids = [self.fid]


class _AddFieldCommand(_CmdBase):
    def __init__(self, session, field, default=None):
        super().__init__(session, _tr("添加字段 {0}").format(str(field.name)))
        self.field = field
        self.default = default

    def _redo_body(self):
        s = self.session
        fields = s._layer._fields
        if any(getattr(f, "name", None) == self.field.name for f in fields):
            return
        fields.append(self.field)
        for a in s._attrs:
            if isinstance(a, dict):
                a.setdefault(self.field.name, self.default)
        self.changed_fids = list(range(len(s._attrs)))
        self.structural = True

    def _undo_body(self):
        s = self.session
        fields = s._layer._fields
        for i in range(len(fields) - 1, -1, -1):
            if getattr(fields[i], "name", None) == self.field.name:
                del fields[i]
                break
        for a in s._attrs:
            if isinstance(a, dict):
                a.pop(self.field.name, None)
        self.changed_fids = list(range(len(s._attrs)))
        self.structural = True


class _DeleteFieldCommand(_CmdBase):
    def __init__(self, session, name):
        super().__init__(session, _tr("删除字段 {0}").format(str(name)))
        self.name = str(name)
        self._idx = -1
        self._removed = None
        self._saved = None

    def _redo_body(self):
        s = self.session
        fields = s._layer._fields
        self._idx = -1
        self._removed = None
        for i, f in enumerate(fields):
            if getattr(f, "name", None) == self.name:
                self._idx = i
                self._removed = f
                break
        if self._idx >= 0:
            del fields[self._idx]
        self._saved = [(i, a.get(self.name))
                       for i, a in enumerate(s._attrs) if isinstance(a, dict)]
        for a in s._attrs:
            if isinstance(a, dict):
                a.pop(self.name, None)
        self.changed_fids = list(range(len(s._attrs)))
        self.structural = True

    def _undo_body(self):
        s = self.session
        if self._removed is not None and self._idx >= 0:
            fields = s._layer._fields
            if self._idx > len(fields):
                self._idx = len(fields)
            fields.insert(self._idx, self._removed)
        for i, v in (self._saved or []):
            if 0 <= i < len(s._attrs) and isinstance(s._attrs[i], dict):
                s._attrs[i][self.name] = v
        self.changed_fids = list(range(len(s._attrs)))
        self.structural = True


class _RenameFieldCommand(_CmdBase):
    def __init__(self, session, old, new):
        super().__init__(session,
                         _tr("重命名字段 {0} → {1}").format(str(old), str(new)))
        self.old = str(old)
        self.new = str(new)
        self._field = None

    def _redo_body(self):
        s = self.session
        for f in s._layer._fields:
            if getattr(f, "name", None) == self.old:
                self._field = f
                break
        if self._field is not None:
            self._field.name = self.new
        for a in s._attrs:
            if isinstance(a, dict) and self.old in a:
                a[self.new] = a.pop(self.old)
        self.changed_fids = list(range(len(s._attrs)))
        self.structural = True

    def _undo_body(self):
        s = self.session
        if self._field is not None:
            self._field.name = self.old
        for a in s._attrs:
            if isinstance(a, dict) and self.new in a:
                a[self.old] = a.pop(self.new)
        self.changed_fids = list(range(len(s._attrs)))
        self.structural = True


class _SetAttributesBulkCommand(_CmdBase):
    def __init__(self, session, changes):
        super().__init__(session, _tr("批量修改属性"))
        self.changes = {int(f): dict(v) for f, v in (changes or {}).items()}
        self._old = None

    def _redo_body(self):
        s = self.session
        self._old = {}
        for fid, kvs in self.changes.items():
            if not (0 <= fid < len(s._attrs)):
                continue
            a = s._attrs[fid]
            saved = {}
            for name, val in kvs.items():
                saved[name] = a.get(name)
                a[name] = val
            self._old[fid] = saved
        self.changed_fids = list(self.changes.keys())
        self.structural = False

    def _undo_body(self):
        s = self.session
        for fid, saved in (self._old or {}).items():
            if not (0 <= fid < len(s._attrs)):
                continue
            a = s._attrs[fid]
            for name, val in saved.items():
                a[name] = val
        self.changed_fids = list((self._old or {}).keys())
        self.structural = False


def _write_layer_job(snap, target):
    from ggis.io.vector_io import write_layer_atomic
    return write_layer_atomic(snap, target)


class EditSession(QObject):

    changed = Signal()
    structureChanged = Signal()
    dirtyChanged = Signal(bool)
    committed = Signal(str)

    def __init__(self, layer, snapper=None, parent=None):
        super().__init__(parent)
        self._layer = layer
        self._snapper = snapper
        self._stack = QUndoStack(self)
        self._stack.setUndoLimit(0)
        self._dirty = False
        self._active = False
        self._saved: Optional[List[Any]] = None
        self._index: Optional[GgsEditableIndex] = None
        self._commit_task = None
        self._batch_depth = 0
        self._batch_touched = False
        self._batch_structural = False
        self._batch_changed: set = set()
        self._batch_removed: set = set()
        self._stack.cleanChanged.connect(self._on_clean_changed)

    def layer(self):
        return self._layer

    def undo_stack(self):
        return self._stack

    def is_active(self):
        return self._active

    def is_dirty(self):
        return self._dirty

    def snapper(self):
        return self._snapper

    def set_snapper(self, snapper):
        self._snapper = snapper

    def start(self):
        if self._active:
            return
        self._active = True
        self._index = install_editable_index(self._layer)
        self._stack.clear()
        self._set_dirty(False)
        if self._snapper is not None:
            try:
                self._snapper.register_layer(self._layer)
            except Exception:
                _log.exception("silent exception in start")

    def stop(self):
        if not self._active:
            return
        if self._snapper is not None:
            try:
                self._snapper.unregister_layer(self._layer)
            except Exception:
                _log.exception("silent exception in stop")
        if self._index is not None:
            self._index.detach()
            self._index = None
        self._active = False

    @property
    def _geoms(self):
        return self._layer.geoms()

    @property
    def _attrs(self):
        return self._layer.attrs()

    def _set_dirty(self, on):
        on = bool(on)
        if on != self._dirty:
            self._dirty = on
            self.dirtyChanged.emit(on)

    def _after_change(self, changed=None, removed=None, structural=False):
        changed = list(changed or [])
        removed = list(removed or [])
        structural = bool(structural or removed)

        self._layer.invalidate_extent()
        _bump_data_version(self._layer)
        self._set_dirty(True)

        idx = self._index
        if idx is not None:
            if structural:
                idx.mark_dirty()
            else:
                geoms = self._geoms
                for fid in changed:
                    if 0 <= fid < len(geoms):
                        idx.update(fid, geoms[fid])

        if self._snapper is not None:
            try:
                if structural:
                    self._snapper.invalidate(self._layer)
                elif changed:
                    self._snapper.rebuild(self._layer.id(), changed)
            except Exception:
                _log.exception("silent exception in _after_change")

        if self._batch_depth > 0:
            self._batch_touched = True
            self._batch_structural = bool(self._batch_structural or structural)
            self._batch_changed.update(changed)
            self._batch_removed.update(removed)
            return

        self.changed.emit()
        if structural:
            self.structureChanged.emit()

    def begin_batch(self):
        self._batch_depth += 1

    def end_batch(self):
        if self._batch_depth > 0:
            self._batch_depth -= 1
        if self._batch_depth > 0 or not self._batch_touched:
            return
        structural = bool(self._batch_structural)
        self._batch_touched = False
        self._batch_structural = False
        self._batch_changed.clear()
        self._batch_removed.clear()
        self.changed.emit()
        if structural:
            self.structureChanged.emit()

    def _run(self, cmd):
        if not self._active:
            self.start()
        self._stack.push(cmd)
        return cmd

    def add_feature(self, geom, attrs=None):
        cmd = _AddFeatureCommand(self, geom, attrs or {})
        self._run(cmd)
        return cmd.fid

    def delete_features(self, fids):
        fids = [int(f) for f in (fids or [])]
        if not fids:
            return 0
        self._run(_DeleteFeaturesCommand(self, fids))
        return len(fids)

    def replace_features(self, mapping, text=""):
        from .geometry import explode

        dels, adds = [], []
        for fid, geoms in (mapping or []):
            try:
                fid = int(fid)
            except Exception:
                _log.exception("silent exception in replace_features")
                continue
            if not (0 <= fid < len(self._geoms)):
                continue
            parts = explode(geoms)
            parts = [g for g in parts
                     if g is not None and not getattr(g, "is_empty", False)]
            if not parts:
                continue
            attrs = self._attrs[fid] if fid < len(self._attrs) else {}
            dels.append(fid)
            for g in parts:
                adds.append((g, dict(attrs or {})))
        if not dels:
            return 0

        cmds = [_DeleteFeaturesCommand(self, dels)]
        for g, a in adds:
            cmds.append(_AddFeatureCommand(self, g, a))
        if not self._active:
            self.start()
        self._stack.beginMacro(
            text or _tr("替换 {0} 个要素").format(len(dels)))
        for c in cmds:
            self._stack.push(c)
        self._stack.endMacro()
        return len(adds)

    def set_geometry(self, fid, geom):
        self._run(_SetGeometryCommand(self, fid, geom))

    def set_attribute(self, fid, name, value):
        self._run(_SetAttributeCommand(self, fid, name, value))

    def add_field(self, field, default=None):
        self._run(_AddFieldCommand(self, field, default))

    def delete_field(self, name):
        self._run(_DeleteFieldCommand(self, name))

    def rename_field(self, old, new):
        self._run(_RenameFieldCommand(self, old, new))

    def set_attributes_bulk(self, changes):
        if not changes:
            return
        self._run(_SetAttributesBulkCommand(self, changes))

    def move_features(self, fids, dx, dy):
        from shapely import affinity
        cmds = []
        for fid in fids or []:
            fid = int(fid)
            if not (0 <= fid < len(self._geoms)):
                continue
            cmds.append(_SetGeometryCommand(
                self, fid, affinity.translate(self._geoms[fid], dx, dy),
                text=_tr("移动要素")))
        if not cmds:
            return
        if not self._active:
            self.start()
        self._stack.beginMacro(_tr("移动 %d 个要素").format(len(cmds)))
        for c in cmds:
            self._stack.push(c)
        self._stack.endMacro()

    def _ring_coords(self, fid, part=0, ring=0):
        from .snapping import _iter_parts
        if not (0 <= fid < len(self._geoms)):
            return None
        geom = self._geoms[fid]
        is_poly = getattr(geom, "geom_type", "").startswith(("Polygon",))
        for p, r, coords in _iter_parts(geom) or ():
            if p == part and r == ring:
                closed = len(coords) > 2 and coords[0] == coords[-1]
                return list(coords), closed, is_poly
        return None

    def _rebuild_geom(self, geom, part, ring, coords):
        from shapely.geometry import (LineString, MultiLineString, MultiPolygon, Polygon)

        gt = getattr(geom, "geom_type", "")
        if gt == "LineString":
            return LineString(coords)
        if gt == "Polygon":
            ext, holes = list(geom.exterior.coords), \
                [list(r.coords) for r in geom.interiors]
            if ring == 0:
                ext = coords
            else:
                if ring - 1 < len(holes):
                    holes[ring - 1] = coords
            return Polygon(ext, holes)
        if gt == "MultiLineString":
            parts = [list(g.coords) for g in geom.geoms]
            if part < len(parts):
                parts[part] = coords
            return MultiLineString(parts)
        if gt == "MultiPolygon":
            polys = list(geom.geoms)
            if part < len(polys):
                polys[part] = self._rebuild_geom(polys[part], 0, ring, coords)
            return MultiPolygon(polys)
        return geom

    def preview_geometry(self, fid, index, x, y, part=0, ring=0):
        got = self._ring_coords(fid, part, ring)
        if got is None:
            return None
        coords, closed, _is_poly = got
        if not (0 <= index < len(coords)):
            return None
        coords[index] = (float(x), float(y))
        if closed and index == 0:
            coords[-1] = (float(x), float(y))
        elif closed and index == len(coords) - 1:
            coords[0] = (float(x), float(y))
        return self._rebuild_geom(self._geoms[fid], part, ring, coords)

    def move_vertex(self, fid, index, x, y, part=0, ring=0):
        got = self._ring_coords(fid, part, ring)
        if got is None:
            return False
        coords, closed, _is_poly = got
        if not (0 <= index < len(coords)):
            return False
        coords[index] = (float(x), float(y))
        if closed and index == 0:
            coords[-1] = (float(x), float(y))
        elif closed and index == len(coords) - 1:
            coords[0] = (float(x), float(y))
        new = self._rebuild_geom(self._geoms[fid], part, ring, coords)
        self._run(_SetGeometryCommand(self, fid, new, text=_tr("移动折点")))
        return True

    def move_vertices(self, fid, moves, part=0, ring=0):
        got = self._ring_coords(fid, part, ring)
        if got is None:
            return False
        coords, closed, _is_poly = got
        for index, x, y in moves:
            if not (0 <= index < len(coords)):
                continue
            coords[index] = (float(x), float(y))
            if closed and index == 0:
                coords[-1] = (float(x), float(y))
            elif closed and index == len(coords) - 1:
                coords[0] = (float(x), float(y))
        new = self._rebuild_geom(self._geoms[fid], part, ring, coords)
        self._run(_SetGeometryCommand(self, fid, new, text=_tr("移动折点")))
        return True

    def insert_vertex(self, fid, segment, x, y, part=0, ring=0):
        got = self._ring_coords(fid, part, ring)
        if got is None:
            return False
        coords, _closed, _is_poly = got
        if not (0 <= segment < len(coords) - 1):
            return False
        coords.insert(segment + 1, (float(x), float(y)))
        new = self._rebuild_geom(self._geoms[fid], part, ring, coords)
        self._run(_SetGeometryCommand(self, fid, new, text=_tr("添加折点")))
        return True

    def delete_vertex(self, fid, index, part=0, ring=0):
        got = self._ring_coords(fid, part, ring)
        if got is None:
            return False
        coords, _closed, is_poly = got
        n = len(coords)
        uniq = n - 1 if (_closed and n > 2 and coords[0] == coords[-1]) else n
        need = 3 if is_poly else 2
        if uniq <= need:
            return False
        if not (0 <= index < n):
            return False
        del coords[index]
        new = self._rebuild_geom(self._geoms[fid], part, ring, coords)
        self._run(_SetGeometryCommand(self, fid, new, text=_tr("删除折点")))
        return True

    def check_topology(self, fids=None):
        from .snapping import _iter_parts
        geoms = self._geoms
        if fids is None:
            fids = range(len(geoms))
        out = []
        for fid in fids:
            fid = int(fid)
            if not (0 <= fid < len(geoms)):
                continue
            g = geoms[fid]
            if g is None or getattr(g, "is_empty", True):
                out.append(TopologyIssue(fid, TOPOLOGY_EMPTY, "几何为空"))
                continue

            gt = getattr(g, "geom_type", "")
            try:
                if "Line" in gt and float(g.length) <= 0.0:
                    out.append(TopologyIssue(fid, TOPOLOGY_ZERO_LENGTH,
                                             "线长度为 0"))
                    continue
            except Exception:
                _log.exception("silent exception in check_topology")

            try:
                import shapely
                from shapely.validation import explain_validity
                if not bool(shapely.is_valid(g)):
                    try:
                        reason = str(explain_validity(g))
                    except Exception:
                        _log.exception("silent exception in check_topology")
                        reason = "几何无效"
                    kind = TOPOLOGY_SELF_INTERSECTION if \
                        "self-intersection" in reason.lower() else \
                        TOPOLOGY_INVALID
                    loc = None
                    try:
                        m = reason[reason.find("[") + 1:reason.find("]")]
                        parts = m.replace(",", " ").split()
                        loc = (float(parts[0]), float(parts[1]))
                    except Exception:
                        _log.exception("silent exception in check_topology")
                        try:
                            rp = g.representative_point()
                            loc = (float(rp.x), float(rp.y))
                        except Exception:
                            _log.exception("silent exception in check_topology")
                            loc = None
                    out.append(TopologyIssue(fid, kind, reason or "几何无效",
                                             loc))
                    continue
            except Exception:
                _log.exception("silent exception in check_topology")

            try:
                if "Polygon" in gt and float(g.area) <= 0.0:
                    out.append(TopologyIssue(fid, TOPOLOGY_ZERO_LENGTH,
                                             "面积为 0"))
                    continue
            except Exception:
                _log.exception("silent exception in check_topology")

            for _p, _r, coords in _iter_parts(g) or ():
                dup = None
                for i in range(1, len(coords)):
                    if coords[i] == coords[i - 1]:
                        dup = coords[i]
                        break
                if dup is None and len(coords) > 2 and coords[0] == coords[-1]:
                    pass
                if dup is not None:
                    out.append(TopologyIssue(fid, TOPOLOGY_DUPLICATE_POINT,
                                             "相邻顶点重复", dup))
                    break
        return out

    def commit(self, path=None):
        target = str(path or self._layer.source() or "")
        if not target:
            raise ValueError("图层没有数据源路径")
        try:
            from ggis.exec import guard as _guard
            from ggis.exec import task as _exec_task
            _async = bool(_guard.ui_mode() and _guard.on_ui_thread())
        except Exception:
            _log.exception("silent exception in commit")
            _async = False
        if not _async:
            out = _write_layer_job(self._layer, target)
            self._after_commit(out, sig=None)
            return out

        snap = _freeze_layer(self._layer)
        sig = self._write_signature()
        self._commit_task = _exec_task.submit(
            _write_layer_job, snap, target, kind="io",
            name=_tr("保存编辑"),
            protect=True)
        self._commit_task.on_done(
            lambda ev: self._after_commit(ev.get("result"), sig=sig))
        return self._commit_task

    def _write_signature(self):
        try:
            return (id(self._layer), int(_data_version(self._layer)))
        except Exception:
            _log.exception("silent exception in _write_signature")
            return (id(self._layer), -1)

    def _after_commit(self, target, sig=None):
        tgt = str(target or "")
        if sig is not None:
            try:
                stale = (self._write_signature() != sig)
            except Exception:
                _log.exception("silent exception in _after_commit")
                stale = False
            if stale:
                if tgt:
                    try:
                        self._layer.relink_source(tgt)
                    except Exception:
                        _log.exception("silent exception in _after_commit")
                self.committed.emit(tgt)
                return tgt
        if tgt:
            try:
                self._layer.relink_source(tgt)
            except Exception:
                _log.exception("silent exception in _after_commit")
        self._stack.setClean()
        self._set_dirty(False)
        self.committed.emit(tgt)
        return tgt

    def accept_in_memory(self):
        try:
            self._stack.setClean()
        except Exception:
            _log.exception("silent exception in accept_in_memory")
        self._set_dirty(False)
        try:
            self.changed.emit()
        except Exception:
            _log.exception("silent exception in accept_in_memory")
        return None

    def rollback(self):
        if not self._active:
            return
        self._stack.setIndex(0)
        self._stack.clear()
        self._set_dirty(False)
        self._layer.invalidate_extent()
        _bump_data_version(self._layer)
        if self._index is not None:
            self._index.mark_dirty()
        if self._snapper is not None:
            try:
                self._snapper.invalidate(self._layer)
            except Exception:
                _log.exception("silent exception in rollback")
        self.changed.emit()
        self.structureChanged.emit()

    def _on_clean_changed(self, clean):
        if clean:
            self._set_dirty(False)
