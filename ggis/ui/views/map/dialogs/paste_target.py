# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QAbstractItemView,
                               QDialogButtonBox,
                               QListWidgetItem,
                               QVBoxLayout,
)

from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons as _icons
from ggis.core.app import i18n
from ggis.core.model.geometry import base_kind as _geom_base_kind
from ggis.common.widgets.displays import GgsDimLabel
from PySide6.QtWidgets import QLabel

_tr = i18n.tr

KIND_LABELS = {"point": "点", "line": "线", "polygon": "面"}

_KIND_ORDER = ("point", "line", "polygon")


def kind_label(kind):
    k = str(kind or "").lower()
    if k in KIND_LABELS:
        return _tr(KIND_LABELS[k])
    if k == "collection":
        return _tr("几何集合")
    return _tr("未知")


def _kinds_text(kinds):
    out = [kind_label(k) for k in _KIND_ORDER if k in (kinds or ())]
    return "、".join(out) if out else _tr("未知")


def clipboard_kinds(clip):
    ks = set()
    for it in (clip or ()):
        try:
            k = str(_geom_base_kind((it or {}).get("geom")) or "").lower()
        except Exception:
            exc_note("clipboard_kinds @ ggis/ui/views/map/dialogs/paste_target.py:84")
            k = ""
        if k in KIND_LABELS:
            ks.add(k)
        elif k == "collection":
            return None
    return ks or None


def layer_kind(layer):
    try:
        k = str(layer.base_kind() or "").lower()
    except Exception:
        exc_note("layer_kind @ ggis/ui/views/map/dialogs/paste_target.py:103")
        return ""
    if k in KIND_LABELS:
        return k
    if k == "collection":
        return ""
    try:
        gs = layer.geoms() or ()
        if gs:
            k2 = str(_geom_base_kind(gs[0]) or "").lower()
            if k2 in KIND_LABELS:
                return k2
    except Exception:
        exc_note("layer_kind @ ggis/ui/views/map/dialogs/paste_target.py:115")
        pass
    return ""


def clip_summary(clip):
    items = list(clip or ())
    ks = clipboard_kinds(items)
    ktext = _kinds_text(ks)
    src = ""
    for it in items:
        s = str((it or {}).get("layer") or "")
        if s:
            src = s
            break
    if src:
        return _tr("剪贴板：{0} 个「{1}」要素（来自「{2}」）").format(
            len(items), ktext, src)
    return _tr("剪贴板：{0} 个「{1}」要素").format(len(items), ktext)


def build_rows(layers, clip):
    want = clipboard_kinds(clip)
    want_text = _kinds_text(want)
    rows = []
    for lyr in (layers or ()):
        try:
            name = str(lyr.name())
        except Exception:
            exc_note("build_rows @ ggis/ui/views/map/dialogs/paste_target.py:153")
            continue
        try:
            is_vec = bool(lyr.is_vector())
        except Exception:
            exc_note("build_rows @ ggis/ui/views/map/dialogs/paste_target.py:157")
            is_vec = False
        if not is_vec:
            text = (_tr("{0}（栅格）").format(name) + "  —  "
                    + _tr("不支持要素粘贴"))
            rows.append({"name": name, "kind": "", "layer": lyr, "ok": False,
                         "text": text,
                         "tip": _tr("栅格图层不支持要素粘贴")})
            continue
        k = layer_kind(lyr)
        if want is None or not k or k in want:
            ok, reason, tip = True, "", name
        else:
            ok = False
            reason = _tr("不可粘贴（需要「{0}」）").format(want_text)
            tip = _tr("几何类型不一致").format(
                kind_label(k), want_text)
        text = _tr("{0}（{1}）").format(name, kind_label(k))
        if reason:
            text += "  —  " + reason
        rows.append({"name": name, "kind": k, "layer": lyr, "ok": ok,
                     "text": text, "tip": tip})
    return rows


class GgsPasteTargetDialog(GgsDialog):

    def __init__(self, rows, summary="", parent=None):
        super().__init__(parent)
        self.setObjectName("GgsPasteTargetDialog")
        self.setWindowTitle(_tr("选择性粘贴"))
        try:
            self.setWindowIcon(_icons.icon("paste_special", size=16))
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/paste_target.py:208")
            pass
        self.setMinimumSize(460, 400)
        self._rows = list(rows or [])

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.lbl_sum = GgsPasteTargetSum(str(summary or ""))
        self.lbl_sum.setWordWrap(True)
        root.addWidget(self.lbl_sum)

        self.lst = GgsListWidget()
        self.lst.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.lst.setWordWrap(True)
        first = -1
        for i, r in enumerate(self._rows):
            it = QListWidgetItem(str(r.get("text") or r.get("name") or ""))
            if r.get("tip"):
                it.setToolTip(str(r["tip"]))
            if not r.get("ok"):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled
                            & ~Qt.ItemFlag.ItemIsSelectable)
            elif first < 0:
                first = i
            self.lst.addItem(it)
        self.lst.itemDoubleClicked.connect(self._on_double)
        self.lst.currentRowChanged.connect(lambda _r: self._refresh())
        root.addWidget(self.lst, 1)

        self.lbl_hint = GgsDimLabel("")
        self.lbl_hint.setWordWrap(True)
        root.addWidget(self.lbl_hint)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        self.btn_ok = box.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        self.btn_ok.setText(_tr("粘贴"))
        self.btn_cancel.setText(_tr("取消"))
        try:
            self.btn_ok.setIcon(_icons.icon("paste_features", size=16))
            self.btn_cancel.setIcon(_icons.icon("clear", size=16))
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/paste_target.py:264")
            pass
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

        if first >= 0:
            self.lst.setCurrentRow(first)
        self._refresh()

    def _row(self, i):
        return self._rows[i] if 0 <= i < len(self._rows) else None

    def _refresh(self):
        r = self._row(self.lst.currentRow())
        ok = bool(r and r.get("ok"))
        try:
            self.btn_ok.setEnabled(ok)
        except Exception:
            exc_note("_refresh @ ggis/ui/views/map/dialogs/paste_target.py:283")
            pass
        if not self._rows:
            self.lbl_hint.setText(_tr("工程里没有图层"))
        elif ok:
            self.lbl_hint.setText(
                _tr("把剪贴板里的要素粘贴到「{0}」"
                    "（该图层不在编辑态时会自动开始编辑）").format(
                        r.get("name") or ""))
        else:
            self.lbl_hint.setText(
                _tr("没有可粘贴的目标图层：剪贴板里要素的类型"
                    "与列表中的图层都对不上"))

    def _on_double(self, item):
        i = self.lst.row(item)
        r = self._row(i)
        if r and r.get("ok"):
            self.lst.setCurrentRow(i)
            self.accept()

    def picked(self):
        r = self._row(self.lst.currentRow())
        return r.get("layer") if (r and r.get("ok")) else None


class GgsPasteTargetSum(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPasteTargetSum")
