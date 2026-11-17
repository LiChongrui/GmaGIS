# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
                               QCheckBox,
                               QDialogButtonBox,
                               QHBoxLayout,
                               QLabel,
                               QLineEdit,
                               QListWidgetItem,
                               QSplitter,
                               QToolButton,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n
from ggis.core.expr import label_expr
from ggis.common.styling import icons
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.base.dialog import GgsDialog
from ggis.ui.dialogs.field_calculator import GgsExprError
from ggis.ui.dialogs.field_calculator import GgsExprText
from ggis.common.widgets.inputs import GgsSearchEdit
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr


class GgsLabelExpressionDialog(GgsDialog):

    def __init__(self, layer, expression="", parent=None):
        super().__init__(parent)
        self._layer = layer
        self._initial = str(expression or "")
        self._fields = []
        self.setObjectName("GgsLabelExprDlg")
        self.setWindowTitle(_tr("标注表达式"))
        self.resize(620, 460)
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_fields())
        split.addWidget(self._build_funcs())
        split.setSizes([320, 320])
        root.addWidget(split, 3)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        head.addWidget(QLabel(_tr("表达式")))
        head.addStretch(1)
        self.chk_adv = QCheckBox(_tr("高级"))
        self.chk_adv.setToolTip(
            "")
        self.chk_adv.toggled.connect(self._on_advanced)
        head.addWidget(self.chk_adv)
        root.addLayout(head)

        self.ed = GgsExprText()
        self._set_placeholder(False)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.ed.setFont(f)
        self.ed.setMinimumHeight(96)
        self.ed.textChanged.connect(self._on_text_changed)
        root.addWidget(self.ed, 2)

        self.lbl_status = GgsExprError("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setMinimumHeight(18)
        root.addWidget(self.lbl_status)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.btn_reset = GgsSmallButtonStyle1(
            "reset_edit", _tr("重置为打开时的内容"), self._reset)
        self.btn_verify = GgsSmallButtonStyle1(
            "confirm", _tr("验证"), self._verify)
        self.btn_copy = GgsSmallButtonStyle1(
            "clipboard_copy", _tr("复制表达式"), self._copy)
        self.btn_clear = GgsSmallButtonStyle1(
            "clear", _tr("清除表达式"), self._clear)
        for b in (self.btn_reset, self.btn_verify, self.btn_copy,
                  self.btn_clear):
            row.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        bbox.accepted.connect(self.accept)
        self.btn_ok = bbox.button(QDialogButtonBox.StandardButton.Ok)
        if self.btn_ok is not None:
            self.btn_ok.setText(_tr("确定"))
        row.addWidget(bbox, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(row)

    def _build_fields(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(self._list_head(_tr("字段"), "ed_filter_field"))
        self.lst_fields = GgsListWidget()
        self.lst_fields.setToolTip(_tr("双击插入"))
        self.lst_fields.itemDoubleClicked.connect(self._on_field_double)
        lay.addWidget(self.lst_fields, 1)
        return w

    def _build_funcs(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(self._list_head(_tr("函数"), "ed_filter_func"))
        self.lst_funcs = GgsListWidget()
        self.lst_funcs.setToolTip(_tr("双击插入"))
        self.lst_funcs.itemDoubleClicked.connect(self._on_func_double)
        lay.addWidget(self.lst_funcs, 1)
        return w

    def _list_head(self, title, attr):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(QLabel(title))
        row.addStretch(1)
        btn = QToolButton(self)
        btn.setIcon(icons.icon("search"))
        btn.setToolTip(_tr("过滤"))
        btn.setCheckable(True)
        row.addWidget(btn)
        ed = GgsSearchEdit(self)
        ed.setPlaceholderText(_tr("过滤"))
        ed.setVisible(False)
        ed.textChanged.connect(lambda _t, a=attr: self._filter(a))
        btn.toggled.connect(ed.setVisible)
        setattr(self, attr, ed)
        holder = QVBoxLayout()
        holder.setContentsMargins(0, 0, 0, 0)
        holder.setSpacing(2)
        holder.addLayout(row)
        holder.addWidget(ed)
        box = QWidget()
        box.setLayout(holder)
        out = QVBoxLayout()
        out.setContentsMargins(0, 0, 0, 0)
        out.addWidget(box)
        return out

    def _load(self):
        self._fields = self._read_fields()
        self._initial = self._normalize(self._initial)
        for name, typ in self._fields:
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, name)
            it.setToolTip("%s (%s)" % (name, typ))
            self.lst_fields.addItem(it)
        for disp, _lo, _hi, doc, _fn in label_expr.LABEL_METHODS:
            it = QListWidgetItem(disp)
            it.setData(Qt.ItemDataRole.UserRole, disp)
            it.setToolTip(_tr(doc))
            self.lst_funcs.addItem(it)
        self.ed.setPlainText(self._initial)
        self.chk_adv.setChecked(label_expr.is_python_expr(self._initial))
        self._on_advanced(self.chk_adv.isChecked())
        want = label_expr.first_field(self._initial)
        row = 0
        for i in range(self.lst_fields.count()):
            if self.lst_fields.item(i).text() == want:
                row = i
                break
        if self.lst_fields.count():
            self.lst_fields.setCurrentRow(row)
            if not self._initial:
                self.ed.setPlainText("[%s]" % self._current_field())

    def _read_fields(self):
        out = []
        try:
            for name, typ in self._layer.fields():
                out.append((str(name), str(typ)))
        except Exception:
            _log.exception("silent exception in _read_fields")
        return out

    def _normalize(self, text):
        t = str(text or "").strip()
        if not t or "[" in t or "]" in t:
            return t
        if any(ch in t for ch in '"+.'):
            return t
        names = {str(n) for n, _typ in self._fields}
        return ("[%s]" % t) if t in names else t

    def expression(self):
        return self.ed.toPlainText().strip()

    def _filter(self, which):
        ed = getattr(self, which)
        lst = self.lst_fields if which == "ed_filter_field" else self.lst_funcs
        key = ed.text().strip().lower()
        for i in range(lst.count()):
            it = lst.item(i)
            it.setHidden(bool(key) and key not in it.text().lower())

    def _set_placeholder(self, advanced):
        self.ed.setPlaceholderText(
            ""
            if advanced else
            _tr("例如：[地名] + \" \" + [区划码]"))

    def _on_advanced(self, on):
        self._set_placeholder(bool(on))
        self.lbl_status.setText("")

    def _current_field(self):
        it = self.lst_fields.currentItem()
        return str(it.data(Qt.ItemDataRole.UserRole)) if it is not None else ""

    def _insert(self, text):
        cur = self.ed.textCursor()
        cur.insertText(text)
        self.ed.setTextCursor(cur)

    def _on_field_double(self, item):
        self._insert("[%s]" % item.data(Qt.ItemDataRole.UserRole))

    def _on_func_double(self, item):
        self._insert(item.data(Qt.ItemDataRole.UserRole))

    def _reset(self):
        self.ed.setPlainText(self._initial)
        self.chk_adv.setChecked(label_expr.is_python_expr(self._initial))
        self.lbl_status.setText("")

    def _clear(self):
        self.ed.setPlainText("")
        self.lbl_status.setText("")
        try:
            self.ed.setFocus()
        except Exception:
            _log.exception("silent exception in _clear")

    def _copy(self):
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.expression())
            self.lbl_status.setText(_tr("表达式已复制到剪贴板"))
        except Exception:
            _log.exception("silent exception in _copy")

    def _verify(self):
        expr = self.expression()
        if not expr:
            self.lbl_status.setText(_tr("表达式为空"))
            return
        rows = []
        try:
            rows = list(self._layer.attrs())
        except Exception:
            _log.exception("silent exception in _verify")
            rows = []
        if not rows:
            self.lbl_status.setText(_tr("图层没有要素，无法验证"))
            return
        try:
            out, err = label_expr.verify_python(expr, rows[0])
        except Exception as exc:
            _log.exception("silent exception in _verify")
            self.lbl_status.setText(_tr("验证失败：{0}").format(exc))
            return
        if err:
            self.lbl_status.setText(_tr("验证失败：{0}").format(err))
        elif out:
            self.lbl_status.setText(
                _tr("验证通过（用第一个要素）：{0}").format(out))
        else:
            self.lbl_status.setText(_tr("验证通过，结果为空"))

    def _on_text_changed(self):
        if self.lbl_status.text():
            self.lbl_status.setText("")
