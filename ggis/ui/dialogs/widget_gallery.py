
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.core.crs.extent import GgsRectangle
from ggis.common.styling import icons
from ggis.common.widgets.inputs import (GgsColorField, GgsColorRampField, GgsComboBox, GgsCrsSelector, GgsExtentPicker, GgsLineEdit, GgsSearchEdit, GgsSliderSpin, GgsDockComboBox)
from ggis.common.widgets.colors import GgsColorRampBar, GgsColorSwatch
from ggis.common.widgets.separators import (GgsGroupCard, GgsSepH, GgsSepV)
from ggis.common.widgets.inputs import GgsFileInputWidget, GgsFileOutputWidget, GgsLayerInputWidget, GgsLayerOutputWidget, GgsMultiLayerInputWidget
from ggis.ui.dialogs.color import GgsColorButton
from ggis.common.widgets.buttons import (GgsButtonBox, GgsStandardButton, GgsSwitch, GgsSmallButtonStyle1, GgsSmallButtonStyle2, GgsSmallCheckButtonStyle1, GgsSmallCheckButtonStyle2)
from ggis.common.widgets.itemviews import GgsTreeWidget, GgsTreeView
from ggis.common.widgets.itemviews import GgsTableWidget
from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.widgets.msgbar import GgsMessageBar, GgsMsgClose, GgsMsgText
from ggis.ui.framework.ribbon import RibbonGroup
from ggis.common.widgets.buttons import (GgsBigButtonStyle1,
                      GgsBigCheckButtonStyle1,
                      GgsBigMenuButtonStyle1,
                      GgsBigMenuButtonStyle2,
                      GgsBigMenuButtonStyle3,
                      GgsBigMenuButtonStyle4,
                      GgsSmallMenuButtonStyle1,
                      GgsSmallMenuButtonStyle2,
                      GgsMediumButtonStyle1,
                      GgsMediumButtonStyle2,
                      GgsMediumButtonStyle3)
from ggis.ui.framework.searchbar import GgsSearchBar
from ggis.common.widgets.separators import GgsDockSepOverlay
from ggis.ui.framework.statusbar import GgsViewTabs
from ggis.common.base.dialog import (GgsDialog, GgsFileDialog, GgsDockTitleBtn, GgsDockTitleLabel, GgsInputDialog, GgsMsgBox)
from ggis.common.base.view import GgsView
from ggis.common.widgets.displays import GgsDimLabel, GgsRenderStatus, GgsSpinner
from .app import _NavDialog
import logging
_log = logging.getLogger("gmagis")


class _SampleShellDialog(GgsDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("对话框样例"))
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 14)
        lay.setSpacing(12)
        lab = QLabel(i18n.tr("这是 GgsDialog 对话框壳样例。"))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)


_SRC = {
    "GgsStandardButton": "ggis/common/widgets/buttons.py",
    "GgsSwitch": "ggis/common/widgets/buttons.py",
    "GgsButtonBox": "ggis/common/widgets/buttons.py",
    "GgsBigButton": "ggis/common/widgets/buttons.py",
    "GgsBigMenuButton": "ggis/common/widgets/buttons.py",
    "GgsSmallButton": "ggis/common/widgets/buttons.py",
    "GgsSmallCheckButton": "ggis/common/widgets/buttons.py",
    "GgsSmallMenuButton": "ggis/common/widgets/buttons.py",
    "GgsMediumButton": "ggis/common/widgets/buttons.py",
    "GgsLineEdit": "ggis/common/widgets/inputs.py",
    "GgsComboBox": "ggis/common/widgets/inputs.py",
    "GgsDockComboBox": "ggis/common/widgets/inputs.py",
    "GgsSearchEdit": "ggis/common/widgets/inputs.py",
    "GgsSearchBar": "ggis/ui/framework/searchbar.py",
    "GgsSliderSpin": "ggis/common/widgets/inputs.py",
    "GgsExtentPicker": "ggis/common/widgets/inputs.py",
    "GgsCrsSelector": "ggis/common/widgets/inputs.py",
    "GgsColorField": "ggis/common/widgets/inputs.py",
    "GgsColorSwatch": "ggis/common/widgets/colors.py",
    "GgsColorButton": "ggis/ui/dialogs/color.py",
    "GgsColorRampField": "ggis/common/widgets/inputs.py",
    "GgsColorRampBar": "ggis/common/widgets/colors.py",
    "GgsLayerInputWidget": "ggis/common/widgets/inputs.py",
    "GgsLayerOutputWidget": "ggis/common/widgets/inputs.py",
    "GgsMultiLayerInputWidget": "ggis/common/widgets/inputs.py",
    "GgsFileInputWidget": "ggis/common/widgets/inputs.py",
    "GgsFileOutputWidget": "ggis/common/widgets/inputs.py",
    "GgsTreeWidget": "ggis/common/widgets/itemviews.py",
    "GgsTreeView": "ggis/common/widgets/itemviews.py",
    "GgsTableWidget": "ggis/common/widgets/itemviews.py",
    "GgsListWidget": "ggis/common/widgets/itemviews.py",
    "GgsSpinner": "ggis/common/widgets/displays.py",
    "GgsRenderStatus": "ggis/common/widgets/displays.py",
    "GgsDimLabel": "ggis/common/widgets/displays.py",
    "GgsMessageBar": "ggis/common/widgets/msgbar.py",
    "GgsDockSepOverlay": "ggis/common/widgets/separators.py",
    "GgsSepH": "ggis/common/widgets/separators.py",
    "GgsSepV": "ggis/common/widgets/separators.py",
    "GgsGroupCard": "ggis/common/widgets/separators.py",
    "GgsMsgBox": "ggis/common/base/dialog.py",
    "GgsDialog": "ggis/common/base/dialog.py",
    "GgsInputDialog": "ggis/common/base/dialog.py",
    "GgsFileDialog": "ggis/common/base/dialog.py",
    "GgsDockTitleBtn": "ggis/common/base/dialog.py",
    "GgsDockTitleLabel": "ggis/common/base/dialog.py",
    "GgsView": "ggis/common/base/view.py",
    "GgsViewTabs": "ggis/ui/framework/statusbar.py",
}

_CALL = {
    "GgsStandardButton": "ggis/ui/dialogs/settings.py:430",
    "GgsSwitch": "ggis/ui/framework/titlebar.py:662",
    "GgsButtonBox": "ggis/ui/dialogs/app.py:235",
    "GgsBigButtonStyle1": "ggis/ui/features/map_ribbon_groups.py:155",
    "GgsBigCheckButtonStyle1": "ggis/ui/features/map_ribbon_groups.py:94",
    "GgsBigMenuButtonStyle1": "ggis/ui/features/map_ribbon_groups.py:139",
    "GgsBigMenuButtonStyle2": "ggis/ui/features/map_ribbon_groups.py:261",
    "GgsBigMenuButtonStyle3": "ggis/ui/features/map_ribbon_groups.py:148",
    "GgsBigMenuButtonStyle4": "ggis/ui/features/map_ribbon_groups.py:173",
    "GgsSmallButtonStyle1": "ggis/common/widgets/inputs.py:921",
    "GgsSmallButtonStyle2": "ggis/ui/framework/statusbar.py:538",
    "GgsSmallCheckButtonStyle1": "ggis/ui/panels/measure.py:123",
    "GgsSmallCheckButtonStyle2":
        "ggis/common/styling/themes.py:2811（QSS #GgsSmallCheckButtonStyle2）",
    "GgsSmallMenuButtonStyle1": "ggis/ui/dialogs/crs.py:1632",
    "GgsSmallMenuButtonStyle2":
        "ggis/common/widgets/buttons.py:769（定义处，暂无调用点）",
    "GgsMediumButtonStyle1": "ggis/ui/dialogs/about.py:505",
    "GgsMediumButtonStyle2":
        "ggis/common/widgets/buttons.py:824（定义处，暂无调用点）",
    "GgsMediumButtonStyle3":
        "ggis/common/widgets/buttons.py:837（定义处，暂无调用点）",
    "GgsLineEdit": "ggis/ui/views/map/dialogs/new_layer.py:132",
    "GgsComboBox": "ggis/ui/dialogs/export.py:436",
    "GgsDockComboBox": "ggis/ui/panels/spectral_profile_dock.py:58",
    "GgsSearchEdit": "ggis/ui/dialogs/app.py:446",
    "GgsSearchBar": "ggis/ui/framework/regions/RibbonRegion.py:146",
    "GgsSliderSpin": "ggis/ui/dialogs/color.py:1182",
    "GgsExtentPicker": "ggis/ui/dialogs/raster_analysis.py:153",
    "GgsCrsSelector": "ggis/ui/dialogs/new_map.py:60",
    "GgsColorField": "ggis/common/styling/themes.py:1742",
    "GgsColorSwatch": "ggis/common/styling/themes.py:1740",
    "GgsColorButton": "ggis/ui/dialogs/label.py:100",
    "GgsColorRampField": "ggis/ui/dialogs/color_ramp.py:904",
    "GgsColorRampBar": "ggis/ui/panels/symbology.py:1397",
    "GgsLayerInputWidget": "ggis/ui/dialogs/analysis.py:237",
    "GgsLayerOutputWidget": "ggis/ui/dialogs/analysis.py:376",
    "GgsMultiLayerInputWidget": "ggis/ui/dialogs/raster_analysis.py:140",
    "GgsFileInputWidget":
        "ggis/common/widgets/inputs.py:3114（定义处，暂无调用点）",
    "GgsFileOutputWidget": "ggis/ui/dialogs/export.py:442",
    "GgsTreeWidget": "ggis/ui/dialogs/crs.py:1645",
    "GgsTreeView": "ggis/ui/views/map/browser.py:588",
    "GgsTableWidget": "ggis/ui/dialogs/attribute_table.py:1847",
    "GgsListWidget": "ggis/common/widgets/inputs.py:2496",
    "GgsSpinner": "ggis/ui/dialogs/busy.py:68",
    "GgsRenderStatus": "ggis/ui/framework/statusbar.py:371",
    "GgsDimLabel": "ggis/ui/dialogs/analysis.py:409",
    "GgsMessageBar": "ggis/ui/framework/regions/DockRegion.py:1806",
    "GgsMsgText": "ggis/common/widgets/msgbar.py:94（同模块内部）",
    "GgsMsgClose": "ggis/common/widgets/msgbar.py:99（同模块内部）",
    "GgsDockSepOverlay": "ggis/common/widgets/separators.py:219（同模块内部）",
    "GgsSepH": "ggis/ui/panels/coord_transform_dock.py:200",
    "GgsSepV": "ggis/ui/panels/measure.py:132",
    "GgsGroupCard": "ggis/ui/dialogs/app.py:771",
    "GgsMsgBox": "ggis/common/widgets/inputs.py:1088",
    "GgsDialog": "ggis/common/widgets/inputs.py:2902",
    "GgsInputDialog": "ggis/ui/features/viewshell.py:782",
    "GgsFileDialog": "ggis/ui/dialogs/app.py:1240",
    "GgsDockTitleBtn": "ggis/ui/framework/docks.py:146",
    "GgsDockTitleLabel": "ggis/ui/dialogs/view_props.py:85",
    "GgsView": "ggis/ui/framework/regions/TitleRegion.py:202",
    "GgsViewTabs": "ggis/ui/framework/statusbar.py:1652",
}


class GgsWidgetGalleryDialog(_NavDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("Ggs 控件画廊"))
        self.buttons.setVisible(False)

        self._add_page(icons.icon("select"), i18n.tr("按钮"),
                       self._page_buttons())
        self._add_page(icons.icon("logo"), i18n.tr("输入控件"),
                       self._page_inputs())
        self._add_page(icons.icon("logo"), i18n.tr("颜色与色带"),
                       self._page_colors())
        self._add_page(icons.icon("open"), i18n.tr("图层与文件 IO"),
                       self._page_io())
        self._add_page(icons.icon("table"), i18n.tr("列表视图"),
                       self._page_views())
        self._add_page(icons.icon("info"), i18n.tr("状态与消息"),
                       self._page_status())
        self._add_page(icons.icon("settings"), i18n.tr("分隔与卡片"),
                       self._page_seps())
        self._add_page(icons.icon("info"), i18n.tr("对话框与基座"),
                       self._page_dialogs())
        self.finish()

    def _gal_grouped_page(self):
        sa, group = self._grouped_page()

        def group2(title, icon=""):
            f = group(title, icon)
            self._add_src_tag(f, title)
            return f

        return sa, group2

    def _add_src_tag(self, card, title):
        module = _SRC.get(str(title))
        if not module:
            return
        lab = GgsDimLabel(module)
        lay = card.card.layout()
        for i in range(lay.count()):
            sub = lay.itemAt(i).layout()
            if sub is not None and sub.indexOf(card.lbl_title) >= 0:
                sub.addWidget(lab)
                return

    def _calls(self, card, *names):
        parts = []
        for n in names:
            v = _CALL.get(n)
            if v:
                parts.append(str(n) + " → " + str(v))
        if not parts:
            return
        lab = GgsDimLabel(i18n.tr("调用：") + "；".join(parts))
        lab.setWordWrap(True)
        card.addRow(lab)

    def _page_buttons(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsStandardButton", "select")
        f.addRow("", GgsStandardButton("table", i18n.tr("样例"),
                                       tip=i18n.tr("标准按钮")))
        self._calls(f, "GgsStandardButton")

        f = group("GgsSwitch", "select")
        f.addRow("", GgsSwitch(checked=True))
        self._calls(f, "GgsSwitch")

        f = group("GgsButtonBox", "select")
        f.addRow("", GgsButtonBox())
        self._calls(f, "GgsButtonBox")


        _specs = (
            ("GgsBigButtonStyle1", False, False, False, True,
             "大按钮样式1", "整体按钮，无激活底色"),
            ("GgsBigCheckButtonStyle1", False, False, False, True,
             "大按钮（勾选）样式1", "整体按钮，激活态底色"),
            ("GgsBigMenuButtonStyle1", True, True, False, True,
             "带菜单大按钮样式1", "三行骨架，点任意处弹菜单"),
            ("GgsBigMenuButtonStyle2", True, True, False, True,
             "带菜单大按钮样式2", "点图标执行菜单首项"),
            ("GgsBigMenuButtonStyle3", True, True, False, True,
             "带菜单大按钮样式3", "点图标执行当前已选项"),
            ("GgsBigMenuButtonStyle4", True, True, False, True,
             "带菜单大按钮样式4", "带激活态容器底色"),
            ("GgsSmallButtonStyle2", False, False, False, False,
             "小按钮样式2", "图标 + 文本"),
            ("GgsSmallCheckButtonStyle2", False, False, False, False,
             "小按钮（勾选）样式2", "可切换：图标 + 文本"),
            ("GgsSmallMenuButtonStyle1", True, False, True, False,
             "小菜单按钮样式1", "图标 + 下拉（无文本）"),
            ("GgsSmallMenuButtonStyle2", True, False, False, False,
             "小菜单按钮样式2", "图标 + 文本 + 下拉"),
            ("GgsSmallButtonStyle1", False, False, True, False,
             "小按钮样式1", "图标（无文本）"),
            ("GgsSmallCheckButtonStyle1", False, False, True, False,
             "小按钮（勾选）样式1", "可切换：图标（无文本）"),
        )
        _by_variant = {s[0]: s for s in _specs}
        _families = (
            ("GgsBigButton", ("GgsBigButtonStyle1", "GgsBigCheckButtonStyle1")),
            ("GgsBigMenuButton", ("GgsBigMenuButtonStyle1",
                                  "GgsBigMenuButtonStyle2",
                                  "GgsBigMenuButtonStyle3",
                                  "GgsBigMenuButtonStyle4")),
            ("GgsSmallButton", ("GgsSmallButtonStyle1", "GgsSmallButtonStyle2")),
            ("GgsSmallCheckButton", ("GgsSmallCheckButtonStyle1",
                                    "GgsSmallCheckButtonStyle2")),
            ("GgsSmallMenuButton", ("GgsSmallMenuButtonStyle1",
                                    "GgsSmallMenuButtonStyle2")),
        )
        for _fam, _vs in _families:
            f = group(_fam, "select")
            row = QHBoxLayout()
            row.setSpacing(14)
            for _idx, _v in enumerate(_vs):
                _lab = _by_variant[_v][6]
                cell = QVBoxLayout()
                cell.setSpacing(2)
                _checkable = _v in ("GgsBigCheckButtonStyle1",
                                    "GgsSmallCheckButtonStyle1",
                                    "GgsSmallCheckButtonStyle2")
                cell.addWidget(self._entity(_v, checked=_checkable,
                                            tip=_v + "：" + _lab),
                               0, Qt.AlignmentFlag.AlignHCenter)
                cap = QLabel(i18n.tr("Style{0}").format(_idx + 1))
                cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                cell.addWidget(cap)
                row.addLayout(cell)
            row.addStretch(1)
            f.addRow(i18n.tr("样例"), row)
            self._calls(f, *_vs)

        f = group("GgsMediumButton", "select")
        srow = QHBoxLayout()
        srow.setSpacing(14)
        _txt = i18n.tr("样例")
        for _style, _cap, _mk in (
            (1, i18n.tr("图标 + 文本"),
             lambda: GgsMediumButtonStyle1("table", _txt, tip=_cap)),
            (2, i18n.tr("可切换（选中保留边框）"),
             lambda: GgsMediumButtonStyle2("table", _txt, tip=_cap,
                                               checked=True)),
            (3, i18n.tr("带菜单"),
             lambda: GgsMediumButtonStyle3("table", _txt,
                                               menu=self._sample_menu(),
                                               tip=_cap)),
        ):
            scell = QVBoxLayout()
            scell.setSpacing(2)
            _b = _mk()
            scell.addWidget(_b, 0, Qt.AlignmentFlag.AlignHCenter)
            scap = QLabel(i18n.tr("Style{0}").format(_style))
            scap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            scell.addWidget(scap)
            srow.addLayout(scell)
        srow.addStretch(1)
        f.addRow(i18n.tr("样例"), srow)
        self._calls(f, "GgsMediumButtonStyle1", "GgsMediumButtonStyle2",
                    "GgsMediumButtonStyle3")
        return sa

    def _sample_menu(self):
        m = QMenu(self)
        for t in ("选项一", "选项二", "选项三"):
            m.addAction(QAction(icons.icon("select"), i18n.tr(t), m))
        return m

    def _check_menu(self):
        return self._follow_menu()

    def _follow_menu(self):
        m = QMenu(self)
        grp = QActionGroup(m)
        grp.setExclusive(True)
        for i, (nm, t) in enumerate((("select", "选项一"),
                                     ("table", "选项二"),
                                     ("crs", "选项三"))):
            a = QAction(icons.icon(nm, size=32), i18n.tr(t), m)
            try:
                a.setProperty("ggsIconName", nm)
            except Exception:
                _log.exception("silent exception in _follow_menu")
            a.setCheckable(True)
            grp.addAction(a)
            m.addAction(a)
            if i == 0:
                a.setChecked(True)
        return m

    def _entity(self, variant, checked=False, tip=""):
        m = self._sample_menu()
        txt = i18n.tr("样例")
        if variant == "GgsBigButtonStyle1":
            w = GgsBigButtonStyle1("table", txt, tip=tip)
        elif variant == "GgsBigCheckButtonStyle1":
            w = GgsBigCheckButtonStyle1("table", txt, tip=tip,
                                        checked=checked)
        elif variant == "GgsBigMenuButtonStyle1":
            w = GgsBigMenuButtonStyle1("table", txt, m, tip=tip)
        elif variant == "GgsBigMenuButtonStyle2":
            w = GgsBigMenuButtonStyle2("table", txt, m, tip=tip)
        elif variant == "GgsBigMenuButtonStyle3":
            w = GgsBigMenuButtonStyle3("table", txt, self._check_menu(),
                                       tip=tip)
        elif variant == "GgsBigMenuButtonStyle4":
            w = GgsBigMenuButtonStyle4("table", txt, self._follow_menu(),
                                       tip=tip, checked=checked)
        elif variant == "GgsSmallButtonStyle1":
            w = GgsSmallButtonStyle1("table", tip)
        elif variant == "GgsSmallButtonStyle2":
            w = GgsSmallButtonStyle2("table", txt, tip)
        elif variant == "GgsSmallCheckButtonStyle1":
            w = GgsSmallCheckButtonStyle1("table", tip, checked=checked)
        elif variant == "GgsSmallCheckButtonStyle2":
            w = GgsSmallCheckButtonStyle2("table", txt, tip,
                                          checked=checked)
        elif variant == "GgsSmallMenuButtonStyle1":
            w = GgsSmallMenuButtonStyle1("table", m, tip)
        elif variant == "GgsSmallMenuButtonStyle2":
            w = GgsSmallMenuButtonStyle2("table", txt, m, tip)
        else:
            w = QLabel(variant)
        return self._holder(w)

    def _holder(self, w):
        holder = GgsRibbonPage(self)
        holder.setSizePolicy(QSizePolicy.Policy.Fixed,
                             QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(w, 0, Qt.AlignmentFlag.AlignLeft
                      | Qt.AlignmentFlag.AlignTop)
        return holder

    def _ribbon_variant(self, variant, dropdown=False, style2=False,
                        icon_only=False, big=True, tip="", checkable=False):
        hosts = getattr(self, "_btn_hosts", None)
        if hosts is None:
            hosts = self._btn_hosts = []
        g = RibbonGroup("")
        hosts.append(g)
        action = QAction(icons.icon("table"), i18n.tr("样例"), self)
        if checkable:
            action.setCheckable(True)
            action.setChecked(True)
        before = set(g._drop_state)
        if dropdown:
            g.add_dropdown(action, self._sample_menu(), big=big, tip=tip,
                           style2=style2, variant=variant)
        elif variant in ("GgsBigButtonStyle1", "GgsBigButtonStyle2",
                         "GgsBigCheckButtonStyle1"):
            g._add_style01(action, tip=tip, variant=variant)
        else:
            g.add_action(action, big=big, tip=tip, icon_only=icon_only,
                         variant=variant)
        new = [k for k in g._drop_state if k not in before]
        root = new[0] if new else g._btn_meta[-1][0]
        root.setParent(None)
        holder = GgsRibbonPage(self)
        holder.setSizePolicy(QSizePolicy.Policy.Fixed,
                             QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(root, 0, Qt.AlignmentFlag.AlignLeft
                      | Qt.AlignmentFlag.AlignTop)
        return holder

    def _page_inputs(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsLineEdit", "logo")
        _le = GgsLineEdit()
        _le.setPlaceholderText(i18n.tr("请输入内容"))
        f.addRow("", _le)
        self._calls(f, "GgsLineEdit")

        f = group("GgsComboBox", "logo")
        gcmb = GgsComboBox()
        for _t in ("选项一", "选项二", "选项三"):
            gcmb.addItem(i18n.tr(_t))
        f.addRow("", gcmb)
        self._calls(f, "GgsComboBox")

        f = group("GgsDockComboBox", "logo")
        _tc = GgsDockComboBox()
        for _t in ("选项一", "选项二"):
            _tc.addItem(i18n.tr(_t))
        f.addRow("", _tc)
        self._calls(f, "GgsDockComboBox")

        f = group("GgsSearchEdit", "logo")
        _se = GgsSearchEdit()
        _se.setPlaceholderText(i18n.tr("搜索…"))
        f.addRow("", _se)
        self._calls(f, "GgsSearchEdit")

        f = group("GgsSearchBar", "logo")
        f.addRow("", GgsSearchBar())
        self._calls(f, "GgsSearchBar")

        f = group("GgsSliderSpin", "logo")
        ss = GgsSliderSpin(minimum=0, maximum=100, suffix="%")
        ss.setValue(60)
        f.addRow("", ss)
        self._calls(f, "GgsSliderSpin")

        f = group("GgsExtentPicker", "extent")
        _pk = GgsExtentPicker(modes=("view", "layer", "custom"))
        _pk.set_reference_extent(GgsRectangle(100000.0, 3000000.0,
                                              200000.0, 3100000.0))
        f.addRow("", _pk)
        self._calls(f, "GgsExtentPicker")

        f = group("GgsCrsSelector", "logo")
        ctl_crs = GgsCrsSelector(crs="EPSG:4326", label="坐标系")
        ctl_crs.set_base_crs("EPSG:4326")
        ctl_crs.set_layers(["EPSG:4326", "EPSG:4326", "EPSG:3857", "EPSG:4490"])
        f.addRow("", ctl_crs)
        self._calls(f, "GgsCrsSelector")
        return sa

    def _page_colors(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsColorField", "logo")
        f.addRow("", GgsColorField("#3D8BFF"))
        self._calls(f, "GgsColorField")

        f = group("GgsColorSwatch", "logo")
        row_sw = QHBoxLayout()
        row_sw.setSpacing(14)
        for _shp in ("rect", "line", "dot"):
            _cell = QVBoxLayout()
            _cell.setSpacing(2)
            _sw = GgsColorSwatch(color="#3D8BFF", shape=_shp)
            _sw.setFixedSize(48, 18)
            _cell.addWidget(_sw, 0, Qt.AlignmentFlag.AlignHCenter)
            _cap = QLabel(_shp)
            _cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            _cell.addWidget(_cap)
            row_sw.addLayout(_cell)
        row_sw.addStretch(1)
        f.addRow("", row_sw)
        self._calls(f, "GgsColorSwatch")

        f = group("GgsColorButton", "logo")
        f.addRow("", GgsColorButton(color="#E6A23C"))
        self._calls(f, "GgsColorButton")

        f = group("GgsColorRampField", "logo")
        fld = GgsColorRampField()
        fld.setItems(
            [("demo1", i18n.tr("色带一"),
              ["#2C7BB6", "#ABD9E9", "#FFFFBF"]),
             ("demo2", i18n.tr("色带二"),
              ["#D7191C", "#FDAE61", "#FFFFBF"])],
            current="demo1")
        f.addRow("", fld)
        self._calls(f, "GgsColorRampField")

        f = group("GgsColorRampBar", "logo")
        ramp = GgsColorRampBar()
        ramp.setColors(["#2C7BB6", "#ABD9E9", "#FFFFBF", "#FDAE61", "#D7191C"])
        f.addRow("", ramp)
        self._calls(f, "GgsColorRampBar")
        return sa

    def _page_io(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsLayerInputWidget", "open")
        wi = GgsLayerInputWidget(kind="vector", title=i18n.tr("输入图层"))
        wi.set_items([(i18n.tr("示例矢量图层") + " A", "lyr_a"),
                      (i18n.tr("示例矢量图层") + " B", "lyr_b")])
        f.addRow("", wi)
        wi2 = GgsLayerInputWidget(kind="raster", title=i18n.tr("输入图层"))
        wi2.set_items([(i18n.tr("示例栅格图层"), "lyr_r")])
        f.addRow("", wi2)
        self._calls(f, "GgsLayerInputWidget")

        f = group("GgsLayerOutputWidget", "save")
        f.addRow("", GgsLayerOutputWidget(kind="vector"))
        f.addRow("", GgsLayerOutputWidget(kind="raster"))
        self._calls(f, "GgsLayerOutputWidget")

        f = group("GgsMultiLayerInputWidget", "open")
        wm = GgsMultiLayerInputWidget(kind="raster",
                                      title=i18n.tr("输入图层（勾选多个）"))
        wm.set_layers([i18n.tr("示例栅格图层") + " A",
                       i18n.tr("示例栅格图层") + " B",
                       i18n.tr("示例栅格图层") + " C"])
        f.addRow("", wm)
        self._calls(f, "GgsMultiLayerInputWidget")

        f = group("GgsFileInputWidget", "folder")
        f.addRow("", GgsFileInputWidget(kind="vector",
                                        title=i18n.tr("输入文件")))
        self._calls(f, "GgsFileInputWidget")

        f = group("GgsFileOutputWidget", "save")
        f.addRow("", GgsFileOutputWidget(kind="vector",
                                         title=i18n.tr("输出文件"),
                                         suffix=".gpkg"))
        self._calls(f, "GgsFileOutputWidget")
        return sa

    def _page_views(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsTreeWidget", "table")
        tree = GgsTreeWidget()
        tree.setHeaderLabels([i18n.tr("列表")])
        for _t in ("选项一", "选项二"):
            QTreeWidgetItem(tree, [i18n.tr(_t)])
        _child = QTreeWidgetItem(tree.topLevelItem(0), [i18n.tr("选项二")])
        _child.setIcon(0, icons.icon("info"))
        tree.expandAll()
        tree.setMaximumHeight(110)
        f.addRow("", tree)
        self._calls(f, "GgsTreeWidget")

        f = group("GgsTreeView", "table")
        _tv = GgsTreeView()
        _mod = QStandardItemModel(_tv)
        for _t in ("选项一", "选项二"):
            _it = QStandardItem(i18n.tr(_t))
            _it.appendRow(QStandardItem(i18n.tr("子项")))
            _mod.appendRow(_it)
        _tv.setModel(_mod)
        _tv.expandAll()
        _tv.setMaximumHeight(110)
        f.addRow("", _tv)
        self._calls(f, "GgsTreeView")

        f = group("GgsTableWidget", "table")
        tbl = GgsTableWidget(2, 3)
        for _r in range(2):
            for _c in range(3):
                tbl.setItem(
                    _r, _c,
                    _QtItem(i18n.tr("选项一") + " %d-%d" % (_r + 1, _c + 1)))
        tbl.setMaximumHeight(96)
        f.addRow("", tbl)
        self._calls(f, "GgsTableWidget")

        f = group("GgsListWidget", "table")
        lst = GgsListWidget()
        for _t in ("选项一", "选项二", "选项三"):
            QListWidgetItem(i18n.tr(_t), lst)
        lst.setMaximumHeight(96)
        f.addRow("", lst)
        self._calls(f, "GgsListWidget")
        return sa

    def _page_status(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsSpinner", "logo")
        row_sp = QHBoxLayout()
        row_sp.setSpacing(10)
        _sp = GgsSpinner(diameter=20)
        _sp.start()
        row_sp.addWidget(_sp)
        row_sp.addWidget(QLabel(i18n.tr("转动中…")))
        row_sp.addStretch(1)
        f.addRow("", row_sp)
        self._calls(f, "GgsSpinner")

        f = group("GgsRenderStatus", "logo")
        row_rs = QHBoxLayout()
        row_rs.setSpacing(14)
        for _st in ("busy", "done"):
            _w = GgsRenderStatus()
            _w.set_state(_st)
            row_rs.addWidget(_w)
        _w = GgsRenderStatus()
        _w.set_clickable(False)
        row_rs.addWidget(_w)
        row_rs.addStretch(1)
        f.addRow("", row_rs)
        self._calls(f, "GgsRenderStatus")

        f = group("GgsDimLabel", "logo")
        f.addRow("", GgsDimLabel(i18n.tr("这是一段弱化说明文字")))
        self._calls(f, "GgsDimLabel")

        f = group("GgsMessageBar", "info")
        bar = GgsMessageBar()
        bar.setMinimumHeight(32)
        bb = QPushButton(i18n.tr("弹一条消息"))
        bb.clicked.connect(
            lambda: bar.pushMessage(i18n.tr("消息"),
                                    i18n.tr("这是一条消息条消息。")))
        rowb = QHBoxLayout()
        rowb.setSpacing(8)
        rowb.addWidget(bar, 1)
        rowb.addWidget(bb)
        f.addRow("", rowb)
        self._calls(f, "GgsMessageBar")

        f = group("消息条子件", "info")
        rowm = QHBoxLayout()
        rowm.setSpacing(10)
        rowm.addWidget(GgsMsgText(i18n.tr("消息文本")))
        _mc = GgsMsgClose()
        _mc.setText(i18n.tr("✕"))
        rowm.addWidget(_mc)
        rowm.addStretch(1)
        f.addRow("", rowm)
        self._calls(f, "GgsMsgText", "GgsMsgClose")
        return sa

    def _page_seps(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsDockSepOverlay", "logo")
        rowsep = QHBoxLayout()
        rowsep.setSpacing(6)
        rowsep.addWidget(QLabel(i18n.tr("左")))
        _sl = GgsDockSepOverlay(True)
        _sl.setFixedWidth(8)
        rowsep.addWidget(_sl)
        rowsep.addWidget(QLabel(i18n.tr("右")))
        rowsep.addStretch(1)
        f.addRow("", rowsep)
        self._calls(f, "GgsDockSepOverlay")

        f = group("GgsSepH", "logo")
        rowsep2 = QHBoxLayout()
        rowsep2.setSpacing(6)
        rowsep2.addWidget(QLabel(i18n.tr("左")))
        rowsep2.addWidget(GgsSepH(), 1)
        rowsep2.addWidget(QLabel(i18n.tr("右")))
        f.addRow("", rowsep2)
        self._calls(f, "GgsSepH")

        f = group("GgsSepV", "logo")
        rowsep3 = QHBoxLayout()
        rowsep3.setSpacing(6)
        rowsep3.addWidget(QLabel(i18n.tr("左")))
        rowsep3.addWidget(GgsSepV())
        rowsep3.addWidget(QLabel(i18n.tr("右")))
        rowsep3.addStretch(1)
        f.addRow("", rowsep3)
        self._calls(f, "GgsSepV")

        f = group("GgsGroupCard", "settings")
        f.addRow(i18n.tr("键"), QLabel(i18n.tr("值示例")))
        _span = QHBoxLayout()
        _span.setSpacing(8)
        _span.addWidget(GgsColorField("#67C23A"))
        _span.addStretch(1)
        f.addRow(_span)
        self._calls(f, "GgsGroupCard")

        f = group("参数分组（标准）", "settings")
        _grp_std = QGroupBox(i18n.tr("示例分组"))
        _gf = QFormLayout(_grp_std)
        _gf.setContentsMargins(8, 8, 8, 8)
        _gf.setSpacing(4)
        _gcb = GgsComboBox()
        for _t in ("单一符号", "唯一值", "分级色彩"):
            _gcb.addItem(i18n.tr(_t))
        _gf.addRow(i18n.tr("渲染方式"), _gcb)
        _gsp = GgsSliderSpin(minimum=0, maximum=100, suffix=" %")
        _gsp.setValue(100)
        _gf.addRow(i18n.tr("不透明度"), _gsp)
        _gcol = GgsColorField("#3D8BFF")
        _gf.addRow(i18n.tr("颜色"), _gcol)
        f.addRow(_grp_std)
        return sa

    def _page_dialogs(self):
        sa, group = self._gal_grouped_page()

        f = group("GgsMsgBox", "info")
        row = QHBoxLayout()
        row.setSpacing(8)
        for _lv, _key in (("信息", "information"), ("警告", "warning"),
                          ("错误", "critical"), ("询问", "question")):
            _b = QPushButton(i18n.tr(_lv))
            _b.clicked.connect(
                lambda checked=False, _k=_key: self._pop_msg(_k))
            row.addWidget(_b)
        row.addStretch(1)
        f.addRow("", row)
        self._calls(f, "GgsMsgBox")

        f = group("GgsDialog", "settings")
        b = QPushButton(i18n.tr("打开对话框样例"))
        b.clicked.connect(self._pop_sample)
        f.addRow("", b)
        self._calls(f, "GgsDialog")

        f = group("GgsInputDialog", "settings")
        b2 = QPushButton(i18n.tr("打开输入对话框样例"))
        b2.clicked.connect(self._pop_input)
        f.addRow("", b2)
        self._calls(f, "GgsInputDialog")

        f = group("GgsFileDialog", "settings")
        b3 = QPushButton(i18n.tr("打开文件对话框样例"))
        b3.clicked.connect(self._pop_file)
        f.addRow("", b3)
        self._calls(f, "GgsFileDialog")

        f = group("Dock 标题栏骨架件", "settings")
        rowd = QHBoxLayout()
        rowd.setSpacing(14)
        rowd.addWidget(GgsDockTitleLabel(i18n.tr("面板标题")))
        _dtb = GgsDockTitleBtn()
        _dtb.setText(i18n.tr("面板按钮"))
        rowd.addWidget(_dtb)
        rowd.addStretch(1)
        f.addRow("", rowd)
        self._calls(f, "GgsDockTitleLabel", "GgsDockTitleBtn")

        f = group("GgsView", "settings")
        _v = GgsView("map", i18n.tr("样例视图"))
        _vl = QVBoxLayout(_v)
        _vl.setContentsMargins(12, 10, 12, 10)
        _vl.addWidget(QLabel(i18n.tr("一切视图的基类（地图 / 布局 / 模型）")))
        _v.setMinimumHeight(64)
        f.addRow("", _v)
        self._calls(f, "GgsView")

        f = group("GgsViewTabs", "table")
        vt = GgsViewTabs()
        vt.set_views([("map", i18n.tr("地图"), True, ""),
                      ("layout", i18n.tr("布局"), True, "")], "map")
        f.addRow("", vt)
        self._calls(f, "GgsViewTabs")
        return sa

    def _pop_msg(self, kind):
        text = {
            "information": i18n.tr("这是一条信息消息。"),
            "warning": i18n.tr("这是一条警告消息。"),
            "critical": i18n.tr("这是一条错误消息。"),
            "question": i18n.tr("这是一个询问，需要你确认。"),
        }.get(kind, "")
        fn = getattr(GgsMsgBox, kind, None)
        if callable(fn):
            fn(self, i18n.tr("消息"), text)

    def _pop_sample(self):
        dlg = _SampleShellDialog(self)
        dlg.exec()

    def _pop_input(self):
        GgsInputDialog.getText(self, "输入对话框样例", "请输入内容")

    def _pop_file(self):
        GgsFileDialog.getOpenFileName(self, i18n.tr("文件对话框样例"))


def _QtItem(text):
    from PySide6.QtWidgets import QTableWidgetItem
    return QTableWidgetItem(text)


class GgsRibbonPage(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonPage")
