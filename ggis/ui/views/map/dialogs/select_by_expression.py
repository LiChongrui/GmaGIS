# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from ggis.core.app import i18n
from ggis.core.expr.expression import check_expression, compile_expression
from ggis.core.model.selection import GgsSelection
from ggis.ui.views.map.dialogs.filter import GgsFilterDialog
from ggis.common.styling import icons

_tr = i18n.tr


class GgsSelectByExpressionDialog(GgsFilterDialog):

    def __init__(self, layer, parent=None, apply_cb=None):
        super().__init__(layer, parent, apply_cb)
        self.setObjectName("GgsSelectByExpressionDialog")
        self.setWindowTitle(_tr("按属性选择 — {0}").format(layer.name()))
        try:
            self.setWindowIcon(icons.icon("select_attr", size=16))
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/select_by_expression.py:43")
            pass

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
                exc_note("_on_apply @ ggis/ui/views/map/dialogs/select_by_expression.py:64")
                self.lbl_preview.setText(str(e))
                return
            fids = sorted(set(self.match_fids()))
            try:
                GgsSelection.instance().set_fids(self._layer, fids)
            except Exception:
                exc_note("_on_apply @ ggis/ui/views/map/dialogs/select_by_expression.py:70")
                return
            n = len(fids)
        else:
            try:
                GgsSelection.instance().set_fids(self._layer, [])
            except Exception:
                exc_note("_on_apply @ ggis/ui/views/map/dialogs/select_by_expression.py:77")
                pass
            n = 0
        self._applied = True
        try:
            if self._apply_cb is not None:
                self._apply_cb()
        except Exception:
            exc_note("_on_apply @ ggis/ui/views/map/dialogs/select_by_expression.py:84")
            pass
        total = self._layer.feature_count()
        self.lbl_preview.setText(
            _tr("已选中：{0} / {1}（取消可还原）").format(n, total))


