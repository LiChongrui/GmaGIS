# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from ggis.core.app import i18n
from ggis.common.widgets.buttons import GgsSmallButtonStyle1

_tr = i18n.tr

_EXPORT_FILTER = _tr(
    "PNG 图片 (*.png);;"
    "JPEG 图片 (*.jpg *.jpeg);;"
    "TIFF 图片 (*.tif *.tiff);;"
    "SVG 矢量图 (*.svg);;"
    "PDF 文档 (*.pdf);;"
    "EPS 矢量图 (*.eps);;"
    "PostScript (*.ps);;"
    "WEBP 图片 (*.webp);;"
    "所有文件 (*.*)")


def export_mpl_figure(parent, fig, on_message=None):
    from PySide6.QtWidgets import QFileDialog
    if fig is None:
        if on_message is not None:
            on_message(_tr("没有可导出的画布"))
        return False
    path, _ = QFileDialog.getSaveFileName(
        parent, _tr("导出画布"), "", _EXPORT_FILTER)
    if not path:
        return False
    try:
        fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(),
                    edgecolor="none")
        if on_message is not None:
            on_message(_tr("已导出：{0}").format(path))
        return True
    except Exception as exc:
        exc_note("export_mpl_figure @ ggis/ui/charts/mpl_export.py:53")
        if on_message is not None:
            on_message(_tr("导出失败：{0}").format(exc))
        return False


class MplExportButton(GgsSmallButtonStyle1):

    def __init__(self, figure_provider, parent=None, on_message=None):
        super().__init__("export_image", _tr("导出画布"),
                         self._do_export, parent=parent)
        self._figure_provider = figure_provider
        self._on_message = on_message

    def _do_export(self):
        fig = self._figure_provider() if callable(self._figure_provider) else None
        export_mpl_figure(self, fig, self._on_message)
