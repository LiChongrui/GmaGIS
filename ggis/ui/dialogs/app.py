# -*- coding: utf-8 -*-


from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QKeySequence, QColor, QFont, QCursor
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QStackedWidget, QWidget, QLineEdit, QComboBox, QSpinBox,
    QLabel, QToolButton, QToolTip,
    QDialogButtonBox, QGroupBox,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QFrame, QScrollArea,
)

from ggis.core.app import i18n
_tr = i18n.tr
from ggis.core.app import settings as app_settings
from ...core.crs import crs_proj_string, crs_wkt_string
from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons
from ggis.common.styling import themes
from ggis.common.widgets.inputs import GgsCrsSelector
from ggis.common.widgets.buttons import GgsButtonBox
from ggis.common.widgets.separators import GgsGroupCard
from ggis.common.widgets.inputs import GgsSearchEdit
import logging
_log = logging.getLogger("gmagis")


def _theme_icon(path):
    try:
        ic = icons.app_icon()
        if ic is not None and not ic.isNull():
            return ic
    except Exception:
        _log.exception("silent exception in _theme_icon")
    return QIcon()


def _app_icon(name):
    try:
        return icons.icon(name)
    except Exception:
        _log.exception("silent exception in _app_icon")
        return QIcon()


def _dialog_icon(qgis_path, app_name):
    ic = _app_icon(app_name)
    if ic is not None and not ic.isNull():
        return ic
    return _theme_icon(qgis_path)


DISTANCE_UNITS = (
    ("米", "Meters"),
    ("千米", "Kilometers"),
    ("英尺", "Feet"),
    ("码", "Yards"),
    ("英里", "Miles"),
    ("海里", "NauticalMiles"),
    ("度", "Degrees"),
)

AREA_UNITS = (
    ("平方米", "SquareMeters"),
    ("公顷", "Hectares"),
    ("平方千米", "SquareKilometers"),
    ("平方英尺", "SquareFeet"),
    ("平方英里", "SquareMiles"),
    ("英亩", "Acres"),
)


def distance_unit():
    return app_settings.get("distance_unit", "Meters")


def area_unit():
    return app_settings.get("area_unit", "SquareMeters")


def unit_label(units, member_name):
    for label, name in units:
        if name == member_name:
            return label
    return member_name


_CANVAS_TIPS = (
    (i18n.tr("平移画布"), i18n.tr("按住中键 / 空格拖动")),
    (i18n.tr("缩放画布"), i18n.tr("滚轮")),
    (i18n.tr("框选缩放"), i18n.tr("Shift + 拖动")),
)


def _clean(text):
    return (text or "").replace("&", "")


def collect_shortcuts(actions):
    rows = []
    seen = set()

    def add(group, sub, text, sc):
        try:
            if sc is None or sc.isEmpty():
                return
            try:
                s = sc.toString(QKeySequence.SequenceFormat.NativeText)
            except Exception:
                _log.exception("silent exception in add")
                s = sc.toString()
            key = (group, sub, text, s)
            if key in seen:
                return
            seen.add(key)
            rows.append((group, sub, text, s))
        except Exception:
            _log.exception("silent exception in add")

    items = actions.items() if hasattr(actions, "items") else []
    for name, act in items:
        if act is None:
            continue
        grp = name.split("_")[0] if "_" in name else name
        try:
            text = _clean(act.text()) or name
        except Exception:
            _log.exception("silent exception in collect_shortcuts")
            text = name
        add(i18n.tr("功能区"), "", text,
            act.shortcut() if hasattr(act, "shortcut") else None)

    for name, key in _CANVAS_TIPS:
        add(i18n.tr("画布操作"), "", name, _as_keyseq(key))
    return rows


def _as_keyseq(key):
    try:
        from PySide6.QtGui import QKeySequence
        ks = QKeySequence(key)
        return None if ks.isEmpty() else ks
    except Exception:
        _log.exception("silent exception in _as_keyseq")
        return None


class ShortcutsDialog(GgsDialog):

    def __init__(self, mainWindow):
        super().__init__(mainWindow)
        try:
            self.setWindowIcon(_dialog_icon("mActionHelpContents.svg",
                                            "keyboard"))
        except Exception:
            _log.exception("silent exception in __init__")
        self.setWindowTitle(i18n.tr("快捷键速查表"))
        self.resize(620, 620)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 8)

        self.lst = GgsListWidget()
        self.lst.setSpacing(0)
        lay.addWidget(self.lst, 1)

        btns = GgsButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Close).setText(
            i18n.tr("关闭"))
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._rows = collect_shortcuts(
            mainWindow.ctx.svc("actions")._acts or {})
        self._fill()

    def _fill(self):
        self.lst.clear()
        groups, order = {}, []
        for group, sub, name, key in self._rows:
            if group not in groups:
                groups[group] = []
                order.append(group)
            groups[group].append((sub, name, key))

        for group in order:
            items = groups[group]
            hdr = QListWidgetItem(
                _tr("{0}（{1} 项）").format(group, len(items)))
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            f = hdr.font()
            f.setBold(True)
            hdr.setFont(f)
            self.lst.addItem(hdr)
            for sub, name, key in items:
                label = _tr("{0}（{1}）").format(name, sub) if sub else name
                text = "{0}　{1}".format(label, key) if key else label
                self.lst.addItem(text)


class GroupPropertiesDialog(GgsDialog):

    def __init__(self, name, n_layers, n_groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("组属性"))
        try:
            self.setWindowIcon(_dialog_icon("mActionGroupProperties.svg",
                                            "folder"))
        except Exception:
            _log.exception("silent exception in __init__")
        self.resize(340, 170)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(i18n.tr("名称"), self._ro(str(name)))
        form.addRow(i18n.tr("图层数量"), self._ro(str(n_layers)))
        form.addRow(i18n.tr("子组数量"), self._ro(str(n_groups)))
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    @staticmethod
    def _ro(text):
        ed = GgsPropValue(text)
        ed.setReadOnly(True)
        try:
            ed.setObjectName("GgsPropValue")
        except Exception:
            _log.exception("silent exception in _ro")
        return ed


_NAV_DEFAULT_W = 173
_NAV_MIN_W = 115
_NAV_MAX_W = 231


class _NavLeftHost(QWidget):

    def sizeHint(self):
        return QSize(int(_NAV_DEFAULT_W), 300)


class _NavDialog(GgsDialog):

    NAV_WIDTH = _NAV_DEFAULT_W
    NAV_MIN_W = _NAV_MIN_W
    NAV_MAX_W = _NAV_MAX_W
    NAV_ITEM = (110, 26)
    NAV_ICON = 16
    DLG_SIZE = (820, 540)
    DLG_MIN = (680, 440)
    WITH_SEARCH = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(*self.DLG_SIZE)
        self.setMinimumSize(*self.DLG_MIN)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 8)
        outer.setSpacing(8)
        self._outer = outer

        self.split = GgsNavSplit(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        outer.addWidget(self.split, 1)

        left_host = _NavLeftHost()
        left_host.setObjectName("GgsNavHost")
        left_host.setMinimumWidth(self.NAV_MIN_W)
        left_host.setMaximumWidth(self.NAV_MAX_W)
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)
        self.ed_search = GgsSearchEdit()
        self.ed_search.setPlaceholderText(i18n.tr("搜索"))
        self.ed_search.setClearButtonEnabled(True)
        try:
            self.ed_search.addAction(icons.icon("search", size=16),
                                     QLineEdit.ActionPosition.LeadingPosition)
        except Exception:
            _log.exception("silent exception in __init__")
        self.ed_search.textChanged.connect(self._filter_nav)
        left.addWidget(self.ed_search)

        self.nav = GgsListWidget()
        left.addWidget(self.nav, 1)
        self.split.addWidget(left_host)
        self._nav_split_done = False
        try:
            self.split.setStretchFactor(0, 0)
            self.split.setStretchFactor(1, 1)
            self.split.setSizes([int(self.NAV_WIDTH),
                                 max(int(self.NAV_WIDTH) + 1,
                                     int(self.DLG_SIZE[0]) - int(self.NAV_WIDTH)
                                     - 40)])
        except Exception:
            _log.exception("silent exception in __init__")
        if not self.WITH_SEARCH:
            self.ed_search.hide()

        right_host = QWidget()
        right = QVBoxLayout(right_host)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        self.lbl_page = QLabel("")
        _f = self.lbl_page.font()
        _f.setBold(True)
        _f.setPointSizeF(_f.pointSizeF() + 1.5)
        self.lbl_page.setFont(_f)
        self.lbl_page.setVisible(False)

        self.stack = GgsPageStack()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Expanding)
        right.addWidget(self.stack, 1)
        self.split.addWidget(right_host)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.btn_left = QHBoxLayout()
        self.btn_left.setSpacing(6)
        btns.addLayout(self.btn_left)
        btns.addStretch(1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        btns.addWidget(self.buttons)
        outer.addLayout(btns)

        try:
            self.nav.currentItemChanged.connect(self._on_nav)
        except Exception:
            _log.exception("silent exception in __init__")

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_nav_split_done", False):
            return
        try:
            total = int(self.split.width())
            if total <= 0:
                return
            self._nav_split_done = True
            left = max(int(self.NAV_MIN_W),
                       min(int(self.NAV_MAX_W), int(self.NAV_WIDTH)))
            right = max(1, total - left - int(self.split.handleWidth()) - 1)
            self.split.setSizes([left, right])
        except Exception:
            _log.exception("silent exception in showEvent")

    @staticmethod
    def _page_of(item):
        if item is None:
            return None
        v = item.data(Qt.ItemDataRole.UserRole)
        return None if isinstance(v, str) else v

    def _add_header(self, title):
        item = QListWidgetItem(title)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        f = QFont()
        f.setBold(True)
        item.setFont(f)
        try:
            item.setForeground(QColor(themes.theme_color("text",
                                                        icons.is_dark())))
        except Exception:
            _log.exception("silent exception in _add_header")
            item.setForeground(QColor(themes.text_dim()))
        item.setData(Qt.ItemDataRole.UserRole, "header")
        self.nav.addItem(item)

    def _add_page(self, icon, title, widget, tooltip=None):
        try:
            widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Expanding)
        except Exception:
            _log.exception("silent exception in _add_page")
        try:
            for _form in widget.findChildren(QFormLayout):
                _form.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            _log.exception("silent exception in _add_page")
        idx = self.stack.addWidget(self._wrap_page(widget))
        item = QListWidgetItem()
        item.setIcon(icon)
        item.setText(title)
        item.setSizeHint(QSize(*self.NAV_ITEM))
        item.setData(Qt.ItemDataRole.UserRole, idx)
        if tooltip:
            item.setData(Qt.ItemDataRole.ToolTipRole, tooltip)
        self.nav.addItem(item)
        return idx

    @staticmethod
    def _wrap_page(widget):
        if widget is None or isinstance(widget, QScrollArea):
            return widget
        sa = GgsPageScroll()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setSizePolicy(QSizePolicy.Policy.Expanding,
                         QSizePolicy.Policy.Expanding)
        sa.setWidget(widget)
        return sa

    def _on_nav(self, item, prev=None):
        idx = self._page_of(item)
        if idx is None:
            return
        self.stack.setCurrentIndex(int(idx))
        self.lbl_page.setText(item.text() or "")

    def _filter_nav(self, text):
        text = (text or "").strip().lower()
        headers = []
        for i in range(self.nav.count()):
            it = self.nav.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == "header":
                headers.append((i, it))
                continue
            hit = (not text or text in it.text().lower()
                   or text in (it.toolTip() or "").lower())
            it.setHidden(not hit)
        for i, it in headers:
            visible = False
            j = i + 1
            while j < self.nav.count():
                nxt = self.nav.item(j)
                if nxt.data(Qt.ItemDataRole.UserRole) == "header":
                    break
                if not nxt.isHidden():
                    visible = True
                    break
                j += 1
            it.setHidden(not visible)

    def finish(self):
        for i in range(self.nav.count()):
            if self._page_of(self.nav.item(i)) is not None:
                self.nav.setCurrentItem(self.nav.item(i))
                return
        if self.nav.count():
            self.nav.setCurrentItem(self.nav.item(0))

    @staticmethod
    def _form_page(spacing=8):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(spacing)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return w, form

    @staticmethod
    def _ro_line(text):
        ed = GgsPropValue(str(text or ""))
        ed.setReadOnly(True)
        return ed

    def _grouped_page(self):
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        def group(title, icon=""):
            card = GgsGroupCard(i18n.tr(title), str(icon or ""))
            n = lay.count()
            if n > 0 and lay.itemAt(n - 1).spacerItem() is not None:
                lay.insertWidget(n - 1, card.card)
            else:
                lay.addWidget(card.card)
            return card

        sa = GgsPageScroll()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setWidget(inner)
        lay.addStretch(1)
        return sa, group


class ProjectPropertiesDialog(_NavDialog):

    def __init__(self, mainWindow):
        super().__init__(mainWindow)
        try:
            self.setWindowIcon(_dialog_icon(
                "mActionProjectProperties.svg", "project_props"))
        except Exception:
            _log.exception("silent exception in __init__")
        self.setWindowTitle(i18n.tr("工程属性"))
        self._mw = mainWindow

        self._add_page(_dialog_icon("mActionProjectProperties.svg",
                                    "project_props"),
                       i18n.tr("常规"), self._general_page(),
                       i18n.tr("工程文件、工程标题与工程概况"))
        self._add_page(_dialog_icon("mActionMapSettings.svg", "overview"),
                       i18n.tr("视图"), self._view_page(),
                       i18n.tr("单位（显示 / 坐标相关设置）"))
        self.finish()

    def _general_page(self):
        from ggis.core.model import project_info as _pinfo
        snap = _pinfo.snapshot_of(self._mw)

        w, group = self._grouped_page()

        form = group(i18n.tr("工程"), "project")

        self.ed_path = self._ro_line(
            snap["path"] or i18n.tr("（内存工程，尚未保存到文件）"))
        self.ed_path.setToolTip(i18n.tr("只读"))
        form.addRow(i18n.tr("工程文件"), self.ed_path)

        self.ed_title = QLineEdit(app_settings.get("project_title") or "")
        self.ed_title.setPlaceholderText(i18n.tr("未命名工程"))
        form.addRow(i18n.tr("工程标题"), self.ed_title)

        form2 = group(i18n.tr("信息"), "info")

        self.lbl_crs = self._ro_line(snap["crs"] or i18n.tr("（未定义）"))
        self.lbl_crs.setToolTip(i18n.tr("只读"))
        form2.addRow(i18n.tr("坐标系"), self.lbl_crs)

        self.lbl_layers = self._ro_line(snap["layers"] or "—")
        form2.addRow(i18n.tr("图层"), self.lbl_layers)
        self.lbl_features = self._ro_line(snap["features"] or "—")
        form2.addRow(i18n.tr("要素总数"), self.lbl_features)
        self.lbl_size = self._ro_line(snap["size"] or "—")
        form2.addRow(i18n.tr("文件大小"), self.lbl_size)
        self.lbl_mtime = self._ro_line(snap["mtime"] or "—")
        form2.addRow(i18n.tr("最后修改"), self.lbl_mtime)
        return w

    def _view_page(self):
        sa, group = self._grouped_page()

        g = group(i18n.tr("单位"), "units")
        self.cb_dist = QComboBox()
        for label, name in DISTANCE_UNITS:
            self.cb_dist.addItem(label, name)
        self._select(self.cb_dist, app_settings.get("distance_unit"))
        g.addRow(i18n.tr("距离单位"), self.cb_dist)

        self.cb_area = QComboBox()
        for label, name in AREA_UNITS:
            self.cb_area.addItem(label, name)
        self._select(self.cb_area, app_settings.get("area_unit"))
        g.addRow(i18n.tr("面积单位"), self.cb_area)

        self.spn_prec = QSpinBox()
        self.spn_prec.setRange(0, 12)
        self.spn_prec.setValue(int(app_settings.get("coord_precision", 6)))
        self.spn_prec.setToolTip(i18n.tr("小数位数"))
        g.addRow(i18n.tr("坐标小数位"), self.spn_prec)
        return sa

    @staticmethod
    def _select(combo, data):
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def collect(self):
        return {
            "project_title": self.ed_title.text().strip(),
            "distance_unit": self.cb_dist.currentData() or "Meters",
            "area_unit": self.cb_area.currentData() or "SquareMeters",
            "coord_precision": self.spn_prec.value(),
        }


class LayerPropertiesDialog(_NavDialog):

    CRS_KEEP = "keep"
    CRS_SET = "set"
    CRS_REPROJECT = "reproject"

    def __init__(self, layer, mainWindow=None, parent=None):
        super().__init__(parent if parent is not None else mainWindow)
        self.setObjectName("GgsLayerPropertiesDialog")
        self.setWindowTitle(i18n.tr("属性"))
        self._layer = layer
        self._view = mainWindow
        try:
            self.setWindowIcon(_dialog_icon("mActionLayerProperties.svg",
                                            "info"))
        except Exception:
            _log.exception("silent exception in __init__")

        self._add_page(_dialog_icon("mActionLayerProperties.svg", "info"),
                       i18n.tr("常规"), self._general_page(),
                       i18n.tr("图层 / 数据源 / 范围"))
        self._add_page(_dialog_icon("mActionMapSettings.svg", "overview"),
                       i18n.tr("坐标系"), self._crs_page(),
                       i18n.tr("图层坐标系的参数（只读，可复制）"))
        self.finish()

    def _row(self, form, label, value):
        ed = self._ro_line(str(value))
        try:
            ed.setObjectName("GgsPropValue")
        except Exception:
            _log.exception("silent exception in _row")
        ed.setToolTip(str(value))
        form.addRow(i18n.tr(label), ed)
        return ed

    def _row_files(self, form, label, paths):
        from PySide6.QtWidgets import QVBoxLayout
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        for _p in paths:
            ed = self._ro_line(str(_p))
            ed.setObjectName("GgsPropValue")
            ed.setToolTip(str(_p))
            box.addWidget(ed)
        form.addRow(i18n.tr(label), box)
        return box

    def _general_page(self):
        w, group = self._grouped_page()
        lyr = self._layer
        self._orig_source = str(_safe(lyr.source, "") or "")

        f = group("图层", "layer")
        self._row(f, "名称", _safe(lyr.name))
        self._row(f, "图层类型", _safe(lyr.type_label) or _safe(lyr.layer_type))
        if _safe(lyr.is_tile):
            self._tile_rows(f)
        elif _safe(lyr.is_vector):
            self._vector_rows(f)
        else:
            self._raster_rows(f)

        f = group("数据源", "open")
        self._source_rows(f)

        f = group("范围", "bounding_box")
        self._extent_rows(f)
        return w

    def _source_rows(self, form):
        lyr = self._layer
        src = self._orig_source
        is_tile = bool(_safe(lyr.is_tile, False))
        editable = bool(src) or is_tile

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.ed_source = self._ro_line(src or i18n.tr("（内存图层）"))
        self.ed_source.setObjectName("GgsPropSource")
        if not editable:
            self.ed_source.setToolTip(
                i18n.tr("这是内存图层（还没有落盘的来源）；先用「导出」写出"
                        "文件，之后就能在这里指定数据源。"))
        h.addWidget(self.ed_source, 1)
        btn = GgsPropSourceModify()
        try:
            btn.setIcon(icons.icon("folder", size=16))
        except Exception:
            _log.exception("silent exception in _source_rows")
        if is_tile:
            btn.setToolTip(i18n.tr("修改数据源"))
        else:
            btn.setToolTip(i18n.tr("修改数据源"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if not editable:
            btn.setEnabled(False)
            btn.setToolTip(i18n.tr("无可修改的数据源"))
        btn.clicked.connect(self._on_modify_source)
        h.addWidget(btn)
        form.addRow(i18n.tr("路径" if not is_tile else "服务地址"), row)

        if is_tile:
            return

        rel = _related_files(src)
        if rel:
            self._row_files(form, "关联文件", rel)
        drv = _real_driver(lyr, src)
        if drv:
            self._row(form, "存储驱动", drv)
        comp = _compression_format(lyr, src)
        if comp:
            self._row(form, "压缩", comp)
        size = _source_size(src)
        if size is not None:
            total, n = size
            self._row(form, "磁盘占用",
                      i18n.tr("{0}（{1} 个文件）").format(_size_text(total), n)
                      if n > 1 else _size_text(total))

    def _on_modify_source(self):
        view = getattr(self, "_view", None)
        if view is None:
            return
        if _safe(self._layer.is_tile, False):
            from PySide6.QtWidgets import QInputDialog
            cur = _safe(self._layer.source, "") or ""
            txt, ok = QInputDialog.getText(
                self, i18n.tr("修改数据源"),
                i18n.tr("服务地址（瓦片 URL 模板，需含 {z}/{x}/{y}）："),
                text=str(cur))
            if not ok or not str(txt or "").strip():
                return
            self._relink_to(str(txt).strip())
            return
        try:
            from ggis.common.base.dialog import GgsFileDialog
        except Exception:
            _log.exception("silent exception in _on_modify_source")
            return
        import os as _os
        cur = str(self.ed_source.text() or "").strip()
        start = _os.path.dirname(cur) if cur and _os.path.dirname(cur) else ""
        if _safe(self._layer.is_raster, False):
            from ...io.raster_io import RASTER_SUFFIXES
            pat = " ".join("*" + s for s in sorted(RASTER_SUFFIXES))
            flt = i18n.tr("栅格数据 ({0});;所有文件 (*)").format(pat)
        else:
            from ...io.vector_io import VECTOR_SUFFIXES
            pat = " ".join("*" + s for s in sorted(VECTOR_SUFFIXES))
            flt = i18n.tr("矢量数据 ({0});;所有文件 (*)").format(pat)
        path, _f = GgsFileDialog.getOpenFileName(
            self, i18n.tr("修改数据源"), start, flt)
        if path:
            self._relink_to(str(path))

    def _relink_to(self, new_source):
        view = getattr(self, "_view", None)
        if view is None or not new_source:
            return
        try:
            view.relink_layer_source(self._layer, new_source)
        except Exception:
            _log.exception("silent exception in _relink_to")
        try:
            self.ed_source.setText(
                str(_safe(self._layer.source, "") or new_source))
        except Exception:
            _log.exception("silent exception in _relink_to")

    def new_source(self):
        ed = getattr(self, "ed_source", None)
        if ed is None:
            return ""
        try:
            if ed.isReadOnly():
                return ""
            txt = str(ed.text() or "").strip()
        except Exception:
            _log.exception("silent exception in new_source")
            return ""
        if not txt or txt == str(getattr(self, "_orig_source", "")):
            return ""
        return txt

    def _vector_rows(self, form):
        lyr = self._layer
        self._row(form, "几何类型",
                  _safe(lyr.geometry_type_display) or i18n.tr("（未知）"))
        n_all = _safe(lyr.feature_count, 0)
        self._row(form, "要素数", n_all)
        vis = _safe(lyr.visible_count, None)
        if vis is not None and vis != n_all:
            self._row(form, "可见要素数", vis)
        try:
            nf = len(list(lyr.fields() or []))
        except Exception:
            _log.exception("silent exception in _vector_rows")
            nf = 0
        if nf:
            self._row(form, "字段数", nf)
        try:
            sub = lyr.subset_fids()
        except Exception:
            _log.exception("silent exception in _vector_rows")
            sub = None
        if sub is not None:
            self._row(form, "已过滤（子集）要素数", len(sub))

    def _extent_rows(self, form):
        lyr = self._layer
        ext = _safe(lyr.extent, None)
        ok = False
        if ext is not None and not getattr(ext, "is_empty", lambda: False)():
            try:
                xmin, ymin = float(ext.xmin), float(ext.ymin)
                xmax, ymax = float(ext.xmax), float(ext.ymax)
                form.addRow(self._compass(xmin, ymin, xmax, ymax))
                ok = True
            except Exception:
                _log.exception("silent exception in _extent_rows")
                ok = False
        if not ok:
            self._row(form, "范围", _extent_text(ext))

    def _raster_rows(self, form):
        lyr = self._layer
        self._row(form, "尺寸", "%s × %s px" % (_safe(lyr.width, "?"),
                                               _safe(lyr.height, "?")))
        try:
            rx, ry = lyr.resolution()
            self._row(form, "分辨率", _fmt_xy(rx, ry, 8))
        except Exception:
            _log.exception("silent exception in _raster_rows")
            self._row(form, "分辨率", "")
        self._row(form, "波段数", _safe(lyr.band_count, "?"))
        dt = _safe(lyr.dtype, "")
        if dt:
            self._row(form, "像素类型", dt)
        nd = _safe(lyr.nodata, None)
        self._row(form, "无数据值", "" if nd is None else nd)
        try:
            ov = list(lyr.overview_factors() or [])
            if ov:
                self._row(form, "金字塔层级",
                          "%d 级（%s%s）" % (
                              len(ov),
                              ", ".join(str(int(v)) for v in ov[:6]),
                              "…" if len(ov) > 6 else ""))
        except Exception:
            _log.exception("silent exception in _raster_rows")

    def _compass(self, xmin, ymin, xmax, ymax):
        box = QWidget()
        g = QGridLayout(box)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(4)
        for col, align in ((0, Qt.AlignmentFlag.AlignRight),
                           (1, Qt.AlignmentFlag.AlignHCenter),
                           (2, Qt.AlignmentFlag.AlignLeft)):
            g.setColumnStretch(col, 1)

        def cell(cap, value, align, hint):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            if align == Qt.AlignmentFlag.AlignRight:
                h.addStretch(1)
            lab = GgsCompassCap(i18n.tr(cap))
            lab.setToolTip(i18n.tr(hint))
            h.addWidget(lab)
            ed = self._ro_line(str(value))
            try:
                ed.setObjectName("GgsPropValue")
                ed.setToolTip("%s（%s）" % (value, i18n.tr(hint)))
                ed.setMinimumWidth(120)
                ed.setMaximumWidth(190)
            except Exception:
                _log.exception("silent exception in cell")
            h.addWidget(ed)
            if align == Qt.AlignmentFlag.AlignLeft:
                h.addStretch(1)
            return w

        g.addWidget(cell("北", "%.6f" % ymax,
                         Qt.AlignmentFlag.AlignHCenter, "最大 Y"), 0, 1)
        g.addWidget(cell("西", "%.6f" % xmin,
                         Qt.AlignmentFlag.AlignRight, "最小 X"), 1, 0)
        g.addWidget(cell("东", "%.6f" % xmax,
                         Qt.AlignmentFlag.AlignLeft, "最大 X"), 1, 2)
        g.addWidget(cell("南", "%.6f" % ymin,
                         Qt.AlignmentFlag.AlignHCenter, "最小 Y"), 2, 1)
        return box

    def _tile_rows(self, form):
        lyr = self._layer
        src = _safe(lyr.tile_source, None)
        tsize = _safe(src.tile_size, 256) if src else 256
        try:
            tsize = int(tsize)
        except Exception:
            _log.exception("silent exception in _tile_rows")
            tsize = 256
        self._row(form, "瓦片尺寸", i18n.tr("{0} × {0} px").format(tsize))
        zmin = _safe(src.min_zoom, 0) if src else 0
        zmax = _safe(src.max_zoom, 0) if src else 0
        self._row(form, "缩放层级", "z = {0} ~ {1}".format(zmin, zmax))
        tcrs = _safe(src.crs, "") if src else ""
        if tcrs:
            self._row(form, "切片方案", tcrs)
        tms = bool(_safe(src.tms, False)) if src else False
        self._row(form, "行号约定",
                  i18n.tr("TMS（{ -y }，自下而上）" if tms else "XYZ（自上而下）"))
        att = _safe(lyr.attribution, "")
        if att:
            self._row(form, "版权信息", att)

    def _crs_page(self):
        cur = _safe(self._layer.crs, None)
        has_crs = bool(cur is not None
                       and getattr(cur, "is_valid", lambda: False)())
        self._crs_def = {}
        if has_crs:
            for _k, _getter in (("wkt", crs_wkt_string),
                                ("proj", crs_proj_string)):
                _txt = _getter(cur)
                if _txt:
                    self._crs_def[_k] = _txt


        sa, group = self._grouped_page()

        if not has_crs:
            f = group("基本信息", "crs")
            self._row(f, "坐标系", i18n.tr("（未定义坐标系）"))
            return sa

        f = group("基本信息", "crs")
        self._row(f, "名称",
                  _safe(cur.description, "") or i18n.tr("（自定义坐标系）"))
        self._row(f, "编码",
                  _safe(cur.auth_code, "") or i18n.tr("（无 EPSG 编码）"))
        self._row(f, "类型",
                  i18n.tr("投影坐标系") if _safe(cur.is_projected, False)
                  else (i18n.tr("地理坐标系")
                        if _safe(cur.is_geographic, False)
                        else i18n.tr("（未知）")))

        pj = None
        try:
            pj = cur.to_pyproj()
        except Exception:
            _log.exception("silent exception in _crs_page")
            pj = None
        if pj is not None:
            if _safe(cur.is_projected, False):
                op = getattr(pj, "coordinate_operation", None)
                f = group("投影参数", "crs_proj")
                if op is not None:
                    _m = ""
                    try:
                        _m = str(getattr(op, "method_name", "") or "")
                    except Exception:
                        _log.exception("silent exception in _crs_page")
                        _m = ""
                    if _m:
                        self._row(f, "投影方法", _m)
                    try:
                        _params = list(getattr(op, "params", None) or [])
                    except Exception:
                        _log.exception("silent exception in _crs_page")
                        _params = []
                    for _p in _params:
                        try:
                            _pn = str(getattr(_p, "name", "") or "")
                            _pv = getattr(_p, "value", None)
                        except Exception:
                            _log.exception("silent exception in _crs_page")
                            continue
                        if not _pn or _pv is None:
                            continue
                        self._row(f, _CRS_PARAM_ZH.get(_pn, _pn),
                                  _crs_param_text(_pv, _p))

            gcs = pj
            try:
                _gc = pj.geodetic_crs
                if _gc is not None:
                    gcs = _gc
            except Exception:
                _log.exception("silent exception in _crs_page")
            _geo_title = i18n.tr("大地基准参数") if _safe(cur.is_geographic, False) \
                else i18n.tr("地理坐标系")
            f = group(_geo_title, "crs_geo")
            _ang = ""
            try:
                _axes = gcs.axis_info
                if _axes:
                    _ax = _axes[0]
                    _un = str(getattr(_ax, "unit_name", "") or "")
                    _fac = getattr(_ax, "unit_conversion_factor", None)
                    if _un == "degree":
                        _un = i18n.tr("度")
                    if _un and _fac is not None:
                        _ang = "%s（%.12g）" % (_un, float(_fac))
                    elif _un:
                        _ang = _un
            except Exception:
                _log.exception("silent exception in _crs_page")
                _ang = ""
            if _ang:
                self._row(f, "角度单位", _ang)
            for label, obj, attr in (("基准面", getattr(pj, "datum", None),
                                      "name"),
                                     ("椭球体", getattr(pj, "ellipsoid", None),
                                      "name")):
                val = ""
                try:
                    val = str(getattr(obj, attr, "") or "")
                except Exception:
                    _log.exception("silent exception in _crs_page")
                    val = ""
                if val:
                    self._row(f, label, val)
            _el = getattr(pj, "ellipsoid", None)
            if _el is not None:
                try:
                    _a = getattr(_el, "semi_major_metre", None)
                    _b = getattr(_el, "semi_minor_metre", None)
                    _inv = getattr(_el, "inverse_flattening", None)
                    if _a is not None and _b is not None:
                        self._row(f, "长短半轴",
                                  "%.4f / %.4f m" % (float(_a), float(_b)))
                    if _inv is not None:
                        self._row(f, "反扁率", "%.6f" % float(_inv))
                except Exception:
                    _log.exception("silent exception in _crs_page")
            pm = getattr(pj, "prime_meridian", None)
            if pm is not None:
                _pm = ""
                try:
                    _nm = str(getattr(pm, "name", "") or "")
                    _lon = float(getattr(pm, "longitude", 0.0))
                    _pm = ("%s（%.4f°）" % (_nm, _lon) if _nm
                           else "%.4f°" % _lon)
                except Exception:
                    _log.exception("silent exception in _crs_page")
                    _pm = ""
                if _pm:
                    self._row(f, "本初子午线", _pm)
        return sa

    def _copy_crs(self, kind):
        try:
            txt = str(self._crs_def.get(kind) or "")
        except Exception:
            _log.exception("silent exception in _copy_crs")
            txt = ""
        if not txt:
            return
        try:
            QApplication.clipboard().setText(txt)
        except Exception:
            _log.exception("silent exception in _copy_crs")
            return
        try:
            QToolTip.showText(QCursor.pos(),
                              i18n.tr("已复制到剪贴板（{0} 字符）")
                              .format(len(txt)))
        except Exception:
            _log.exception("silent exception in _copy_crs")

    def crs_action(self):
        return self.CRS_KEEP

    def selected_crs(self):
        return None


def _safe(fn, default=None):
    if not callable(fn):
        return fn if fn is not None else default
    try:
        return fn()
    except Exception:
        _log.exception("silent exception in _safe")
        return default


def _extent_text(ext):
    if ext is None:
        return i18n.tr("（无）")
    try:
        return ("{:.6f} , {:.6f}\n{:.6f} , {:.6f}"
                .format(float(ext.xmin), float(ext.ymin),
                        float(ext.xmax), float(ext.ymax)))
    except Exception:
        _log.exception("silent exception in _extent_text")
        return str(ext)


_CRS_PARAM_ZH = {
    "Longitude of natural origin": "中央经线",
    "Latitude of natural origin": "原点纬度",
    "Scale factor at natural origin": "比例因子",
    "False Easting": "东偏移（假东）",
    "False Northing": "北偏移（假北）",
    "Latitude of 1st standard parallel": "第一标准纬线",
    "Latitude of 2nd standard parallel": "第二标准纬线",
    "Latitude of false origin": "假原点纬度",
    "Longitude of false origin": "假原点经度",
    "Easting at false origin": "假原点东偏",
    "Northing at false origin": "假原点北偏",
    "Longitude of centre": "中心经度",
    "Latitude of centre": "中心纬度",
}


def _crs_param_text(value, param=None):
    try:
        v = float(value)
    except Exception:
        _log.exception("silent exception in _crs_param_text")
        return str(value)
    unit = ""
    try:
        unit = str(getattr(param, "unit_name", "") or "")
    except Exception:
        _log.exception("silent exception in _crs_param_text")
        unit = ""
    if unit in ("degree", "rad"):
        return "%.8g°" % v
    if unit.startswith("metre"):
        return "%.8g m" % v
    return "%.8g" % v


_DRIVERS = {
    ".shp": "ESRI Shapefile", ".geojson": "GeoJSON", ".json": "GeoJSON",
    ".gpkg": "GeoPackage", ".gml": "GML", ".kml": "KML",
    ".tab": "MapInfo File", ".mif": "MapInfo File", ".mid": "MapInfo File",
    ".csv": "CSV", ".txt": "CSV", ".tsv": "CSV", ".xlsx": "XLSX",
    ".tif": "GeoTIFF", ".tiff": "GeoTIFF", ".img": "Erdas Imagine",
    ".vrt": "VRT", ".nc": "NetCDF", ".asc": "AAIGrid", ".dem": "USGS DEM",
    ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".bmp": "BMP",
    ".grd": "GMT", ".hdf": "HDF", ".h5": "HDF5",
}

_SHAPE_SIDECARS = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix",
                   ".sbn", ".sbx", ".shp.xml", ".qpj", ".fix")


def _driver_name(source):
    s = str(source or "")
    low = s.lower()
    for ext in sorted(_DRIVERS, key=len, reverse=True):
        if low.endswith(ext):
            return _DRIVERS[ext]
    return ""


def _real_driver(layer, source):
    s = str(source or "")
    try:
        _is_raster = bool(getattr(layer, "is_raster", lambda: False)())
        _is_vector = bool(getattr(layer, "is_vector", lambda: False)())
        if _is_raster:
            ds = _safe(getattr(layer, "dataset", lambda: None)(), None)
            if ds is not None:
                d = _safe(getattr(ds, "driver", None), None)
                if d:
                    return str(d)
        if _is_vector and s:
            try:
                import pyogrio as _po
                info = _po.read_info(s)
                d = info.get("driver") if isinstance(info, dict) else None
                if d:
                    return str(d)
            except Exception:
                _log.exception("silent exception in _real_driver")
    except Exception:
        _log.exception("silent exception in _real_driver")
    return _driver_name(s)


def _related_files(source):
    import os
    s = str(source or "")
    if not s or s.startswith(("http://", "https://", "memory:")):
        return []
    try:
        if not os.path.isfile(s):
            return []
        low = s.lower()
        out = []
        if low.endswith(".shp"):
            base = s[: -len(".shp")]
            for ext in _SHAPE_SIDECARS:
                p = base + ext
                if os.path.isfile(p) and p != s:
                    out.append(p)
        elif low.endswith((".tif", ".tiff")):
            for suf in (".aux.xml", ".ovr", ".msk"):
                p = s + suf
                if os.path.isfile(p):
                    out.append(p)
            base = s[: -len(".tif")] if low.endswith(".tif") else s[: -len(".tiff")]
            for suf in (".tfw", ".tifw"):
                p = base + suf
                if os.path.isfile(p):
                    out.append(p)
        return out
    except Exception:
        _log.exception("silent exception in _related_files")
        return []


def _compression_format(layer, src):
    try:
        s = str(src or "")
        low = s.lower()
        for ext, name in ((".zip", "ZIP"), (".7z", "7-Zip"),
                          (".gz", "GZip"), (".tgz", "GZip (tar)"),
                          (".tar.gz", "GZip (tar)"), (".bz2", "BZip2"),
                          (".xz", "XZ"), (".rar", "RAR")):
            if low.endswith(ext):
                return name
        if layer is not None and getattr(layer, "is_raster", False) \
                and not getattr(layer, "is_tile", False):
            ds = getattr(layer, "_ds", None)
            if ds is None:
                try:
                    ds = getattr(layer, "dataset", None)
                except Exception:
                    _log.exception("silent exception in _compression_format")
                    ds = None
            meta = None
            try:
                meta = ds.GetMetadata("IMAGE_STRUCTURE") if ds else None
            except Exception:
                _log.exception("silent exception in _compression_format")
                meta = None
            if meta:
                c = meta.get("COMPRESSION")
                if c:
                    return "栅格压缩：%s" % str(c)
    except Exception:
        _log.exception("silent exception in _compression_format")
        return None
    return None


def _source_size(source):
    import os
    s = str(source or "")
    if not s or s.startswith(("http://", "https://", "memory:")):
        return None
    try:
        if not os.path.exists(s):
            return None
        low = s.lower()
        if low.endswith(".shp"):
            base = s[: -len(".shp")]
            total = 0
            n = 0
            for ext in _SHAPE_SIDECARS:
                p = base + ext
                try:
                    if os.path.isfile(p):
                        total += os.path.getsize(p)
                        n += 1
                except Exception:
                    _log.exception("silent exception in _source_size")
                    continue
            return (total, n) if n else None
        return (os.path.getsize(s), 1)
    except Exception:
        _log.exception("silent exception in _source_size")
        return None


def _size_text(nbytes):
    try:
        n = float(nbytes)
    except Exception:
        _log.exception("silent exception in _size_text")
        return str(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return "%d %s" % (int(n), unit)
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n



def _fmt_xy(x, y, digits=6):
    try:
        return ("{:.%df}, {:.%df}" % (digits, digits)).format(float(x),
                                                             float(y))
    except Exception:
        _log.exception("silent exception in _fmt_xy")
        return "%s, %s" % (x, y)


class GgsCompassCap(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCompassCap")
class GgsNavSplit(QSplitter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsNavSplit")
class GgsPageScroll(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPageScroll")
class GgsPageStack(QStackedWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPageStack")
class GgsPropSourceModify(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPropSourceModify")
class GgsPropValue(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPropValue")
