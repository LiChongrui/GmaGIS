# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidgetItem,
                               QSizePolicy, QSpinBox, QVBoxLayout,
                               QWidget)

from ggis.core.app import i18n
from ggis.core.model.field import GgsField
from ggis.common.styling import icons as _icons
from ggis.core.expr.fieldcalc import (compile_code_block, compile_field_calc,
                               dump_cal, eval_field_calc, parse_cal)
from ggis.core.expr.expression import function_catalog
from ggis.core.model.selection import GgsSelection
from ggis.common.base.dialog import GgsDialog, GgsMsgBox
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
import logging
from PySide6.QtWidgets import QLineEdit, QListWidget, QPlainTextEdit, QPushButton
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_OPERATORS = ["*", "/", "+", "-", "="]

_NEW_TYPES = [("integer", "整数"), ("real", "实数"),
              ("string", "文本"), ("bool", "布尔")]


class GgsFieldCalculatorDialog(GgsDialog):

    def __init__(self, parent, widget):
        super().__init__(parent)
        self.setObjectName("GgsFieldCalculatorDialog")
        self._widget = widget
        self._layer = widget._layer
        self._fields = list(widget.model_.fields())
        try:
            self.setWindowIcon(_icons.icon("calc", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        self.setWindowTitle(
            _tr("字段计算器 — {0}").format(self._layer_name()))
        self.resize(560, 700)
        self._build()
        self._init_selection()
        self._refresh()

    def _layer_name(self):
        try:
            return self._layer.name()
        except Exception:
            _log.exception("silent exception in _layer_name")
            return ""

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        grp_f = QGroupBox(_tr("字段"), self)
        gf = QVBoxLayout(grp_f)
        gf.setContentsMargins(8, 8, 8, 8)
        gf.setSpacing(4)
        gf.addWidget(QLabel(_tr("字段名称")))
        self.cmb_target = QComboBox(grp_f)
        self.cmb_target.setEditable(True)
        for i, f in enumerate(self._fields):
            self.cmb_target.addItem(f.name)
            self.cmb_target.setItemData(
                i, "%s (%s)" % (f.name, f.type), Qt.ItemDataRole.ToolTipRole)
        gf.addWidget(self.cmb_target)

        self.wgt_new = QWidget(grp_f)
        nf = QFormLayout(self.wgt_new)
        nf.setContentsMargins(0, 0, 0, 0)
        self.cmb_type = QComboBox(self.wgt_new)
        for t, lab in _NEW_TYPES:
            self.cmb_type.addItem(_tr(lab), t)
        self.spn_w = QSpinBox(self.wgt_new)
        self.spn_w.setRange(0, 254)
        self.spn_p = QSpinBox(self.wgt_new)
        self.spn_p.setRange(0, 16)
        nf.addRow(_tr("类型"), self.cmb_type)
        nf.addRow(_tr("宽度"), self.spn_w)
        nf.addRow(_tr("精度"), self.spn_p)
        gf.addWidget(self.wgt_new)
        self.wgt_new.hide()

        self.chk_sel = QCheckBox(_tr("仅更新选中的要素"), grp_f)
        gf.addWidget(self.chk_sel)
        lay.addWidget(grp_f)

        grp_e = QGroupBox(_tr("表达式"), self)
        ge = QVBoxLayout(grp_e)
        ge.setContentsMargins(8, 8, 8, 8)
        ge.setSpacing(4)

        lists = QWidget(grp_e)
        ll = QHBoxLayout(lists)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        col = QWidget(lists)
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        cl.addWidget(QLabel(_tr("字段")))
        self.lst_fields = GgsExprFields(col)
        for f in self._fields:
            it = QListWidgetItem("%s (%s)" % (f.name, f.type))
            it.setData(Qt.ItemDataRole.UserRole, f.name)
            self.lst_fields.addItem(it)
        self.lst_fields.itemDoubleClicked.connect(
            lambda it: self._insert(it.data(Qt.ItemDataRole.UserRole)))
        self.lst_fields.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Ignored)
        self.lst_fields.setMinimumHeight(120)
        cl.addWidget(self.lst_fields, 1)
        ll.addWidget(col, 1)

        col = QWidget(lists)
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        cl.addWidget(QLabel(_tr("助手")))
        self.lst_funcs = GgsExprFields(col)
        for cat, items in function_catalog():
            for name, sig, doc in items:
                it = QListWidgetItem(_tr(sig))
                it.setData(Qt.ItemDataRole.UserRole, name)
                it.setToolTip(_tr(doc))
                self.lst_funcs.addItem(it)
        self.lst_funcs.itemDoubleClicked.connect(
            lambda it: self._insert(
                "%s(" % (it.data(Qt.ItemDataRole.UserRole) or "")))
        self.lst_funcs.setSizePolicy(QSizePolicy.Policy.Preferred,
                                     QSizePolicy.Policy.Ignored)
        self.lst_funcs.setMinimumHeight(120)
        cl.addWidget(self.lst_funcs, 1)
        ll.addWidget(col, 1)

        ge.addWidget(lists, 1)
        if self.lst_fields.count():
            self.lst_fields.setCurrentRow(0)

        ops = QWidget(grp_e)
        ol = QHBoxLayout(ops)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(3)
        for op in _OPERATORS:
            b = GgsExprOp(op, ops)
            b.setFixedHeight(24)
            b.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _c=False, t=op: self._insert(t))
            ol.addWidget(b, 1)
        ge.addWidget(ops)

        self.ed_expr = GgsExprEdit(grp_e)
        self.ed_expr.setPlaceholderText(
            "")
        ge.addWidget(self.ed_expr)
        lay.addWidget(grp_e, 2)

        grp = QGroupBox(_tr("代码块（可选）"), self)
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(8, 6, 8, 8)
        gl.setSpacing(4)
        self.ed_code = GgsExprText(grp)
        self.ed_code.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding)
        self.ed_code.setMinimumHeight(80)
        gl.addWidget(self.ed_code)
        lay.addWidget(grp, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)
        self.btn_imp = GgsSmallButtonStyle1(
            "input_file", _tr("导入 .cal 表达式文件"), self._import_cal, 16,
            self)
        self.btn_exp = GgsSmallButtonStyle1(
            "export", _tr("导出为 .cal 表达式文件"), self._export_cal, 16,
            self)
        bottom.addWidget(self.btn_imp)
        bottom.addWidget(self.btn_exp)
        self.lbl_err = GgsExprError("", self)
        self.lbl_err.setWordWrap(False)
        bottom.addWidget(self.lbl_err, 1)
        bottom.addStretch(1)
        bbox = QDialogButtonBox(self)
        self.btn_ok = bbox.addButton(_tr("确定"),
                                     QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.addButton(_tr("取消"), QDialogButtonBox.ButtonRole.RejectRole)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        bottom.addWidget(bbox)
        lay.addLayout(bottom)

        self.cmb_target.currentTextChanged.connect(self._on_target)
        self.ed_expr.textChanged.connect(self._refresh)
        self.ed_code.textChanged.connect(self._on_code_changed)
        self._on_target()

    def _init_selection(self):
        n = 0
        try:
            fids = GgsSelection.instance().fids(self._layer) or []
            n = len(set(int(f) for f in fids))
        except Exception:
            _log.exception("silent exception in _init_selection")
            n = 0
        if n > 0:
            self.chk_sel.setChecked(True)
        else:
            self.chk_sel.setChecked(False)
            self.chk_sel.setEnabled(False)

    def _insert(self, text):
        if not text:
            return
        cur = self.ed_expr.text()
        pos = self.ed_expr.cursorPosition()
        self.ed_expr.setText(cur[:pos] + str(text) + cur[pos:])
        self.ed_expr.setCursorPosition(pos + len(str(text)))
        self.ed_expr.setFocus()

    def _on_code_changed(self):
        self._refresh()

    def _refresh(self, *_):
        expr = self.ed_expr.text().strip()
        if not expr:
            _fns, err = compile_code_block(self.ed_code.toPlainText())
            self.lbl_err.setText(err or "")
            return
        _compiled, err = compile_field_calc(
            expr, self.ed_code.toPlainText(),
            [f.name for f in self._fields])
        self.lbl_err.setText(err or "")

    def _import_cal(self):
        path, _ = QFileDialog.getOpenFileName(
            self, _tr("导入字段计算器表达式"), "",
            _tr("字段计算器表达式 (*.cal)"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except Exception as e:
            GgsMsgBox.warning(self, _tr("导入失败"), str(e))
            return
        expr, code, err = parse_cal(text)
        if err:
            GgsMsgBox.warning(self, _tr("导入失败"), err)
            return
        self.ed_expr.setText(expr)
        self.ed_code.setPlainText(code)

    def _export_cal(self):
        path, _ = QFileDialog.getSaveFileName(
            self, _tr("导出字段计算器表达式"), "",
            _tr("字段计算器表达式 (*.cal)"))
        if not path:
            return
        if not path.lower().endswith(".cal"):
            path += ".cal"
        try:
            with open(path, "w", encoding="utf-8-sig") as fh:
                fh.write(dump_cal(self.ed_expr.text(),
                                  self.ed_code.toPlainText()))
        except Exception as e:
            GgsMsgBox.warning(self, _tr("导出失败"), str(e))
            return
        self._msg(_tr("已导出：{0}").format(path))

    def _msg(self, text):
        fn = getattr(self._widget, "_host_msg", None)
        if callable(fn):
            try:
                fn(text)
                return
            except Exception:
                _log.exception("silent exception in _msg")
        GgsMsgBox.information(self, _tr("字段计算器"), text)

    def _on_target(self, *_):
        name = self.cmb_target.currentText().strip()
        self.wgt_new.setVisible(
            bool(name) and name not in {f.name for f in self._fields})

    def _alert(self, text):
        GgsMsgBox.warning(self, _tr("字段计算器"), text)

    def accept(self):
        w = self._widget
        s = w._session() if hasattr(w, "_session") else None
        if s is None or not s.is_active():
            self._alert(_tr("本图层当前不可编辑，无法执行该操作"))
            return
        expr = self.ed_expr.text().strip()
        if not expr:
            self._alert(_tr("请输入表达式"))
            return
        new_field = None
        name = self.cmb_target.currentText().strip()
        if not name:
            self._alert(_tr("请填写字段名称"))
            return
        if name not in {f.name for f in self._fields}:
            new_field = GgsField(name, self.cmb_type.currentData(),
                                 self.spn_w.value(), self.spn_p.value())
        target = name
        compiled, err = compile_field_calc(
            expr, self.ed_code.toPlainText(),
            [f.name for f in self._fields])
        if err:
            self._alert(err)
            return
        only_sel = self.chk_sel.isChecked() and self.chk_sel.isEnabled()
        sel = set()
        if only_sel:
            try:
                sel = set(int(f) for f in
                          (GgsSelection.instance().fids(self._layer) or []))
            except Exception:
                _log.exception("silent exception in accept")
                sel = set()
        attrs = self._layer.attrs() or []
        changes = {}
        for fid, a in enumerate(attrs):
            if only_sel and fid not in sel:
                continue
            if not isinstance(a, dict):
                continue
            val, err = eval_field_calc(compiled, a)
            if err:
                self._alert(_tr("第 {0} 个要素计算失败：{1}"
                                "（已中止，未写入任何数据）").format(fid, err))
                return
            changes[fid] = {target: val}
        if not changes:
            self._alert(_tr("没有可更新的要素"))
            return
        try:
            if new_field is not None:
                s.add_field(new_field)
            s.set_attributes_bulk(changes)
        except Exception as e:
            _log.exception("silent exception in accept")
            self._alert(_tr("写入失败：{0}").format(e))
            return
        super().accept()


class GgsExprEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExprEdit")
class GgsExprError(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExprError")
class GgsExprFields(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExprFields")
class GgsExprOp(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExprOp")
class GgsExprText(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExprText")
