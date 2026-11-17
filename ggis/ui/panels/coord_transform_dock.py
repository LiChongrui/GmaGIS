# -*- coding: utf-8 -*-

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFrame,
                              QHeaderView, QLabel, QLineEdit, QTableWidgetItem,
                              QHBoxLayout, QVBoxLayout, QWidget)

from ggis.core.app import i18n
from ggis.ui.panels.pick_dock import GgsPickDockBase
from ggis.common.widgets.inputs import GgsCrsSelector
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.widgets.itemviews import GgsTableWidget
from ggis.ui.framework.docks import GgsDockBody
from ggis.common.widgets.separators import GgsSepH
_log = logging.getLogger("gmagis")

try:
    from ..dialogs.coord_transform import transform_point_checked
except Exception:
    _log.exception("silent exception")
    transform_point_checked = None

_tr = i18n.tr

_SEP = ","

_COL_IN = 0
_COL_OUT = 1


def _num(text):
    s = str(text or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        _log.exception("silent exception in _num")
        return None


def _fmt(v, digits=8):
    try:
        f = float(v)
    except Exception:
        _log.exception("silent exception in _fmt")
        return ""
    s = ("%." + str(int(digits)) + "f") % f
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _xy_text(x, y):
    return "%s%s%s" % (_fmt(x), _SEP, _fmt(y))


def _parse_input(text):
    pts = []
    for seg in str(text or "").split(";"):
        seg = seg.strip()
        if not seg:
            continue
        parts = seg.split(_SEP)
        if len(parts) < 2:
            continue
        x = _num(parts[0])
        y = _num(parts[1])
        if x is None or y is None:
            continue
        pts.append((x, y))
    return pts


def _csv_cell(text):
    s = str(text or "")
    if ("," in s) or ('"' in s):
        return '"' + s.replace('"', '""') + '"'
    return s


class GgsCoordinateTransformDock(GgsPickDockBase):

    def __init__(self, title="坐标转换", parent=None):
        super().__init__(title, parent)
        self.setObjectName("GgsCoordinateTransformDock")
        self._proj_crs_provider = None
        self._last_src = None
        self._view_id = None
        self._pts_by_view = {}
        self._aligning = False
        self._action_name = "coord_transform"

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 8, 8, 2)
        lay.setSpacing(6)
        self._build(lay)
        self.setWidget(body)

    def _build(self, lay):
        row_src = QHBoxLayout()
        row_src.setSpacing(6)
        row_src.addWidget(QLabel(_tr("源坐标系")))
        self.src_sel = GgsCrsSelector(self, crs="EPSG:4326")
        row_src.addWidget(self.src_sel, 1)
        lay.addLayout(row_src)

        row_dst = QHBoxLayout()
        row_dst.setSpacing(6)
        row_dst.addWidget(QLabel(_tr("目标坐标系")))
        self.dst_sel = GgsCrsSelector(self, crs="EPSG:4326")
        row_dst.addWidget(self.dst_sel, 1)
        lay.addLayout(row_dst)

        sep = GgsSepH()
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        row_in = QHBoxLayout()
        row_in.setSpacing(6)
        row_in.addWidget(QLabel(_tr("输入点")))
        self.ed_input = QLineEdit()
        self.ed_input.setPlaceholderText(_tr("X,Y；多个点用分号隔开"))
        self.ed_input.returnPressed.connect(self._on_add)
        row_in.addWidget(self.ed_input, 1)
        self.btn_add = GgsSmallButtonStyle1("add", _tr("添加点"), self._on_add)
        row_in.addWidget(self.btn_add)
        lay.addLayout(row_in)

        self.tbl = GgsTableWidget(0, 2, self)
        self.tbl.setHorizontalHeaderLabels([_tr("输入点"), _tr("输出点")])
        self.tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(_COL_IN, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_OUT, QHeaderView.ResizeMode.Stretch)
        self.tbl.cellChanged.connect(self._on_cell_changed)
        wrap = QWidget(self)
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self.tbl)
        lay.addWidget(wrap, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_pick = GgsSmallButtonStyle1(
            "select", _tr("地图取点"), self._on_toggle_pick)
        self.btn_pick.setChecked(False)
        self._pick_btn = self.btn_pick
        self.btn_del = GgsSmallButtonStyle1("delete", _tr("删除选中"), self._on_delete)
        self.btn_clear = GgsSmallButtonStyle1("broom", _tr("清空点"), self._on_clear)
        for _b in (self.btn_pick, self.btn_del, self.btn_clear):
            btn_row.addWidget(_b)
        btn_row.addStretch(1)
        self.btn_export = GgsSmallButtonStyle1(
            "export", _tr("导出 CSV"), self._on_export)
        btn_row.addWidget(self.btn_export)
        lay.addLayout(btn_row)

        self.src_sel.crsChanged.connect(self._on_crs_changed)
        self.dst_sel.crsChanged.connect(self._on_crs_changed)
        self.tbl.itemSelectionChanged.connect(self._update_actions)
        self._update_actions()

    def set_map_provider(self, fn):
        self._map_provider = fn

    def set_proj_crs_provider(self, fn):
        self._proj_crs_provider = fn

    def configure_crs(self, proj_authid, layer_authids=None):
        items = [a for a in (layer_authids or []) if a]
        try:
            if proj_authid:
                self.src_sel.set_base_crs(proj_authid)
                self.dst_sel.set_base_crs(proj_authid)
            if items:
                self.src_sel.set_layers(items)
                self.dst_sel.set_layers(items)
            src = items[0] if items else (proj_authid or "EPSG:4326")
            dst = proj_authid or "EPSG:4326"
            if dst == src:
                dst = ("EPSG:4326" if src != "EPSG:4326"
                       else (proj_authid or "EPSG:4326"))
            self.src_sel.setCrs(src, emit=False)
            self.dst_sel.setCrs(dst, emit=False)
        except Exception:
            _log.exception("silent exception in configure_crs")
        self._last_src = self._src_authid()
        self._recompute()

    def reorient(self, proj_authid, layer_authids=None, view_id=None):
        _loaded_src = self._align_view(view_id)
        old_src = _loaded_src or self._src_authid()
        self.configure_crs(proj_authid, layer_authids)
        new_src = self._src_authid()
        if old_src and new_src and old_src != new_src and self.tbl.rowCount():
            self._reproject_inputs(old_src, new_src)
            self._recompute()
        self._last_src = new_src
        self._update_display()

    def add_point(self, x, y):
        self._append_rows([(x, y)])
        return True

    _add_input = add_point

    def _proj_crs(self):
        if self._proj_crs_provider is not None:
            try:
                return self._proj_crs_provider()
            except Exception:
                _log.exception("silent exception in _proj_crs")
                return None
        return None

    def _src_authid(self):
        return self.src_sel.crs() or self._proj_crs() or "EPSG:4326"

    def _dst_authid(self):
        return self.dst_sel.crs() or self._proj_crs() or "EPSG:4326"

    def _transform(self, x, y, src, dst):
        if transform_point_checked is None:
            raise RuntimeError("transform_point_checked unavailable")
        return transform_point_checked((x, y), src, dst)

    def _cell(self, row, col, text="", editable=True):
        it = self.tbl.item(row, col)
        if it is None:
            it = QTableWidgetItem()
            self.tbl.setItem(row, col, it)
        if not editable:
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if it.text() != text:
            it.setText(text)
        return it

    def _append_rows(self, pts):
        if not pts:
            return
        self.tbl.blockSignals(True)
        try:
            for (x, y) in pts:
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                self._cell(r, _COL_IN, _xy_text(x, y))
                self._cell(r, _COL_OUT, "", editable=False)
        finally:
            self.tbl.blockSignals(False)
        self._recompute()

    def _current_view_id(self):
        mw = getattr(self, "_main_win", None)
        if mw is None:
            return None
        try:
            mv = mw.current_map_view()
        except Exception:
            _log.exception("silent exception in _current_view_id")
            return None
        return getattr(mv, "view_id", None)

    def _input_pts(self):
        pts = []
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, _COL_IN)
            if it is None:
                continue
            parts = (it.text() or "").split(_SEP)
            x = _num(parts[0]) if len(parts) >= 1 else None
            y = _num(parts[1]) if len(parts) >= 2 else None
            if x is None or y is None:
                continue
            pts.append((x, y))
        return pts

    def _set_input_pts(self, pts):
        self.tbl.blockSignals(True)
        try:
            self.tbl.setRowCount(0)
            for (x, y) in pts:
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                self._cell(r, _COL_IN, _xy_text(x, y))
                self._cell(r, _COL_OUT, "", editable=False)
        finally:
            self.tbl.blockSignals(False)
        self._recompute()

    def _align_view(self, view_id=None):
        if self._aligning:
            return None
        if view_id is None:
            view_id = self._current_view_id()
        if view_id is None or view_id == self._view_id:
            return None
        self._aligning = True
        try:
            if self._view_id is not None:
                self._pts_by_view[self._view_id] = (self._src_authid(),
                                                    self._input_pts())
            elif self._view_id is None and self.tbl.rowCount():
                self._pts_by_view[view_id] = (self._src_authid(),
                                              self._input_pts())
            self._view_id = view_id
            _saved = self._pts_by_view.get(view_id)
            _saved_src, _saved_pts = (_saved if _saved else (None, []))
            self._set_input_pts(list(_saved_pts or []))
            return _saved_src
        finally:
            self._aligning = False

    def forget_view(self, view_id):
        if view_id is None:
            return
        try:
            self._pts_by_view.pop(view_id, None)
        except Exception:
            _log.exception("silent exception in forget_view")
        if self._view_id == view_id:
            self._view_id = None

    def _notify(self, text, warn=True):
        try:
            from ggis.common.base.dialog import GgsMsgBox
            fn = GgsMsgBox.warning if warn else GgsMsgBox.information
            fn(self, _tr("坐标转换"), text)
        except Exception:
            _log.exception("silent exception in _notify")

    def _on_add(self, *_):
        pts = _parse_input(self.ed_input.text())
        if not pts:
            self.ed_input.setFocus()
            self.ed_input.selectAll()
            return
        self._append_rows(pts)
        self.ed_input.clear()

    def _on_clear(self, *_):
        if self.tbl.rowCount() <= 0:
            self._update_actions()
            self._update_display()
            return
        try:
            from PySide6.QtWidgets import QMessageBox
            from ggis.common.base.dialog import GgsMsgBox
            _r = GgsMsgBox.question(
                self, _tr("清空所有点"),
                "")
            if _r != QMessageBox.StandardButton.Yes:
                return
        except Exception:
            _log.exception("silent exception in _on_clear")
            return
        self.tbl.setRowCount(0)
        self._update_actions()
        self._update_display()

    def _on_delete(self, *_):
        rows = sorted({idx.row() for idx in self.tbl.selectedIndexes()},
                      reverse=True)
        if not rows:
            return
        self.tbl.blockSignals(True)
        try:
            for r in rows:
                self.tbl.removeRow(r)
        finally:
            self.tbl.blockSignals(False)
        self._update_actions()
        self._recompute()

    def _on_crs_changed(self, *_):
        old = self._last_src
        new = self._src_authid()
        if old and new and old != new and self.tbl.rowCount():
            self._reproject_inputs(old, new)
        self._last_src = new
        self._recompute()

    def _reproject_inputs(self, old_src, new_src):
        self.tbl.blockSignals(True)
        try:
            for r in range(self.tbl.rowCount()):
                in_it = self.tbl.item(r, _COL_IN)
                parts = (in_it.text() if in_it else "").split(_SEP)
                x = _num(parts[0]) if len(parts) >= 1 else None
                y = _num(parts[1]) if len(parts) >= 2 else None
                if x is None or y is None:
                    continue
                try:
                    nx, ny = self._transform(x, y, old_src, new_src)
                except Exception:
                    _log.exception("silent exception in _reproject_inputs")
                    continue
                self._cell(r, _COL_IN, _xy_text(nx, ny))
        finally:
            self.tbl.blockSignals(False)

    def _update_actions(self):
        has = self.tbl.rowCount() > 0
        sel = bool(self.tbl.selectedIndexes())
        try:
            self.btn_del.setEnabled(sel)
            self.btn_clear.setEnabled(has)
            self.btn_export.setEnabled(has)
        except Exception:
            _log.exception("silent exception in _update_actions")

    def _on_cell_changed(self, row, col):
        if col != _COL_IN:
            return
        self._recompute()

    def _recompute(self):
        src = self._src_authid()
        dst = self._dst_authid()
        self.tbl.blockSignals(True)
        try:
            for r in range(self.tbl.rowCount()):
                in_it = self.tbl.item(r, _COL_IN)
                parts = (in_it.text() if in_it else "").split(_SEP)
                x = _num(parts[0]) if len(parts) >= 1 else None
                y = _num(parts[1]) if len(parts) >= 2 else None
                if x is None or y is None:
                    self._cell(r, _COL_OUT, "", editable=False)
                    continue
                try:
                    ox, oy = self._transform(x, y, src, dst)
                except Exception:
                    _log.exception("silent exception in _recompute")
                    self._cell(r, _COL_OUT, "—", editable=False)
                    continue
                self._cell(r, _COL_OUT, _xy_text(ox, oy), editable=False)
        finally:
            self.tbl.blockSignals(False)
        self._update_actions()
        self._update_display()

    def _tool_pair(self):
        if self._map_provider is None:
            return None
        try:
            return self._map_provider()
        except Exception:
            _log.exception("silent exception in _tool_pair")
            return None

    def _need_tool(self):
        return bool(self._pick_on or self.tbl.rowCount() > 0)

    def _clear_drawn_points(self, tool):
        try:
            tool.clear_display_points()
        except Exception:
            _log.exception("silent exception in _clear_drawn_points")

    def _handle_pick(self, px, py):
        if not self._pick_on:
            return
        try:
            self._align_view()
        except Exception:
            logging.getLogger("gmagis").debug(
                "swallowed coord_transform_dock._handle_pick._align_view",
                exc_info=True)
        src = self._src_authid()
        proj = self._proj_crs() or src
        try:
            sx, sy = self._transform(px, py, proj, src)
        except Exception:
            logging.getLogger("gmagis").warning(
                "坐标转换取点换算失败 src=%s proj=%s 画布点=(%s, %s)",
                src, proj, px, py, exc_info=True)
            return
        self._append_rows([(sx, sy)])

    def _push_tool_point(self):
        if self._tool is None:
            return
        dst = self._dst_authid()
        proj = self._proj_crs() or dst
        pts = []
        for r in range(self.tbl.rowCount()):
            out_it = self.tbl.item(r, _COL_OUT)
            parts = (out_it.text() if out_it else "").split(_SEP)
            x = _num(parts[0]) if len(parts) >= 1 else None
            y = _num(parts[1]) if len(parts) >= 2 else None
            if x is None or y is None:
                continue
            if not dst or dst == proj:
                pts.append((x, y))
                continue
            try:
                pts.append(self._transform(x, y, dst, proj))
            except Exception:
                _log.exception("silent exception in _push_tool_point")
                continue
        try:
            self._tool.set_display_points(pts)
        except Exception:
            _log.exception("silent exception in _push_tool_point")

    def _on_toggle_pick(self, checked):
        super()._on_toggle_pick(checked)
        self._update_display()

    def _update_display(self):
        self._align_view()
        self._sync_tool()
        if self._tool is None:
            return
        dst = self._dst_authid()
        proj = self._proj_crs() or dst
        pts = []
        for r in range(self.tbl.rowCount()):
            out_it = self.tbl.item(r, _COL_OUT)
            parts = (out_it.text() if out_it else "").split(_SEP)
            x = _num(parts[0]) if len(parts) >= 1 else None
            y = _num(parts[1]) if len(parts) >= 2 else None
            if x is None or y is None:
                continue
            if not dst or dst == proj:
                pts.append((x, y))
                continue
            try:
                pts.append(self._transform(x, y, dst, proj))
            except Exception:
                _log.exception("silent exception in _update_display")
                continue
        try:
            self._tool.set_display_points(pts)
        except Exception:
            _log.exception("silent exception in _update_display")

    def _on_export(self, *_):
        if self.tbl.rowCount() == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, _tr("导出坐标点"), "",
            _tr("CSV 文件 (*.csv);;所有文件 (*.*)"))
        if not path:
            return
        try:
            self._write_csv(path)
            self._notify(_tr("已导出：{}").format(path), warn=False)
        except Exception as e:
            _log.exception("silent exception in _on_export")
            self._notify(_tr("导出失败：{}").format(e))

    def _write_csv(self, path):
        lines = [
            "﻿%s,%s" % (_tr("源坐标系"), _csv_cell(self._src_authid())),
            "%s,%s" % (_tr("目标坐标系"), _csv_cell(self._dst_authid())),
            "%s,%s" % (_tr("输入点"), _tr("输出点")),
        ]
        for r in range(self.tbl.rowCount()):
            in_it = self.tbl.item(r, _COL_IN)
            out_it = self.tbl.item(r, _COL_OUT)
            lines.append("%s,%s" % (
                _csv_cell(in_it.text() if in_it else ""),
                _csv_cell(out_it.text() if out_it else "")))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


