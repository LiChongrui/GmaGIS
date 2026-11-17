# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QGridLayout,
                               QGroupBox,
                               QHBoxLayout,
                               QListWidget,
                               QListWidgetItem,
                               QPlainTextEdit,
                               QPushButton,
                               QSizePolicy,
                               QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.core.expr.expression import check_expression, compile_expression
from ggis.core.model.field import fields_from_layer
from ggis.core.expr.query import features_by_expression
from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons
from PySide6.QtWidgets import QLabel, QLineEdit

_tr = i18n.tr

_OP_SEQ = ("=", "<>", "<", ">", "<=", ">=",
           "LIKE", "%", "IN", "BETWEEN", "IS", "NOT", "NULL",
           "AND", "OR", "(", ")")

_OP_COLS = 6

_ALL_VALUES = 5000

_EXPR_TIP = ""


class GgsFilterDialog(GgsDialog):

    def __init__(self, layer, parent=None, apply_cb=None):
        super().__init__(parent)
        self._layer = layer
        self._fields = fields_from_layer(layer)
        self._node = None
        self._cleared = False
        self._apply_cb = apply_cb
        self._orig_subset = None
        self._orig_text = ""
        self._applied = False
        self._remember_original()
        self.setObjectName("GgsFilterDialog")
        self.setWindowTitle(_tr("过滤要素 — {0}").format(layer.name()))
        try:
            self.setWindowIcon(icons.icon("filter", size=16))
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/filter.py:141")
            pass
        self.resize(760, 560)
        self._build()
        self._load_current()
        self._reset_values()
        self._refresh_preview()

    def _remember_original(self):
        try:
            self._orig_subset = self._layer.subset_fids()
        except Exception:
            exc_note("_remember_original @ ggis/ui/views/map/dialogs/filter.py:159")
            self._orig_subset = None
        try:
            self._orig_text = str(self._layer.subset_expression() or "")
        except Exception:
            exc_note("_remember_original @ ggis/ui/views/map/dialogs/filter.py:163")
            self._orig_text = ""

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        cols = QHBoxLayout()
        cols.setSpacing(8)
        cols.addWidget(self._build_fields(), 1)
        cols.addWidget(self._build_values(), 1)
        lay.addLayout(cols, 1)

        lay.addWidget(self._build_ops())

        lay.addWidget(self._build_expr(), 3)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        btn_test = QPushButton(_tr("测试"), self)
        btn_test.clicked.connect(self._on_test)
        bottom.addWidget(btn_test)

        btn_clear = QPushButton(_tr("清除"), self)
        btn_clear.clicked.connect(self._on_clear)
        bottom.addWidget(btn_clear)

        self.lbl_preview = GgsFilterPreview("")
        self.lbl_preview.setWordWrap(False)
        bottom.addWidget(self.lbl_preview)

        bottom.addStretch(1)

        btn_apply = QPushButton(_tr("应用"), self)
        btn_apply.clicked.connect(self._on_apply)
        bottom.addWidget(btn_apply)

        btn_ok = QPushButton(_tr("确定"), self)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        bottom.addWidget(btn_ok)

        btn_cancel = QPushButton(_tr("取消"), self)
        btn_cancel.clicked.connect(self._on_reject)
        bottom.addWidget(btn_cancel)

        self.btn_test = btn_test
        self.btn_clear = btn_clear
        self.btn_apply = btn_apply
        try:
            self.btn_test.setEnabled(self._apply_cb is not None)
            self.btn_apply.setEnabled(self._apply_cb is not None)
        except Exception:
            exc_note("_build @ ggis/ui/views/map/dialogs/filter.py:244")
            pass
        lay.addLayout(bottom)

    def _build_fields(self):
        gb = QGroupBox(_tr("字段"))
        v = QVBoxLayout(gb)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)
        self.lst_fields = GgsFilterFields()
        gb.setMinimumHeight(200)
        self.lst_fields.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Ignored)
        self.lst_fields.setMinimumHeight(60)
        for f in self._fields:
            it = QListWidgetItem("%s (%s)" % (f.name, f.type))
            it.setData(Qt.ItemDataRole.UserRole, str(f.name))
            it.setToolTip(_tr("双击插入字段名"))
            self.lst_fields.addItem(it)
        self.lst_fields.itemDoubleClicked.connect(
            lambda it: self._insert(str(it.data(Qt.ItemDataRole.UserRole)
                                        or "")))
        self.lst_fields.currentItemChanged.connect(
            lambda *a: self._reset_values())
        v.addWidget(self.lst_fields, 1)
        return gb

    def _build_values(self):
        gb = QGroupBox(_tr("值"))
        v = QVBoxLayout(gb)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)
        gb.setMinimumHeight(200)

        self.lst_values = GgsFilterValues()
        self.lst_values.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Ignored)
        self.lst_values.setMinimumHeight(60)
        self.lst_values.itemDoubleClicked.connect(
            lambda it: self._insert(self._value_literal(it.text())))
        v.addWidget(self.lst_values, 1)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.btn_unique = GgsFilterAll(_tr("获取唯一值"))
        self.btn_unique.setToolTip(
            "")
        self.btn_unique.clicked.connect(lambda: self._load_values())
        row.addWidget(self.btn_unique)

        self.ed_search = GgsFilterValueSearch()
        self.ed_search.setPlaceholderText(_tr("搜索候选值…（先点「获取唯一值」）"))
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.textChanged.connect(lambda _t: self._apply_value_filter())
        row.addWidget(self.ed_search, 1)
        v.addLayout(row)
        return gb

    def _build_ops(self):
        gb = QGroupBox(_tr("运算符"))
        grid = QGridLayout(gb)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        for i, op in enumerate(_OP_SEQ):
            b = GgsFilterOp(op)
            b.setMinimumHeight(24)
            b.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
            b.setToolTip(_tr("插入 {0}").format(op))
            b.clicked.connect(lambda _c=False, t=op: self._insert(t))
            grid.addWidget(b, i // _OP_COLS, i % _OP_COLS)
        for c in range(_OP_COLS):
            grid.setColumnStretch(c, 1)
        return gb

    def _build_expr(self):
        gb = QGroupBox(_tr("过滤表达式"))
        v = QVBoxLayout(gb)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)

        self.ed = GgsFilterEdit()
        self.ed.setPlaceholderText(_EXPR_TIP)
        self.ed.setMinimumHeight(48)
        self.ed.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Expanding)
        self.ed.textChanged.connect(self._refresh_preview)
        v.addWidget(self.ed, 1)

        return gb

    def _current_field_name(self):
        it = self.lst_fields.currentItem()
        if it is None:
            return ""
        return str(it.data(Qt.ItemDataRole.UserRole) or "")

    def _reset_values(self):
        if hasattr(self, "lst_values"):
            self.lst_values.clear()
        self._value_cache = []

    def _load_values(self):
        if not hasattr(self, "lst_values"):
            return
        name = self._current_field_name()
        self._value_cache = []
        self.lst_values.clear()
        if not name or self._layer is None:
            return
        limit = _ALL_VALUES
        seen = set()
        out = []
        try:
            attrs = self._layer.attrs()
        except Exception:
            exc_note("_load_values @ ggis/ui/views/map/dialogs/filter.py:406")
            attrs = []
        for a in attrs:
            if not isinstance(a, dict):
                continue
            v = a.get(name)
            if v is None:
                continue
            s = str(v)
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= limit:
                break
        out.sort()
        self._value_cache = out
        self._apply_value_filter()
        try:
            if out:
                tail = "" if len(out) < _ALL_VALUES else _tr("（已截断）")
                self.lst_values.setToolTip(
                    _tr("候选值 {0} 个{1}").format(len(out), tail))
            else:
                self.lst_values.setToolTip(
                    _tr("「{0}」没有取到候选值").format(name))
        except Exception:
            exc_note("_load_values @ ggis/ui/views/map/dialogs/filter.py:433")
            pass

    def _apply_value_filter(self):
        if not hasattr(self, "lst_values"):
            return
        try:
            kw = self.ed_search.text().strip().lower()
        except Exception:
            exc_note("_apply_value_filter @ ggis/ui/views/map/dialogs/filter.py:442")
            kw = ""
        self.lst_values.clear()
        for s in getattr(self, "_value_cache", []):
            if kw and kw not in s.lower():
                continue
            self.lst_values.addItem(s)
            if self.lst_values.count() >= _ALL_VALUES:
                break
        if self.lst_values.count():
            self.lst_values.setCurrentRow(0)

    @staticmethod
    def _value_literal(text):
        s = str(text)
        try:
            float(s)
            return s
        except Exception:
            exc_note("_value_literal @ ggis/ui/views/map/dialogs/filter.py:461")
            return "'%s'" % s.replace("'", "''")

    def _load_current(self):
        try:
            text = self._layer.subset_expression()
        except Exception:
            exc_note("_load_current @ ggis/ui/views/map/dialogs/filter.py:469")
            text = ""
        if text:
            self.ed.setPlainText(text)
        if self.lst_fields.count():
            self.lst_fields.setCurrentRow(0)

    def _insert(self, text):
        if not text:
            return
        cur = self.ed.toPlainText()
        pos = self.ed.textCursor().position()
        add = str(text)
        if pos > 0 and cur[pos - 1:pos] not in (" ", "(", ""):
            add = " " + add
        self.ed.setPlainText(cur[:pos] + add + cur[pos:])
        cur2 = self.ed.textCursor()
        cur2.setPosition(pos + len(add))
        self.ed.setTextCursor(cur2)
        self.ed.setFocus()

    def expression_text(self):
        try:
            return self.ed.toPlainText().strip()
        except Exception:
            exc_note("expression_text @ ggis/ui/views/map/dialogs/filter.py:496")
            return ""

    def mode(self):
        return "keep"

    def match_fids(self):
        if self._node is None:
            return []
        try:
            return features_by_expression(self._layer, self._node)
        except Exception:
            exc_note("match_fids @ ggis/ui/views/map/dialogs/filter.py:515")
            return []

    def result_fids(self):
        text = self.expression_text()
        if not text:
            return None
        if self._node is None:
            try:
                self._node = compile_expression(text, self._fields)
            except Exception:
                exc_note("result_fids @ ggis/ui/views/map/dialogs/filter.py:531")
                return []
        return sorted(set(self.match_fids()))

    def _refresh_preview(self, *_):
        text = self.expression_text()
        if not text:
            self.lbl_preview.setText("")
            return
        err = check_expression(text, self._fields)
        if err:
            self.lbl_preview.setText(err)
            return
        self.lbl_preview.setText("")

    def _restore_original(self):
        try:
            if self._orig_text and self._orig_subset is not None:
                self._layer.set_subset(list(self._orig_subset),
                                       self._orig_text)
            else:
                self._layer.clear_subset()
        except Exception:
            exc_note("_restore_original @ ggis/ui/views/map/dialogs/filter.py:561")
            pass
        try:
            if self._apply_cb is not None:
                self._apply_cb()
        except Exception:
            exc_note("_restore_original @ ggis/ui/views/map/dialogs/filter.py:566")
            pass

    def _on_test(self):
        text = self.expression_text()
        if not text:
            self._node = None
            self.lbl_preview.setText(
                _tr("表达式为空"))
            return
        try:
            self._node = compile_expression(text, self._fields)
        except Exception as e:
            exc_note("_on_test @ ggis/ui/views/map/dialogs/filter.py:585")
            self.lbl_preview.setText(str(e))
            return
        try:
            n = len(self.match_fids())
            total = self._layer.feature_count()
            self.lbl_preview.setText(
                _tr("匹配 {0} / {1}").format(
                    n, total))
        except Exception:
            exc_note("_on_test @ ggis/ui/views/map/dialogs/filter.py:594")
            pass

    def _on_clear(self):
        try:
            self.ed.setPlainText("")
        except Exception:
            exc_note("_on_clear @ ggis/ui/views/map/dialogs/filter.py:607")
            pass
        self._node = None
        self._cleared = False
        self.lbl_preview.setText(
            _tr("表达式已清空"))

    def _on_apply(self):
        text = self.expression_text()
        if text:
            err = check_expression(text, self._fields)
            if err:
                self.lbl_preview.setText(err)
                return
            try:
                self._node = compile_expression(text, self._fields)
            except Exception as e:
                exc_note("_on_apply @ ggis/ui/views/map/dialogs/filter.py:633")
                self.lbl_preview.setText(str(e))
                return
            fids = sorted(set(self.match_fids()))
            try:
                self._layer.set_subset(fids, text)
            except Exception:
                exc_note("_on_apply @ ggis/ui/views/map/dialogs/filter.py:639")
                return
            n = len(fids)
        else:
            try:
                self._layer.clear_subset()
            except Exception:
                exc_note("_on_apply @ ggis/ui/views/map/dialogs/filter.py:645")
                return
            n = self._layer.feature_count()
        self._applied = True
        try:
            if self._apply_cb is not None:
                self._apply_cb()
        except Exception:
            exc_note("_on_apply @ ggis/ui/views/map/dialogs/filter.py:652")
            pass
        total = self._layer.feature_count()
        self.lbl_preview.setText(
            _tr("已应用：保留 {0} / {1}").format(n, total))

    def _on_reject(self):
        if self._applied:
            self._restore_original()
            self._applied = False
        super().reject()

    def reject(self):
        self._on_reject()

    def cleared(self):
        return bool(getattr(self, "_cleared", False))


class GgsFilterAll(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterAll")
class GgsFilterEdit(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterEdit")
class GgsFilterFields(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterFields")
class GgsFilterOp(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterOp")
class GgsFilterPreview(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterPreview")
class GgsFilterValueSearch(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterValueSearch")
class GgsFilterValues(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsFilterValues")
