# -*- coding: utf-8 -*-

from ggis.core.app import i18n
from ggis.core.crs.extent import GgsRectangle
from ggis.core.model.selection import GgsSelection
from ggis.core.analysis.tile import basemap as find_basemap, basemap_choices
from ggis.common.base.dialog import GgsMsgBox
from ggis.render.map_canvas import GgsMapCanvas
from ggis.ui.framework.ribbon import GgsRibbon, RibbonGroup, RibbonPage
from ggis.common.styling import icons
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget
import logging

_tr = i18n.tr
LEVEL_INFO = "Info"
LEVEL_SUCCESS = "Success"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"
LEVEL_WARN = LEVEL_WARNING
_log = logging.getLogger("gmagis")

DOCK_W = 300

EDGE = 6
_CANVAS_MIN_W = 320
_CANVAS_MIN_H = 240

__all__ = [
    "i18n", "_tr", "_log",
    "LEVEL_INFO", "LEVEL_SUCCESS", "LEVEL_WARNING", "LEVEL_CRITICAL",
    "LEVEL_WARN", "DOCK_W",
    "EDGE", "_CANVAS_MIN_W", "_CANVAS_MIN_H",
    "GgsMsgBox", "GgsMapCanvas", "GgsRectangle", "GgsSelection",
    "Qt", "QWidget", "QAction", "QMenu",
    "GgsRibbon", "RibbonGroup", "RibbonPage",
    "icons", "find_basemap", "basemap_choices",
]
