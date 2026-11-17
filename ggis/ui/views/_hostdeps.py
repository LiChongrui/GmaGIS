# -*- coding: utf-8 -*-
from ggis.core.app import i18n
from ggis.core.app import settings as app_settings
from ggis.core.model.selection import GgsSelection
from ggis.core.analysis.tile import basemap as find_basemap, basemap_choices
from ...io.formats import VECTOR_WRITE_FORMATS, vector_suffix_for_driver
from ggis.common.base.dialog import GgsMsgBox
from ..panels.layertree import ROLE_KIND, ROLE_LAYER_ID
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog

_tr = i18n.tr

LEVEL_INFO = "Info"
LEVEL_SUCCESS = "Success"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"
LEVEL_WARN = LEVEL_WARNING

__all__ = [
    "i18n", "_tr", "app_settings",
    "GgsSelection", "GgsMsgBox",
    "find_basemap", "basemap_choices",
    "VECTOR_WRITE_FORMATS", "vector_suffix_for_driver",
    "ROLE_KIND", "ROLE_LAYER_ID",
    "Qt", "QTimer", "QApplication", "QDialog",
    "LEVEL_INFO", "LEVEL_SUCCESS", "LEVEL_WARNING",
    "LEVEL_CRITICAL", "LEVEL_WARN",
]
