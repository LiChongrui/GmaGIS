# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import os
import re


_DARK = {
    "window":      "#1e2229",
    "panel":       "#242932",
    "panel_hi":    "#313742",
    "panel_dn":    "#393f49",
    "dock_sel":    "#393f49",
    "group_bg":    "#242932",
    "workspace":   "#2a2f38",
    "group_hi":    "#2b3039",
    "input":       "#17191f",
    "border":      "#333941",
    "border_soft": "#2a2e36",
    "hud_border":  "#c8d0da",
    "text":        "#d9dee6",
    "text_dim":    "#b0bac9",
    "status_cap":  "#b0bac9",
    "text_disabled": "#5d6672",
    "accent":      "#3d7fd1",
    "accent_hi":   "#5a97e2",
    "accent_soft": "#3c4758",
    "accent_text": "#ffffff",
    "contextual":  "#4db8d9",
    "app_btn":     "#2d6fd1",
    "app_btn_hi":  "#5a97e2",
    "menu":        "#25272d",
    "tooltip_bg":  "#0f1216",
    "tooltip_fg":  "#e2e8f0",
    "success":     "#3fa45b",
    "s2_hover":    "#364151",
    "s2_down":     "#313b48",
    "s2_border":   "#515c6c",
    "focus":       "#969ca8",
    "check_border": "#333941",
    "check_on":    "#b0bac9",
    "dock_hover":  "#4a5260",
    "dock_active": "#4e5f74",
    "link":       "#3d7fd1",
}

_LIGHT = {
    "window":      "#f3f4f7",
    "panel":       "#ffffff",
    "panel_hi":    "#e7e9ed",
    "panel_dn":    "#d9dce1",
    "dock_sel":    "#ffffff",
    "group_bg":    "#ffffff",
    "workspace":   "#8A8F96",
    "group_hi":    "#efeff1",
    "input":       "#ffffff",
    "border":      "#c9cdd4",
    "border_soft": "#e3e5e8",
    "hud_border":  "#5b6472",
    "text":        "#2d3440",
    "text_dim":    "#5c6572",
    "status_cap":  "#2d3440",
    "text_disabled": "#a4adb9",
    "accent":      "#0078d4",
    "accent_hi":   "#1a8fe0",
    "accent_soft": "#c9d3df",
    "accent_text": "#ffffff",
    "contextual":  "#0fa0ce",
    "app_btn":     "#005a9e",
    "app_btn_hi":  "#0078d4",
    "menu":        "#ffffff",
    "tooltip_bg":  "#f9fafc",
    "tooltip_fg":  "#2d3440",
    "success":     "#2e8b46",
    "s2_hover":    "#d7e6f3",
    "s2_down":     "#d9e4eb",
    "s2_border":   "#adadad",
    "focus":       "#6e7480",
    "check_border": "#7e8590",
    "check_on":    "#5c6572",
    "dock_hover":  "#9aa1ad",
    "dock_active": "#7d8ba0",
    "link":       "#5a7d9e",
}


def _theme_of(name):
    return _LIGHT if name == "light" else _DARK


OK_COLOR = "#3d9e63"
ERR_COLOR = "#d4553f"
WARN_COLOR = "#d29a4f"


def progress_face_color(state):
    if state == "done":
        return OK_COLOR
    if state == "fail":
        return ERR_COLOR
    if state == "cancel":
        try:
            from ggis.common.styling import icons as _icons
            dark = bool(_icons.is_dark())
        except Exception:
            exc_note("progress_face_color @ ggis/common/styling/themes.py:196")
            dark = True
        return (_DARK if dark else _LIGHT)["text_dim"]
    return None

_ICON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "resources", "icons")


def _arrow_url(name):
    for theme in ("dark", "light"):
        tag = "_" + theme
        i = name.find(tag)
        if i > 0 and name.endswith(".svg"):
            head = name[:i]
            tail = name[i + len(tag):]
            name = theme + "/" + head + tail
            break
    p = os.path.join(_ICON_DIR, name).replace("\\", "/")
    return 'url("{}")'.format(p)


_DARK["combo_arrow"] = _arrow_url("combo_arrow_dark.svg")
_LIGHT["combo_arrow"] = _arrow_url("combo_arrow_light.svg")

_DARK["branch_open"] = _arrow_url("branch_open_dark.svg")
_DARK["branch_closed"] = _arrow_url("branch_closed_dark.svg")
_LIGHT["branch_open"] = _arrow_url("branch_open_light.svg")
_LIGHT["branch_closed"] = _arrow_url("branch_closed_light.svg")


_DARK["menu_check"] = _arrow_url("menu_check_dark.svg")
_LIGHT["menu_check"] = _arrow_url("menu_check_light.svg")

_DARK["tree_check"] = _DARK["menu_check"]
_LIGHT["tree_check"] = _LIGHT["menu_check"]

_DARK["radio_dot"] = _arrow_url("radio_dot_dark.svg")
_LIGHT["radio_dot"] = _arrow_url("radio_dot_light.svg")


_TEMPLATE = """
* {{ outline: none; }}
QMainWindow, QDockWidget, QWidget#central {{
    background: {window};
}}
QMainWindow::separator {{
    /* dock 与画布之间、相邻 dock 之间的留白。它同时是**拖动改 dock
       宽度的热区**，所以 here 的 width/height 决定热区大小（5px），
       不能改小——改小了就拖不动。

       注意这里**不再**写 `:hover` 上色：那样 hover 时整条 5px 会变成
       一根灰柱子（用户报「太粗」）。观感交给 ui/separators.py 的自绘浮层
       ——平时居中一条 1px 细线，悬停时只把这条线加强一档，宽度不变。
       浮层是鼠标穿透的，拖拽仍由这里的 5px 热区接管。 */
    background: transparent;
    width: 5px;
    height: 5px;
}}

/* 画布（地图区域）去边框 */
GgsMapCanvas#GgsMapCanvas {{
  border: none;
}}

QToolTip {{
    /* ⚠ 悬停提示一律**方角**，不要加 `border-radius`：QToolTip 是
       **不透明的顶级弹出窗口**，QSS 只把圆角内的区域画出来，四个直角外
       露出窗口自身底色——暗色下底色近黑看不出来，亮色主题下就是四个
       明显的黑角（用户："圆角处怪怪的"）。setMask 可以裁掉角，但掩码
       无抗锯齿、DPR 1.25 下边缘锯齿更丑；自绘 tooltip 要动全部调用点。
       ⇒ 干净解只有方角（与 VS / Office 的提示条一致）。 */
    background: {tooltip_bg}; color: {tooltip_fg};
    border: 1px solid {border}; padding: 4px 7px; font-size: 12px;
}}

/* ---------------- 菜单栏 ---------------- */
QMenuBar {{
    background: {panel}; color: {text};
    border-bottom: 1px solid {border_soft};
    padding: 1px 4px;
}}
QMenuBar::item {{
    background: transparent; padding: 4px 9px; border-radius: 4px;
}}
QMenuBar::item:selected {{ background: {panel_hi}; }}
QMenuBar::item:pressed {{ background: {panel_dn}; }}

/* ---------------- 菜单 ---------------- */
QMenu {{
    background: {menu}; color: {text};
    border: 1px solid {border}; border-radius: 6px; padding: 3px;
}}
QMenu::item {{
    padding: 5px 14px 5px 12px;
    border-radius: 4px;
    background: transparent;
    height: 18px;
}}
QMenu#GgsLayerTreeMenu::item {{
    min-width: 144px;
    padding: 5px 20px 5px 14px;
    height: 18px;
}}
QMenu::item:checked {{ background: {panel_hi}; }}
QMenu::item:selected {{ background: {panel_hi}; color: {text}; }}
QMenu::item:disabled {{ color: {text_disabled}; }}
QMenu::separator {{
    height: 1px; background: {border_soft};
    margin: 3px 8px 4px;
}}
QMenu::icon {{ padding-left: 12px; }}

/* ---------------- 工具栏 ---------------- */
QToolBar {{
    background: {panel}; border: none; spacing: 1px; padding: 2px 3px;
}}
QToolBar::separator {{
    background: {border_soft}; width: 1px; margin: 4px 3px;
}}
QToolBar QToolButton {{
    color: {text}; padding: 3px; border-radius: 6px; border: none;
    background: transparent;
}}
QToolBar QToolButton:hover {{ background: {panel_hi}; }}
QToolBar QToolButton:pressed {{ background: {panel_dn}; }}
QToolBar QToolButton:checked {{
    background: {panel_dn};
    border: 1px solid {border_soft};
    color: {text};
}}

/* ---------------- 停靠面板 ---------------- */
QDockWidget {{
    color: {text}; titlebar-close-icon: none; titlebar-normal-icon: none;
    /* QSS 的 border/background 在 QDockWidget 上不可靠
       （自绘标题栏下实测不渲染）——卡片框架由 GgsDockWidget
       .paintEvent 统一铺底+描边，标题栏/包裹层全部透明 */
}}
QDockWidget::title {{
    background: {window}; padding: 5px 10px; color: {text_dim};
    border-bottom: 1px solid {border_soft}; font-size: 12px;
}}
/* 自绘停靠标题栏（GgsDockTitleBar）：视觉对齐主窗口标题栏——
   同用窗口底色 + 底部弱分隔线，顶部两角随面板圆角 */
GgsDockTitleBar {{
    background: transparent;
    /* 底部分隔线由 paintEvent 自绘、整宽通铺，与下面
       QFrame#GgsDockToolbar 的 border-bottom 等宽等高（用户报
       "标题栏底线左右有缝隙"+"两条线样式要一致"） */
    border-top-left-radius: 5px; border-top-right-radius: 5px;
}}
QLabel#GgsDockTitleLabel {{
    background: transparent; color: {text};
    font-size: 12px; font-weight: 600;
}}
/* 面板内容包裹层（GgsDockWidget.setWidget 包的一层）：
   不透明内容控件会盖住 QDockWidget 自身边框，边框与底部圆角
   改画在这层——布局四周留 1px 让边框露出来 */
QWidget#GgsDockBody {{
    /* 不再自画边框/底色（外框统一在 QDockWidget 上），
       只留四周 1px 空隙让外框露出来 */
    background: transparent;
}}
/* round53d：dock 内容直接铺进卡片。GgsDockBody 直接子级的树/列表/
   文本区不再套通用「输入框卡片」（背景+边框+圆角）——dock 卡片内
   又嵌一层圆角框（浏览器/日志等面板实测）。图层树不受影响：
   layertree.retheme() 的控件级样式优先级更高，且早已去框融入面板。 */
QWidget#GgsDockBody > QTreeWidget,
QWidget#GgsDockBody > QTreeView,
QWidget#GgsDockBody > QListView,
QWidget#GgsDockBody > QTableView,
QWidget#GgsDockBody > QTextEdit,
QWidget#GgsDockBody > QPlainTextEdit {{
    background: transparent; border: none; border-radius: 0;
}}

/* 用户识别 DOCK 的树要显出边框，不要融进面板。
   仅作用于本 DOCK 那棵树（objectName = GgsIdentifyTree），特异度 2 个 id
   压过上面那条 1 个 id 的通用规则；其余 dock 树仍透明无框。
   树仍是 GgsDockBody 直接子级（不套中间容器），只补边框。
   ⇒ 原 `#GgsIdentifyList`（上部图层列表）已随控件删除，
   选择器一并去掉。 */
QWidget#GgsDockBody > QTreeWidget#GgsIdentifyTree {{
    background: transparent;
    border: 1px solid {border};
    /* 圆角由 border-radius 直接负责（与 dock 卡片同半径 6px），
       不再用 setMask 裁剪——setMask 会把边框外半角也裁掉，圆角看着"被挡一块"。
       ⚠ QSS 无 overflow 属性，那条写法会触发 "Unknown property overflow" 告警。 */
    border-radius: 6px;
}}
/* 树上方那行点击坐标。
   用次要色（text_dim）与树里的识别值区分开；文本可选中，不做交互。 */
QLabel#GgsIdentifyCoord {{
    color: {text_dim};
    /* 与树左缘同 1px 对齐：树有 1px 边框 ⇒ 标签左侧补 1px 再加点内边距 */
    padding-left: 2px;
}}


/* 属性表：左上/左下圆角不显示的根因——行号列（垂直表头）与左上角标
   （QTableCornerButton）的方形不透明背景，正好盖住表格自身的圆角弧区。
   （右上不受影响：通用规则给水平表头 :last 补了顶右圆角；右下是视口、
   不画弧区。）这里把表头本体/表头节/角标置为透明，让弧区露出表格自身
   的「1px 边框 + 6px 圆角 + 底色」（该通用规则原样保留，边框不隐藏）；
   表头列分隔线来自通用 border-right/bottom，仍保留。
   选择器挂在表格自身 objectName 上 ⇒ 独立窗口与 DOCK 态都命中
   （挂 #GgsAttributeTableDialog 时 DOCK 不命中 = 上一轮「没有修复」的根因）。 */
QTableView#GgsAttributeTableView QHeaderView,
QTableView#GgsAttributeTableViewFrozen QHeaderView {{
    background: transparent; border: none;
}}
QTableView#GgsAttributeTableView QHeaderView::section,
QTableView#GgsAttributeTableViewFrozen QHeaderView::section {{
    background: transparent;
}}
QTableView#GgsAttributeTableView QTableCornerButton::section,
QTableView#GgsAttributeTableViewFrozen QTableCornerButton::section {{
    background: transparent; border: none;
}}
/* 统一表格（tableview.GgsTableWidget，objectName=GgsTable）：与属性表
   同款圆角修复 —— 行号列/表头/角标透明，弧区露出表格自身的
   「1px 边框 + 6px 圆角」（通用规则，原样保留）。行号列默认隐藏；
   显式打开行号的表（CSV 预览等）靠这里保证左上/左下圆角不被盖。
   表头列分隔线来自通用 border-right/bottom，仍保留。 */
QTableWidget#GgsTable QHeaderView {{
    background: transparent; border: none;
}}
QTableWidget#GgsTable QHeaderView::section {{
    background: transparent;
}}
QTableWidget#GgsTable QTableCornerButton::section {{
    background: transparent; border: none;
}}

/* 坐标转换 DOCK 的表格被
   `QWidget#GgsDockBody > QTableView` 清掉了边框。**修法在面板里**：把表格
   包一层无边框容器 ⇒ 它不再是 GgsDockBody 的直接子级 ⇒ 那条 `>` 规则
   不再命中，表格回到通用的「1px 边框 + 6px 圆角」。这里**不加**规则：
   实测加后代选择器（2 个 id）对 DOCK 内 `setWidget()` 的部件不可靠，
   改结构最稳，也不影响符号系统 DOCK 等其它 GgsTable。 */

GgsDockTitleBtn {{
    background: transparent; border: none; border-radius: 3px;
    padding: 0; color: {text_dim};
}}
GgsDockTitleBtn:hover {{
    background: {panel_hi}; color: {text};
}}
GgsDockTitleBtn:pressed {{
    /* 按下不再用 accent 深蓝（全项目除工程按钮外不允许
       深蓝色块），与主窗口按钮一致走中性按压色 */
    background: {panel_dn}; color: {text};
}}
/* dock 页签化分组底部的标签行（QMainWindowLayout 内建 QTabBar）。
   此前无样式命中，激活页签走 QTabBar 通用规则露出深蓝下划线，与 dock
   卡片风格脱节（用户报"其余的 dock 要改成图层 dock 一样"）。

   （真实主窗口实测 + 方案对比）：选择器从
   `QTabBar#GgsDockTabBar` 改成 **`QMainWindow > QTabBar`**（父选择器）。
   为什么必须换 —— 那条页签栏是 QMainWindowLayout **布局时才造**的：
     * 造出来那一刻 objectName 还是空的 ⇒ Qt 首次 polish 时**按通用
       `QTabBar::tab`**（padding 5px 14px：h=28、每枚页签 74px 宽）匹配；
     * `_name_dock_tabbars()` 之后才补上名字，而 **polish 之后改
       objectName，QSS 不会重算**（`unpolish/polish` 实测同样无效）；
     * 于是只有等用户"**切一下 DOCK**"（raise 触发重新布局）样式才掉过来
       ⇒ 就是用户报的"**启动时底部切换 DOCK 的区域偏大，切换一下又正常**"。
   换成父选择器后 **polish 当场就命中**，不依赖任何命名时机（实测 show 后
   直接就是 h=27 / 每枚 58px，与切换后的稳定值一致）。
   ⚠ `main_window._name_dock_tabbars()` 仍然要留：它不只管样式，
   还挂右键菜单、ElideNone + 滚动按钮，且代码靠 objectName 反查页签栏。 */
QMainWindow > QTabBar {{
    background: transparent;
}}
QMainWindow > QTabBar::tab {{
    /* 左右内边距从 10 收到 6。右侧现在**一定**是"多个面板并成
       一排页签"（见 mainwindow._enforce_right_dock_tabs），五个面板的名字
       在 360px 里按 10px 内距排不下，Qt 会把每个标签都省略成"识…"这种
       一个字——并成选项卡的收益被吃掉了。 */
    background: transparent; color: {text_dim};
    padding: 3px 5px; margin: 1px 0 2px;
    border: 1px solid transparent; border-radius: 6px;
}}
QMainWindow > QTabBar::tab:hover {{
    background: {panel_hi}; color: {text};
}}
QMainWindow > QTabBar::tab:selected {{
    /* ：
       昨晚（）把它改成"底部 2px 横线"（与通用 `QTabBar::tab:selected`
       同一套）—— 用户看了实际效果**不要这条线**。
       ⇒ 激活态只靠"**底色 + 文字 `{text}`**"表达，**四条边全部
       透明**。⚠ `border: 1px solid transparent` 仍要留着：去掉它选中页签会
       比未选中"矮"1px，切换时整行标签会抖一下。
       ⚠ 选中底色用 `{dock_sel}`（双主题专用，见 _DARK/_LIGHT 同名键）：
       亮色 = panel(白)，与改前一致；暗色 = 比 window 明显亮一档的 panel_dn，
       解决"暗色选中态只靠 panel、与 window 仅差一丁点、看不出选中"的不统一。
       仍**不加任何边框**（用户定稿"四边全透明"）。 */
    background: {dock_sel}; color: {text};
    border: 1px solid transparent;
}}
/* 面板内嵌工具条（图层树/日志等的按钮行）。
   此前完全没有规则：QToolButton 通用规则是 transparent 无边框，
   按钮既不显示底也不显示悬停反馈，看起来"点不到"。这里给出固定
   方形热区 + 悬停/按下底色，与工具栏的手感一致。 */
QFrame#GgsDockToolbar {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {border_soft};
}}
/* 。固定高度滚动区裹一层带边框的 QFrame。 */
QFrame#GgsNewLayerFieldsFrame {{
    background: {input};
    border: 1px solid {border};
    border-radius: 6px;
}}
QFrame#GgsNewLayerFieldsFrame QScrollArea {{
    background: transparent;
    border: none;
}}
/* —— 它原先没有任何规则 ⇒ 落到 QToolButton
   的通用态（透明无边框）⇒ 在面板里几乎"看不见"。现在给足边框 + 底色 + 悬停
   反馈；比「应用」（主操作）弱一档，但明显是一颗可点的按钮。 */
QToolButton#GgsSymbolButton {{
    background: {input};
    border: 1px solid {border};
    border-radius: 6px;
    color: {text};
    padding: 1px 8px 1px 4px;
    text-align: left;
}}
/* 原来 hover 把边框刷成 `accent`（主色蓝）、pressed 只换底色
   —— 与项目里其它按钮（`#GgsDockToolButton`）的"`panel_hi` 底 + `border` 边"
   不是一套。现在**对齐既有按钮的观感**。 */
QToolButton#GgsSymbolButton:hover {{
    background: {panel_hi};
    border-color: {border};
}}
QToolButton#GgsSymbolButton:pressed {{
    background: {panel_dn};
    border-color: {border};
}}
QToolButton#GgsSymbolButton:disabled {{
    color: {text_dim};
    border-color: {border_soft};
}}
/* 这里原来有
   一组 `QPushButton#GgsSymFold`（的"分级列表折叠标题条"）。折叠功能
   已整块撤掉（分类页 就删了）⇒ **规则一并去掉**，别再给
   `GgsSymFold` 写样式（那个 objectName 已无调用点）。 */
/* **也换成图标**"）：这类**纯图标按钮**
   （「标注值」的重置、「调色板」的重置）——
   `QToolButton.setAutoRaise(True)` 在 QSS 生效后会**失去作用**（Qt 的规矩：
   一旦给按钮写了 background/border，autoRaise 就不管了），所以透明底与
   "悬停才浮起"都得自己写，否则会出现一个灰方块。
   ⚠ **「标注值」的重置按钮已经撤掉**（标注值改成只读标签，没有可
   重置的东西）⇒ 那些选择器一并去掉。
   面板里所有**列表动作按钮**（规则 / 唯一值 / 分级的
   「新增 / 删除 / 插入 / 全部添加」）统一走 `#GgsSmallButtonStyle1`
   （都是 `symbology._icon_button()` 造出来的无边框图标按钮）⇒ 与「调色板
   重置」共用同一套观感。 */
QToolButton#GgsSymRasPalReset, QToolButton#GgsSmallButtonStyle1 {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 2px;
}}
QToolButton#GgsSymRasPalReset:hover, QToolButton#GgsSmallButtonStyle1:hover {{
    background: {panel_hi};
    border-color: {border};
}}
QToolButton#GgsSymRasPalReset:pressed, QToolButton#GgsSmallButtonStyle1:pressed {{
    background: {border_soft};
}}
QToolButton#GgsSymRasPalReset:disabled, QToolButton#GgsSmallButtonStyle1:disabled {{
    background: transparent; border-color: transparent;
}}
/* 可切换图标按钮（全部要素 / 所选要素 互斥切换）；常态无底无框、
   悬停浮起、激活（checked）态给 accent_soft 底色 + accent 边框。
   控件正式名 `GgsSmallCheckButtonStyle1`。 */
QToolButton#GgsSmallCheckButtonStyle1 {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 2px;
}}
QToolButton#GgsSmallCheckButtonStyle1:hover {{
    background: {panel_hi};
    border-color: {border};
}}
QToolButton#GgsSmallCheckButtonStyle1:checked {{
    background: {accent_soft};
    border-color: {border};
    text-align: center;
}}
QToolButton#GgsSmallCheckButtonStyle1:disabled {{
    background: transparent; border-color: transparent;
}}
/* `GgsStandardButton` 是**标准按钮** —— 继承
   QPushButton，随全局 `QPushButton` 主题（即确定 / 取消 / 应用那套观感），
   **不再**用 QToolButton 皮肤（原 `GgsStandardIconButton` 命名与样式都错）。
   全局 `QPushButton` 规则已经给了常态 / hover / pressed / disabled / default
   五态，这里只需补"可切换（checked）态"——激活给 accent_soft 底 +
   中性边框，激活态一眼可见。 */
/* `GgsStandardButton` 是**标准按钮** —— 继承
   QPushButton，随全局 `QPushButton` 主题。图标 + 文本**整体居中**（与
   确定 / 取消 / 应用那套观感一致），上下左右留白对称（padding 沿用全局
   的 5px 16px）。这里只补"常态文本居中"，避免勾选/未勾选切换时文本位移。 */
QPushButton#GgsStandardButton {{
    text-align: center;
}}
/* 可切换（checked）态 —— 激活给 `accent_soft` 底 +
   **中性边框**（可切换图标按钮的 checked 态同口径，激活态一眼可见）。
   ⚠ 边框**不得用蓝（accent）**：用户明确"本项目只有工程按钮用蓝色"，
   其它位置一律不允许蓝色边框 ⇒ 这里用中性 `border`（深 / 浅主题各一档）；
   蓝色只留给工程按钮与功能区底部激活横线。 */
QPushButton#GgsStandardButton:checked {{
    background: {accent_soft};
    border-color: {border};
}}
/*
   栅格页「拉伸设置 → 值」的两个数值是**只读展示**（`QLabel`），与它下面那行
   可编辑的「标注」要一眼区分开 ⇒ 用次要色（`text_dim`）。
   ⚠ 只淡"值"，别去动行标签（那是 `QFormLayout` 的标签列，改了会与整页不齐）。 */
QLabel#GgsSymRasValue {{
    color: {text_dim};
}}
/*
   符号系统 / 标注面板顶部那条分隔线（`symbology.row_sep` /
   `labeling.row_sep`，都是一个 `QFrame(Shape.HLine)` + objectName
   `GgsSepH`），以前**没有任何 QSS** —— 于是它吃 Qt 自己那套"下沉式"
   frame 绘制：Fusion 风格下是**中灰 + 一圈亮暗双色**，比面板里任何一条
   1px 边框都粗、都深，夹在「渲染方式」和参数页之间就是一根扎眼的分割条。
   现在按主题的边框色画一条 1px 实线（`max-height` 把内容高钉成 1px，
   不然 QFrame 会按 sizeHint 撑成 3~4px 的立体条）。 */
QFrame#GgsSepH {{
    border: none;
    background: {border};
    max-height: 1px;
}}
/* **竖**分隔线（`GgsSepV`）。
   ⚠ 不能复用 `GgsSepH` —— `GgsSepH` 的 `max-height:1px` 会把竖线压成
   1px 高的**点**。这里钉 `max-width:1px`、高度交给布局拉伸，画一条
   1px 宽的竖线；同样只吃主题 `border` 色，随深 / 浅主题刷新。 */
QFrame#GgsSepV {{
    border: none;
    background: {border};
    max-width: 1px;
    min-height: 14px;
}}
/* 紧凑工具条下拉（日志 DOCK / 剖面 DOCK / 光谱 DOCK）：R1a 把原先逐字
   相同的 `#GgsLogFilter` 与 `#GgsToolComboBox` 两条 ID 规则合并为一条按
   `compact` 属性匹配的规则，见本模板下方 QComboBox[compact="true"]。 */
QCheckBox#GgsLogAutoScroll {{
    font-size: 9pt; padding: 0 4px;
}}

/* 消息浮卡（GgsMsgCard，与测量浮窗同款视觉）------------------------ */
QFrame#GgsMsgCard {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 6px;
}}
QLabel#GgsMsgText {{
    background: transparent; border: none;
    color: {text}; font-size: 9pt;
}}
QToolButton#GgsMsgClose {{
    background: transparent; border: none; border-radius: 3px;
    padding: 1px 5px; color: {text_dim}; font-size: 10px;
}}
QToolButton#GgsMsgClose:hover {{
    background: {panel_hi}; color: {text};
}}

/* 标签页（tabify 的停靠面板、以及各对话框里的页签）
   style.qss 在加载顺序上排在我们前面，并且里面 QTabBar::tab 用了
   `border: 0px solid #C0C0C0;` 简写，会覆盖 border-bottom。因此这里
   不用 `border` 简写，而是单独声明各边，确保加载在后时覆盖它。 */
QTabBar::tab {{
    background: {panel}; color: {text_dim};
    border-top: none; border-left: none; border-right: none;
    border-bottom: 2px solid transparent;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
    padding: 5px 14px; margin: 0;
}}
QTabBar::tab:selected {{
    color: {text};
    background: {window};
    /* 这里是全项目
       **最后一处**用 `accent`（#0078d4 蓝）画的边框 —— 选中页签的 2px 下划线。
       选中态本身靠"底色 window + 正文色文字"已经能看清，这条线改用主题灰，
       蓝色就从样式表里彻底消失了。 */
    border-bottom: 2px solid {text_dim};
}}
QTabBar::tab:hover:!selected {{
    color: {text}; background: {panel_hi};
}}
QTabWidget::pane {{ border: 1px solid {border_soft}; border-radius: 6px; }}
/* 属性表 DOCK 里的**图层页签组**不要再
   套一圈边框 —— 它本来就装在 DOCK 卡片里，通用规则的 1px + 6px 圆角在
   这里是多余的第二层框。按对象名只去掉这一处，其它 QTabWidget 不动。 */
QTabWidget#GgsAttrTabs::pane {{ border: none; border-radius: 0px; }}

/* ---------------- 输入控件 ----------------
   圆角统一升到 6px（与面板/卡片一致）；选中/高亮底色用
   accent_soft 低饱和蓝——全项目除工程按钮外不允许深蓝色块 */
QTreeWidget, QTreeView, QListView, QTableView, QTextEdit,
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {input}; color: {text};
    border: 1px solid {border}; border-radius: 6px;
    selection-background-color: {accent_soft}; selection-color: {text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {focus};
}}
/* 单行输入框里的文字**左右各留 6px**，不再贴着边框。
   ⚠ 只写左右 padding（上下写了会顶高控件、破坏 24px 单行口径）；
   只作用于 QLineEdit（多行文本区有自己的 padding，不动）。 */
QLineEdit {{
    padding-left: 6px; padding-right: 6px;
}}
/* 。 */

   /* 24 = 项目自己的"单行控件"口径：搜索框（`ui.framework.searchbar._BAR_H = 24`）、
   `standard._MenuRow`、以及各对话框里一堆 `setFixedHeight(24)` 的按钮。
   写 `min-height` 而不是 `max-height` ⇒ 只**顶高**矮的（纯文本框最矮），
   内容真的更高时（放大字号档位）两边一起长，**始终等高**。
   ⚠ **不含** `QTextEdit / QPlainTextEdit / QTreeView…`（多行/列表，别去动）；
   ⚠ 紧凑场合的控件都自带**显式**高度（功能区小格、带 `compact` 属性的
   工具条下拉是 20/22），布局取最小尺寸时显式最小优先，不会被这里顶高。 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    min-height: 24px;
}}
/*
   实测（`build/_r492et_heights.py`，离屏真控件 + 真样式表）：

       QLineEdit 26 / QComboBox 26 / **QSpinBox 29 / QDoubleSpinBox 29** / 色块 26

   —— 只有**数字框**高 3px：`QAbstractSpinBox` 会在 QSS 的 min-height 之外
   再算一圈自己的边距（上下各一点）。整族补一条 `max-height` 把它钉回同一档
   （24 内容 + 1px 边框 = 26 总高）。
   ⚠ 各处的 ID 规则（`#GgsSearchEdit`（标题栏 22 / 对话框走这条 24）、
   `#GgsPropValue` 15·17、带 `compact` 属性的紧凑下拉 20·22）特异性更高，
   **不受影响**。 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    max-height: 24px;
}}
/* **紧凑工具条下拉**（R1a）：日志 DOCK 的 GgsLogFilter、剖面/光谱 DOCK 的
   GgsDockComboBox 构造里都 setProperty("compact", "true")，共用这一条；
   写在全局 24px 规则之后且带属性选择器，特异性更高，不会被顶高。 */
QComboBox[compact="true"] {{
    min-height: 20px; max-height: 22px;
    padding: 0 6px; font-size: 9pt;
}}
/* **图层树的行内重命名编辑器**（`#GgsTreeRenameEdit`，由
   `panels/layertree.GgsLegendDelegate.createEditor` 打上这个 objectName）。

   上面两条把单行控件钉在"24 内容 + 2 边框 = 26 总高"，而图层树的行是
   **28**（离屏实测 `visualItemRect`）⇒ 重命名框比它要改的那一行**矮一截、
   上下还没对齐**（用户附截图："**重命名内容的大小和当前元素应当水平对齐**"）。

   这里单独放行：18~30 的内容高都允许，**实际高度由
   `updateEditorGeometry()` 按行高给**（行变矮也一样对得上）；内边距收掉，
   框才不会比行胖。 */
QLineEdit#GgsTreeRenameEdit {{
    min-height: 18px;
    max-height: 30px;
    /*
       左内边距收到 0 ——  `updateEditorGeometry()` 已把**框的左边界**摆到
       "图层名"文字的起点（= `::item` 的 padding-left 之后），这里再留 4px
       就会把框里的字顶到文字右边去、看着不齐。右侧仍留 4px 做呼吸。 */
    padding: 0px 4px 0px 0px;
}}
/* **输入控件的"不可用（禁用）态"** —— 用户
   "手动指定区间和百分比设置应当是互斥的，**也应该有不可用状态的样式**！"

   ⚠ 这条**必须自己写**：上面那条 `min-height` 与更早那批把
   `color / background / border` 都**显式**设过 ⇒ 系统默认那种"禁用就灰掉"
   被完全覆盖，`setEnabled(False)` 只让鼠标点不动、**看起来和可用的一模一样**
   （用户因此以为"互斥没生效"）。这里按 `:disabled` 补回来。
   ⚠ `QLabel / QCheckBox / QRadioButton / QPushButton` 的禁用色**另有规则**
   （见模板末尾那几条，用 `{text_disabled}`），别在这里重复写。 */
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background: {window};
    border: 1px solid {border_soft};
    color: {text_disabled};
}}
QComboBox QAbstractItemView:disabled {{
    color: {text_disabled};
}}
/* 下拉箭头：正常态是一枚亮色箭头（见下面的 `QComboBox::down-arrow`），
   框都灰了还挂着一枚亮箭头反而更显眼 ⇒ 禁用时直接不画。 */
QComboBox::down-arrow:disabled {{
    image: none;
}}
/* ---------------- 通用控件尺寸（，**统一入口**）----------------
   用户 "**像一些通用的样式设置，例如文本框宽度等，不要一个一个
   设置，应当有个样式表，统一控制样式！**"

   ⇒ 规矩：凡是"**通用的**尺寸/宽度/高度"，一律写在这一块、按**对象名**给；
   控件代码里只留**结构**（布局 / 信号 / 量程 / 特殊值文本），不再散落
   `setFixedWidth / setMinimumWidth / setMaximumWidth / setMinimumSize`。

   目前收在这里的：

   | 选择器 | 是什么 | 以前散在哪 |
   | --- | --- | --- |
   | 上面那条 `min-height: 24px` | 单行输入家族统一高度 | 无（各家自己长） |
   | `QWidget#GgsSVSquare` | 取色方块的**最小**尺寸 | `color._SVSquare.__init__` |
   | `QSpinBox#GgsColorSpin` | 颜色对话框 6 个通道框的最大宽 | `color` 里逐个 `setMaximumWidth` |
   | `QDoubleSpinBox#GgsRampPosSpin` | 配色编辑器「位置」框 | `color_ramp` 的 `setMaximumWidth(84)` |

   ⚠ 还**没有**收进来的（它们与功能区/工具条的**网格行高**绑在一起，
   动了会改排版，要收得连着那一格一起改）：`workspace._stacked` 里的
   `setFixedHeight(22)` / `setFixedWidth(70)`、`searchbar` 的
   `setMinimumHeight(_BAR_H)`、各处 `setFixedHeight(24)` 的对话框按钮。
   ⚠ `QSpinBox#GgsColorSpin` 的 64px 够放 "100 %" + 上下箭头。 */
QWidget#GgsSVSquare {{
    min-width: 200px; min-height: 150px;
}}
/* 取色时跟随光标的**实时颜色块**（独立小窗，`color._PickerHUD`）。
   用户："**样式要和主题匹配**" —— 外框不铺自绘底色、走这里（里面那个色块由
   `paintEvent` 画，只显示颜色、不带十六进制文字）。 */
/* 取色时的**实时色块** —— 控件**就是**那个色块（没有外框留白），
   。
   （同日晚追加）："**圆角外面应该是透明的！且圆角边框浅色主题下
   染色太浅！**" ⇒
   * 圆角外面透明**不由 QSS 决定** —— 是 `_PickerHUD` 上的
     `WA_TranslucentBackground`（无边框窗口默认有不透明底板，圆角处会露出
     一块方角底色）；
   * 描边改用 `hud_border`（**不跟 `border` 走**）：`border` 是跟面板底对比的，
     而色块浮在画布上、还要衬"任意被采样到的颜色" ⇒ 深色主题给亮描边、
     浅色主题给深描边。
   底色仍必须 transparent：色块由 `_PickerHUD.paintEvent()` 现填，
   底色若给 panel，圆角处会透出一圈面板色。 */
QWidget#GgsPickerHud {{
    background: transparent;
    border: 1px solid {hud_border};
    border-radius: 5px;
}}
QSpinBox#GgsColorSpin {{
    max-width: 64px;
}}
QDoubleSpinBox#GgsRampPosSpin {{
    max-width: 84px;
}}
/* 图层属性「范围」组的**方位标签**（北 / 南 / 西 / 东）——
   与同页的值（`#GgsPropValue`）区分开：标签加粗、值保持正文观感。 */
QLabel#GgsCompassCap {{
    font-weight: 600;
}}
QLineEdit#GgsColorHex {{
    min-width: 84px; max-width: 84px;      /* HEX 框（快选面板 + 对话框共用） */
}}
QLineEdit#GgsRampNameEdit {{
    min-width: 150px;                      /* 配色编辑器的「名称」框 */
}}
QLabel#GgsColorCap {{
    min-width: 46px;                       /* 颜色对话框三行数值的标签列 */
}}
QLabel#GgsColorHead {{
    color: {text_dim};                     /* R/G/B/H/S/V 表头：次要色、居中 */
    font-size: 8pt;
}}
QPlainTextEdit#GgsCrsWkt {{
    max-height: 150px;                     /* 坐标系页的 WKT 块：别把整页吃掉 */
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8pt;
}}
/* 。
   ArcGIS 那一页是"标签 + **纯文本**"，而 `QLineEdit` 在 QSS 里有 input 底
   + 1px 边框 ⇒ 一整页"名称 / 类型 / 要素数 / 坐标"看着像一堆**可编辑的
   输入框**。这里按**对象名**把这些值压成纯文本观感（仍然可选中复制、
   长路径可横向滚动 —— 换成 QLabel 这两样就没了）。
   ⚠ 只作用于这个对象名，**不动全局的只读输入框**。 */
QLineEdit#GgsPropValue {{
    background: transparent;
    border: none;
    padding: 0 2px;
    color: {text};
    /* ：
       这一行原来是"通用的单行输入"高度 24px（见上面那条 `min-height:
       24px`），而它是**纯文本观感**、没有边框也不需要给光标留边 ——
       一页十来行就白白多出 2px×N。ID 选择器的特异性**高于**那条类型
       选择器，所以这里的值生效。
       （同一天："**图层属性右侧项目上下间距太大，不如关于紧凑**"）：
       要比「关于」对话框那种纯 `QLabel` 值行（≈17px + 行距 4）更紧凑 ⇒
       **用 `max-height` 压到 17px**（+ 卡片网格行距 2）。
       ⚠⚠ 压矮**必须写 `max-height`** —— `min-height` 只能"顶高矮的"，
       而这一族的高度实际是被 `sizeHint`（字体 + 内边距）撑出来的，
       光调 `min-height` 永远压不下去。
       ⚠⚠ **这里写的是逻辑 px，不再有任何倍率放大** —— `_scale_px()`
       已于 随 uiscale 一起删除 ⇒ 写 17px 就是 17px。
       17 已是下限（10pt 字约 19px 高），再低会裁字。 */
    min-height: 15px;
    max-height: 17px;
}}
/* ---------------- 模型构建器（）----------------
   `ui/panels/model_builder.py`。节点方块是**自绘**的（配色在控件里按
   `theme_color()` 取），这里只管三处**外壳**：

   * `#GgsModelView`  画布底 —— 用 `panel`（**与自绘节点的 `panel_hi` 左右
                      各差一档**：深色 #242932 / 浅色 #ffffff，而节点是
                      深色 #313742 / 浅色 #e7e9ed ⇒ **两种主题下节点都比
                      画布亮**，一看就是"贴在上面的卡片"。⚠ 别用
                      `panel_dn`：深色主题下它（#393f49）反而**比节点亮**
                      ⇒ 节点看着是凹进去的）；
   * `#GgsModelBar`   进度条压扁（起它长在 **Ribbon 下面那条状态行**
                       里，默认 16~20px 会把整行顶高）。 */
QGraphicsView#GgsModelView {{
    background: {panel};

       /* 画布**去掉 1px 边框与 6px 圆角** —— 那条 `border_soft` 就是用户看到的
       "灰线"（画布铺满整页，上边框正好落在标签下方），而圆角让四角露出
       `window` 底 ⇒ 与标签的 `panel` 不同色 = "不衔接"。
       地图画布（`GgsMapCanvas` 那条 `border: none`）与布局画布
       （`LayoutView.setFrameShape(NoFrame)`）本来就**无框**，这一处是**唯一
       的例外** ⇒ 统一到"无框"。桌面边框的活由四周主窗口 DOCK 承担。
       ⚠⚠ 注释里**不许出现裸花括号**（本模板是 `.format()` 渲染的 —— 这条
         注释第一版直接抄了那条 CSS 规则全文（带花括号），启动即 `KeyError`；
         连"教训注释"里都不能再抄一遍。要写就把花括号去掉，见项目记忆那条红线）。 */
    border: none;
    border-radius: 0;
}}
QProgressBar#GgsModelBar {{
    max-height: 12px;
}}
QLabel#GgsModelCap {{
    color: {text};
    padding-bottom: 2px;
}}
/* 「节点参数」栏重设计补的四条 ——
   `GgsModelCap` 仍给**算子节点的标题**用（粗体由控件侧 `QFont` 加，这里只管色），
   下面四条分别是**分节标题**（参数 / 数据 / 输出 / 连接）、**副句与只读值**
   （节点说明、连接行的来源名、未连接）、**已连接的值**、**空态主句**。
   ⚠ 之前参数栏那批 objectName（`GgsModelCmb` / `GgsModelSpin` / `GgsModelDim`
      …）**一条规则都没有**，全靠通用 `QComboBox` / `QLineEdit` 兜着 —— 这里只补
      "通用样式给不了"的那四种（弱化色 / 字重 / 字号），不做控件级重绘。 */
QLabel#GgsModelSect {{
    color: {text_dim};
    font-weight: 600;
    padding-top: 2px;
}}
QLabel#GgsModelSub {{
    color: {text_dim};
    font-size: 8.5pt;
}}
QLabel#GgsModelVal {{
    color: {text};
}}
QLabel#GgsModelEmpty {{
    color: {text};
    font-weight: 600;
}}
QComboBox::drop-down {{ border: none; width: 18px; background: transparent; }}
QComboBox::down-arrow {{ image: {arrow}; width: 10px; height: 10px; }}
QComboBox::indicator {{ background: transparent; border: none; }}
QComboBox QAbstractItemView {{
    background: {menu}; color: {text};
    border: 1px solid {border}; border-radius: 6px;
    selection-background-color: {accent_soft};
    selection-color: {text};
}}
/* 可编辑下拉（**字体搜索框**，）里的行编辑：去掉它自己的框与底色 ——
   否则组合框里会**再套一个小框**（通用 `QLineEdit` 那条规则会给它加边框）。
   ⚠ 选中的文字也要跟着主题走，不然浅色主题下选中态是系统蓝底黑字、很突兀。 */
QComboBox QLineEdit {{
    background: transparent;
    border: none;
    padding: 0 2px;
    color: {text};
    selection-background-color: {accent_soft};
    selection-color: {text};
}}
/* ---------------- 状态栏比例：「比例」标签 + **可输入**的下拉框（）----
   用户给的图（ArcGIS 的比例控件）随后点名"标签 + 比例下拉菜单（可修改文本）"：
   左边一个标签，右边一个可编辑组合框；点开是标准比例清单，**当前档与悬停档都是
   同一条灰底条、没有勾号**，框里的数字可以直接改。
   ⚠ 这几条必须写在本模板（有 `menu` 键）——`_DIALOG_PATCH` 的键集里没有
      `menu`，写过去会 KeyError（那一整套补丁是 `%` 格式化的）。 */
QLabel#GgsStatusScaleLabel {{
    color: {text_dim};
    background: transparent;
    padding: 0 2px 0 4px;
}}
/* 布局视图那个
   「缩放」下拉（`GgsStatusLayoutZoom`）与「比例」（`GgsStatusScale`）
   共用这一整套规则 —— 控件规格已经在 statusbar.py 里抄过去了，样式
   在这里并进来，两边才真的是同一种控件。 */
QComboBox#GgsStatusScale,
QComboBox#GgsStatusLayoutZoom {{
    /* 与它自己的弹层条目对齐（条目 4 + 弹层内边距 3 = 7） */
    padding: 0 6px;
    /* 20 → **18**。
       QSS 的高度是**内容区**高，加**上下各 1px 边框**才是控件总高 ⇒ 原来
       实际是 22px，而左右邻居（`#GgsStatusScaleLabel` 标签、锁按钮）都是
       `STATUS_CTRL_H = 20` ⇒ 它**比邻居高出 2px**，在 26px 高的状态栏里
       就显得往下坠、下沿贴底。改成 18 + 2 = **20** ⇒ 与邻居**同高、同线**。 */
    min-height: 18px;
    max-height: 18px;
}}
/* 可编辑 ⇒ 组合框里有一个 QLineEdit：**去掉它自己的框与底色**，
   否则框里会再套一个小框（通用 QLineEdit 那条规则会给它加边框） */
QComboBox#GgsStatusScale QLineEdit,
QComboBox#GgsStatusLayoutZoom QLineEdit {{
    background: transparent;
    border: none;
    padding: 0 2px;
    min-height: 18px;
    max-height: 18px;
}}
/* 弹层：行高 24、文字左内缩 12（图里就是这样）；当前档走 `:selected`、
   悬停走 `:hover`，两者同一条灰底条 —— 组合框弹层**天生没有勾号** */
QComboBox#GgsStatusScale QAbstractItemView,
QComboBox#GgsStatusLayoutZoom QAbstractItemView {{
    background: {menu}; color: {text};
    border: 1px solid {border}; border-radius: 6px;
    padding: 3px;
    selection-background-color: {panel_hi};
    selection-color: {text};
}}
QComboBox#GgsStatusScale QAbstractItemView::item,
QComboBox#GgsStatusLayoutZoom QAbstractItemView::item {{
    /* 左内缩 12 → **4** —— 弹层另有 3px 内边距，合起来 7，
       与框里文字（6 + 1px 边框）**同一条竖线** */
    min-height: 24px; padding: 0 4px; border-radius: 4px;
}}
QComboBox#GgsStatusScale QAbstractItemView::item:hover,
QComboBox#GgsStatusLayoutZoom QAbstractItemView::item:hover {{
    background: {panel_hi}; color: {text};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    background: {panel}; border: none; width: 16px;
}}
/* 按钮贴着输入框右缘，方角会盖住框体 6px 圆角（用户报
   「此问题还存在于 spinbox 控件」）——外角补同半径圆角。 */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QAbstractSpinBox::up-button {{
    border-top-right-radius: 5px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button,
QAbstractSpinBox::down-button {{
    border-bottom-right-radius: 5px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: {panel_hi};
}}

/* ---------------- 滑块（QSlider）----------------
   项目此前**没给 QSlider 定过任何样式** ⇒ 它退化成 Qt 原生绘制，
   深色主题下**轨道几乎看不见**。用户报的正是这个：
   「透明度控件（滑块）在透明度 0 时，0~100 部分看不清」—— 值=0 时
   "已填充段"长度也是 0，整条 0~100 全靠轨道自身的颜色，就更看不出来了。
   显式接管三件套：**可见的轨道** + 主色已填充段 + 主色圆手柄。
   ⚠ 只写 `:horizontal`（项目里的滑块都是横向；纵向的填充段叫 `::add-page`，
   照抄这里会画错方向）。 */
QSlider::groove:horizontal {{
    height: 5px; border-radius: 2px;
    /* 未填充槽用 `accent_soft`（两个主题下都是"可见的灰蓝"：#3c4758 / #c9d3df）——
       比 `border` 清楚得多，值=0 时整条 0~100 也一眼看得见；
       与已填充段的 `accent` 同色系，读起来像"走了一半的进度"。 */
    background: {accent_soft};
}}
QSlider::sub-page:horizontal {{
    background: {accent};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 13px; height: 13px; margin: -5px 0;
    border-radius: 7px;
    background: {accent};
    border: 1px solid {panel};      /* 与槽之间留一圈底色，重叠处不糊成一块 */
}}
QSlider::handle:horizontal:hover {{ background: {accent_hi}; }}
QSlider::groove:horizontal:disabled {{ background: {border_soft}; }}
QSlider::sub-page:horizontal:disabled,
QSlider::handle:horizontal:disabled {{ background: {text_disabled}; }}

/* ---------------- 树 / 表格 ----------------
   ——
     * 无焦点虚框（outline: 0）：浏览器那列点过之后不会留一圈虚线；
     * 行高 22 + 上下 padding 1 = 24，与浏览器面板实测行高一致；
     * 悬停 panel_hi、选中 accent_soft（沿用下面两条老规则）。
   背景**不动**：dock 里的列表由 GgsDockBody 直接子级规则保持透明，
   对话框里的沿用容器背景——给每张表都套一层卡片会把对话框切碎。
   图层树在下面用更高特异度的选择器把 padding 与内容高还原。 */
QTreeWidget, QTreeView, QListView, QTableView {{
    outline: 0;
}}
/* 给树/表视图本身
   加 4px 外边距，让内容与容器边缘留白（::item 的 padding 只管行内）。
   故意不含 QListView —— 列表类有各自的对象名规则（如 GgsShortcutTree）。 */
QTreeWidget, QTreeView, QTableWidget, QTableView {{
    padding: 4px;
}}
/* 标准列表控件 `GgsListWidget` / `GgsListView`（objectName `GgsList`）
   与标准树 `GgsTreeWidget` 对齐 —— 本体也带 4px 外边距（内容离控件边缘留白），
   不依赖嵌套容器的 padding。裸用的 `QListView`（状态栏 / 搜索弹窗 / 符号面板等）
   仍按各自 objectName 规则，这里不波及，保持"列表有各自对象名规则"的惯例。 */
QListWidget#GgsList, QListView#GgsList {{
    padding: 4px;
}}
QTreeWidget, QTreeView {{
    qproperty-indentation: 16;
    qproperty-animated: false;
}}
QTreeWidget::branch:closed:has-children,
QTreeView::branch:closed:has-children {{
    image: {branch_closed};
}}
QTreeWidget::branch:open:has-children,
QTreeView::branch:open:has-children {{
    image: {branch_open};
}}
/* branch 格永远树底色、
   不参与悬停/选中——高亮从 item 左缘起，左端自带 ::item 的 4px 圆角。
   三条不能动：
     1. 色必须等于该树自己的底色：对话框/工具箱/快捷键树 = `input`，dock 树 =
        `panel`（被 GgsDockBody 压成 transparent，见下条覆盖）；否则就是当年
        那个"子项前灰块"。
     2. 不要写圆角：branch 段下还压着 ::item 整行高亮，给圆角会漏色到最左缘。
     3. 不要写负 margin（Fusion 时代补缝手段，会画进相邻行）。
   原生 windows11 在 branch 格画的"系统强调色小竖条"（= 橙条）由
   `app.py::_install_tree_branch_style` 的 app 级 QProxyStyle 从根上挡掉。 */
QTreeWidget::branch:hover, QTreeView::branch:hover {{
    background: {input};
}}
QTreeWidget::branch:selected, QTreeView::branch:selected {{
    background: {input};
}}
/* dock 里的树被 `QWidget#GgsDockBody > …` 压成 transparent，真底 = 卡片 `panel`，
   故 branch 格跟 `panel`（深色下 panel/#242932 与 input/#17191f 差一档，少它即灰块）。 */
QWidget#GgsDockBody > QTreeWidget::branch:hover,
QWidget#GgsDockBody > QTreeView::branch:hover,
QWidget#GgsDockBody > QTreeWidget::branch:selected,
QWidget#GgsDockBody > QTreeView::branch:selected {{
    background: {panel};
}}
QTreeWidget::item, QTreeView::item, QListView::item, QTableView::item {{
    height: 24px;
    padding: 2px 4px;
    border: none;
    border-radius: 4px;
}}
/* 用 `::item` 的
   margin 在行间留透明缝隙（不进 hover/选中高亮）。量取 1px，相邻两行各 1px ⇒
   视觉缝隙约 2px（"一点点"）。走纯 QSS 子控件样式、**不用 qproperty-spacing**——
   Qt6 的 QTreeView 没有 `spacing` 属性，写它会报
   "does not have a property named 'spacing'"。**表格不隔行距**（下面无 QTableView）。 */
QTreeWidget::item, QTreeView::item {{
    /* 树行距锁定 1px（相邻两行各 1px ⇒
       视觉缝隙约 2px）。与列表分开，便于独立微调。 */
    margin: 1px 0;
}}
QListView::item {{
    margin: 1px 0;
}}
/* 通用
   `QListView::item` 行高 24px / 内边距 2px 4px 把行高压得太死、上下
   留白不足，内嵌「显示/冻结」复选框被裁掉一截。这里按 objectName 单独放宽
   `GgsColumnList` 的行高与内边距（特异度高于通用规则，不影响其它列表）。 */
QListWidget#GgsColumnList::item {{
    height: 28px;
    min-height: 28px;
    padding: 4px 6px;
}}
QTreeWidget::item:hover, QTreeView::item:hover, QListView::item:hover,
QTableView::item:hover {{
    background: {panel_hi};
    border-radius: 4px;
}}
QTreeWidget::item:selected, QTreeView::item:selected,
QListView::item:selected, QTableView::item:selected {{
    background: {accent_soft};
    color: {text};
    border-radius: 4px;
}}
/* 只针对
   项目统一表格 `GgsTable`（objectName=GgsTable）把项的圆角清零；树 / 列表
   项保持 4px 不变（用户只点名 Ggs 表格）。`QTableView::item` 通用规则仍给
   表格项 4px，这里用 objectName 提高特异度压掉它。 */
QTableWidget#GgsTable::item, QTableWidget#GgsTable::item:hover,
QTableWidget#GgsTable::item:selected, QTableWidget#GgsTable::item:focus {{
    border-radius: 0;
}}
/*
   属性表主视图 `GgsAttributeTableView` 与冻结列子视图
   `GgsAttributeTableViewFrozen` 都是模型驱动的 `QTableView` 子类（不是
   item 型 `QTableWidget`，不便直接换成 `GgsTableWidget`），objectName 也
   不是 `GgsTable`，所以上面的 `QTableWidget#GgsTable` 覆盖规则够不到它们，
   仍被通用 `QTableView::item:hover/:selected` 的 4px 圆角命中。这里按同样
   意图用 objectName 把圆角清零，使属性表与项目统一表格 GgsTable 视觉一致。 */
QTableView#GgsAttributeTableView::item,
QTableView#GgsAttributeTableViewFrozen::item,
QTableView#GgsAttributeTableView::item:hover,
QTableView#GgsAttributeTableViewFrozen::item:hover,
QTableView#GgsAttributeTableView::item:selected,
QTableView#GgsAttributeTableViewFrozen::item:selected,
QTableView#GgsAttributeTableView::item:focus,
QTableView#GgsAttributeTableViewFrozen::item:focus {{
    border-radius: 0;
}}
GgsLayerTreeView::item {{
    height: 24px;
    padding: 2px 4px;
}}
QTableView {{ gridline-color: {border_soft}; }}
QHeaderView::section {{
    background: {panel};
    color: {text_dim};
    border: none;
    border-right: 1px solid {border_soft};
    border-bottom: 1px solid {border_soft};
    padding: 4px 6px;
}}
/* 表头首/末列补上与容器一致的上圆角：否则表头方块盖住
   树/表容器的圆角（图层属性右侧信息树顶部发方的根因） */
QHeaderView::section:first {{ border-top-left-radius: 6px; }}
QHeaderView::section:last {{ border-top-right-radius: 6px; }}

/* ---------------- 滚动条（细窄 + 实体轨道） ----------------
   轨道不再透明：透明轨道 + 圆角把手会"悬浮"在内容上，看起来
   像盖住了最右列的数据。实体轨道 + 左/上分隔线让滚动条成为
   表格的一部分。
   ⚠ 实锤（offscreen 变体矩阵 + 特写截图）：轨道上只要有
   border（哪怕 1px 的 border-left），::handle 的 border-radius 就
   整体失效（Qt 对带边框的滚动条走另一条渲染路径）。分隔线改用
   渐变背景画（qlineargradient 首个 1px stop），圆角把手保得住。 */
QScrollBar:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {border_soft}, stop:0.0835 {panel});
    width: 12px; margin: 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {border}; border-radius: 4px; min-height: 30px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
QScrollBar:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {border_soft}, stop:0.0835 {panel});
    height: 12px; margin: 0 4px;
}}
QScrollBar::handle:horizontal {{
    background: {border}; border-radius: 4px; min-width: 30px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{ background: {text_dim}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------------- 按钮 / 复选框 / 分组框 ---------------- */
QPushButton {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 6px;
    padding: 5px 16px;
}}
QPushButton:hover {{ background: {panel_hi}; border-color: {text_dim}; }}
QPushButton:pressed {{ background: {panel_dn}; }}
QPushButton:default {{ border-color: {focus}; }}
QPushButton:disabled {{ color: {text_disabled}; border-color: {border_soft}; }}

QCheckBox {{ color: {text}; spacing: 6px; }}

QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid {border};
    border-radius: 4px; background: {input};
}}
QCheckBox::indicator:hover {{ border-color: {focus}; }}
QCheckBox::indicator:checked {{
    /* 底色 accent_soft + 主题灰对钩——本项目主题色以灰色
       为主，不用 accent 蓝实底 + 白钩 */
    background: {accent_soft}; border-color: {border};
    image: {menu_check};
}}
QCheckBox::indicator:checked:disabled {{
    background: {border_soft}; border-color: {border_soft};
}}
/* 视图内勾选框（通用，）：图层树 / 布局项树 / 地图数据树等所有可勾选树
   的对钩都由 QSS 原生 indicator 画。QStyleSheetStyle 画该原语时按 opt.widget
   （即视图本身）匹配规则，故对所有 QTreeView 子类生效。
   **不要给
   某一棵树单开 ::indicator 规则**去改尺寸 —— 全项目可勾选树统一。
   （曾给图层树开过 16px 的，被否决。）
   ⚠⚠ Qt QSS 盒模型坑：这里的 `width/height` 设的是**内容区**，四周还要各加
   1px 边框 ⇒ 写 14px 时**外框实际 16px**（项目内实测：20 设备像素 @DPR 1.25，
   见 icons.py `filled_icon` 文档串的记录）——用户要的"14px"一直指的是
   **外框**，而图标图形视觉只有 ~13.5px ⇒ 框永远大一圈。
   ⇒ 内容区改 **12px**：外框 = 12 + 2×1 = **真 14px**，与图层树重画后的
   图标图形（icons.py `_BODY` 占满 ~20.5/24 ⇒ 16px 渲染视觉 13.5~14px）
   视觉等大。`:checked` 贴图本就是 12×12 画布，正好满贴。 */
QTreeView::indicator {{
    width: 12px; height: 12px; border: 1px solid {border};
    border-radius: 4px; background: {input};
}}
QTreeView::indicator:hover {{ border-color: {focus}; }}
/* 选中态（）：白底 + 主题色对钩边框；对钩贴图描边 1.3
   （12×12 画布，见 resources/icons/menu_check_*.svg）。 */
QTreeView::indicator:checked {{
    background: {input}; border-color: {check_border};
    image: {tree_check};
}}
/* 半选（分组内部分图层可见）：实心对钩易与全选混淆，用渐变硬 stop 画一条
   居中横杠（无插值过渡即实色条）。⚠ 内容区同步 12px（与上面同尺寸）。 */
QTreeView::indicator:indeterminate {{
    width: 12px; height: 12px; border: 1px solid {border};
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {input}, stop:0.38 {input},
        stop:0.38 {text_dim}, stop:0.62 {text_dim},
        stop:0.62 {input}, stop:1 {input});
}}
/*
   这里曾按"对钩=图标格子"给图层树单开过 16px 的 indicator 特规 —— 但图标
   图形本体在 24 画布里只占 17/24，16px 渲染下视觉仅 ~11px，16px 对钩反而
   **比图标大出一圈**（正是用户点名的"明显大很多"）。整条撤掉，回归
   **全项目统一**；对齐改由**放大加重图层图标图形**承担（icons.py
   `_BODY` 的图层四枚已重画为占满 ~20.5/24 ⇒ 16px 渲染下视觉 13.5~14px，
   与外框 14px 的对钩视觉等大）—— 图层树不再有任何特殊样式。 */
/* 菜单项的勾选标记（）：14px 指示框 + 左右对称留白，
   checked 态贴随主题取色的对钩图（白钩在白底菜单上看不清） */
QMenu::indicator {{ width: 14px; height: 14px;
    margin-left: 6px; margin-right: 4px; }}
/* QSS 接管 indicator 后原生对钩失效，checked 态显式贴对钩图
   （显示要素数量 / 显示标注等可勾选菜单项的勾选标记） */
QMenu::indicator:checked {{ image: {menu_check}; }}

QGroupBox {{
    color: {text_dim}; border: 1px solid {border_soft};
    border-radius: 6px; margin-top: 12px; padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
}}
/*
   可勾选分组框（`GgsSymbology` 里的「背景值」）的标题复选框 —— 尺寸与
   `QCheckBox` / `QTreeView::indicator` 同一套（14px + 圆角 4 + 同一份
   对钩贴图），免得标题上冒出一个 Fusion 原味的方框。
   ⚠边框色从 `{border}` 改成 **`{text_dim}`**（深一档）——
   标题区里这个复选框的**四周全是浅色**（上方是面板底、内部是白色），
   而 1px 的 `{border}`（浅灰）在 DPR 1.5 下被抗锯齿一摊就**几乎看不见**
   （用户看到的是"上边缺一条"的 `⊔`）。实测黑色边框四边完整 ⇒ 不是没画、
   也不是被裁，而是**对比度不够**。 */
QGroupBox::indicator {{
    width: 14px; height: 14px; border: 1px solid {text_dim};
    border-radius: 4px; background: {input};
}}
QGroupBox::indicator:hover {{ border-color: {focus}; }}
QGroupBox::indicator:checked {{
    background: {accent_soft}; border-color: {border};
    image: {menu_check};
}}
QGroupBox::indicator:checked:disabled {{
    background: {border_soft}; border-color: {border_soft};
}}
/* ：
   这里原来还有 4 条 `#GgsSymCheckGroup::indicator` 规则（尺寸 / 外观 / `:hover`
   / `:checked`）—— 它们与上面的**通用** `QGroupBox::indicator` **一个字都不差**，
   纯属重复；而且其中一条还写了 `subcontrol-origin/position` + `left: 8px;
   top: 2px`，那正是"位置异常"的根源：
   * `subcontrol-position` **不是 `relative`** 时，`left` / `top` 对
     `::indicator` **根本不生效**（Qt 的规矩）⇒ 想摆的位置没摆成；
   * 更糟的是**一写 `subcontrol-*` 就切到"显式定位"那条路**，把 Qt 自带的
     排布（indicator 紧跟标题左侧、与文字**垂直居中**）打断了 ⇒ 复选框浮在
     标题上方偏高一截、与文字不居中 —— 用户看到的就是这个。
   ⇒ **整块删掉**：位置与外观全部交回通用规则（`QGroupBox::indicator`），
   这里只留"标题区加高"与"标题右移给复选框让位"两条。
   ⚠ 以后别再给 `::indicator` 加 `left` / `top` / `subcontrol-position`。 */

QLabel {{ color: {text}; background: transparent; }}

/* ---------------- 状态栏 / 进度条 ---------------- */
QStatusBar {{
    /* round41u：状态栏直接用窗口背景色；上边框取消 */
    background: {window}; color: {text_dim};
}}
QStatusBar QLabel {{ padding: 0 6px; color: {text_dim}; }}
QStatusBar QToolButton {{
    padding: 1px 6px; border-radius: 6px; background: transparent;
    color: {text_dim}; border: none;
}}
QStatusBar QToolButton:hover {{ background: {panel_hi}; color: {text}; }}
QStatusBar QToolButton:checked {{ background: {accent_soft}; color: {text}; }}
/* 「＋」= **带菜单的新建按钮**（原来是"点一下直接建布局"，
   现在要能建地图 / 布局 / 模型构建器…）。外观与标签同族，但更轻，
   并且与最后一个标签**拉开 4px**（），免得看着像"第 N 个页签"。 */
/*
   视图容器铺**选中标签那一档** `panel`。
   ⚠ 历史（，用户 两次纠正"**不是改颜色，是不要设置颜色！**"）：
     那次把 `#GgsViewTabs` 整条删掉、改成"容器什么都不画、继承父色"。
     ⚠ 但**继承父色这条路走不通**：父容器 `GgsCanvasHost` 是 `panel`
       （`#242932`），而**标题栏与功能区都是 `window`**（`#1e2229`）⇒
       标签行那条比上面**亮一档**，横向一条色带（用户实图，割裂感）。
     ⇒ 见下面 那条：标签行容器**自己**取 `window`，与标题栏同色。
       ⚠ 中途两次走偏并已撤回：① 只开 `WA_StyledBackground` 而不写规则
         （开了没规则 = 还是父色）；② 规则值写 `transparent`（QSS 的
         `transparent` 仍算"给容器设置背景"，且开了 StyledBackground 的
         控件会**真的去画**）。正解 = 写**具体色值** + 开那个开关。


     ⇒ 标签行容器 `#GgsViewTabs` 取 **`window`**（与标题栏 / 功能区同色）。
     这样三段连成一片：`标题栏 = 功能区 = 视图选项卡行`，
     往下的画布区才是 `panel`（要的"标签↔内容衔接"改由
     **选中标签那个 `panel` 底**承担，见下面 `::tab:selected`）。
     ⚠ 容器这一层要**开 `WA_StyledBackground`**（在 `statusbar.py` 里）——
       自定义 `QWidget` 不开这个开关，QSS 的 `background` 整个不画。
     ⚠⚠ 本段走 `str.format()` ⇒ **注释里也不能出现花括号**（会被当占位符
       替换掉、把注释搅乱；键名写错更是 import 期 KeyError）。 */
QWidget#GgsCanvasHost {{ background: {panel}; }}
QStackedWidget#GgsViewHost {{ background: {panel}; }}
QWidget#GgsViewTabs {{ background: {window}; }}
/* 画布上方的**视图选项卡**（真正的 `QTabBar`，不是一排按钮）。
   用户："**做成类似 QTabWidget 的 Ggs 控件，顶部切换标签，内容是画布、布局等，
   支持关闭、重命名、新增！不是让你放按钮！**"
   ⚠ 与 `#GgsRibbonTabs`（功能区页签）刻意区分：功能区那条是"独立 chip"，
     这一条要像 QTabWidget —— **选中 tab 上圆角、底部与内容区连成一体**。
   ⚠ 高度由**代码**钉死（`STATUS_CTRL_H`，各控件 `setFixedHeight`）——
     这里**不要**写 `height`，会和代码打架（老口径：边框占位、尺寸不跳）。
   ⚠⚠
     整条标签行 = `window`（与标题栏、功能区连成一片，见上面 `#GgsViewTabs`）。
     页签自身**一律透明**（不画底），只有**选中**那一枚铺 `panel` ——
     它是"往下的画布区"那一档，视觉上把标签行和画布**接起来**
     （定的"标签与内容颜色对应衔接"就是由它承担的）。 */QTabBar#GgsViewTabBar {{ background: transparent; }}
QTabBar#GgsViewTabBar::tab {{
    background: transparent;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 5px 4px 5px 10px;
    margin: 0 1px;
    color: {text_dim};
    font-size: 11.5px;
    min-width: 0;
}}
QTabBar#GgsViewTabBar::tab:hover {{
    background: {panel_hi};
    border-color: {border_soft};
    color: {text};
}}
QTabBar#GgsViewTabBar::tab:selected {{
    background: {panel};
    border-color: {border_soft};
    color: {text};
    /* 不加 font-weight：选中加粗会撑宽 tab，切换时整行回流 */
}}
QProgressBar {{
    background: {input}; border: 1px solid {border};
    color: {text}; border-radius: 4px; text-align: center;
}}
QProgressBar::chunk {{ background: {accent_soft}; border-radius: 4px; }}

/* ---------------- 对话框 / 分割条 / 通用工具按钮 ---------------- */
QDialog {{ background: {window}; }}
/* **全局** —— 所有 `QSplitter` 的 handle 一律
   **什么都不画**（透明、无边框；hover / pressed 也不画）。
   只留 **4px 的空白可拖动区**（鼠标形状仍是左右箭头）⇒
   "看不见任何手柄"与"还能拖"同时成立。
   ⚠ 宽度**别设 0**：0 宽 = 没有任何命中区域 = 彻底拖不动（用户要的是
     "不要有（手柄）"，不是"不要能拖"）。
   原来它是 `border_soft` 的一条实线、hover 还变强调色。 */
QSplitter::handle {{ background: transparent; border: none; }}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical {{ height: 4px; }}
QSplitter::handle:hover, QSplitter::handle:pressed {{
  background: transparent; border: none;
}}
QAbstractScrollArea::corner {{ background: {panel}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
/* 色带下拉里那个列表**要边框** —— 上面那条全局规则把 `QScrollArea`
   的边框去掉了，而 `setFrameShape(Box)` 会被 QSS 盖住（QSS 优先于 frame shape
   的绘制）⇒ 不写这条，列表就是"没框的一堆色带"。用户给的 QGIS 截图里，
   那一块是有明确边界的（"这是个选择区"）。 */
QScrollArea#GgsRampList {{
    border: 1px solid {border};
    background: {input};
}}
QScrollArea#GgsRampList > QWidget > QWidget {{ background: transparent; }}
/* QGIS 原生对话框内部的分隔条（.ui 标准命名 QFrame#line，HLine 3px）
   按约定默认 0px 透明不显示 */
QFrame#line {{
    border: none; background: transparent; max-height: 0px;
}}

/* ---- 「关于」/ 许可声明对话框（）----
   品牌横幅 + 两张信息卡片 + 许可条。用户反馈"关于对话框太简陋了"：
   此前只有一堆裸 HTML 表格，既没有卡片层次，也与项目其它对话框
   （GgsDialog 卡片风格）脱节。颜色一律取主题键，深浅两套自适应。 */
QFrame#GgsAboutHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {accent}, stop:1 {accent_hi});
    border: none;
}}
QLabel#GgsAboutName {{
    color: {accent_text};
    font-size: 20pt;
    font-weight: 600;
}}
QLabel#GgsAboutBadge {{
    background: rgba(255, 255, 255, 51);
    color: {accent_text};
    border: 1px solid rgba(255, 255, 255, 71);
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 9.5pt;
}}
QLabel#GgsAboutTagline {{
    color: rgba(255, 255, 255, 230);
    font-size: 10.5pt;
}}
QFrame#GgsAboutHeroSep {{
    background: rgba(255, 255, 255, 71);
    border: none;
    max-width: 1px;
    min-height: 14px;
}}
QLabel#GgsAboutIcon {{ background: transparent; }}
QFrame#GgsAboutCard {{
    background: {group_bg};
    border: 1px solid {border_soft};
    border-radius: 6px;
}}
QLabel#GgsAboutCardTitle {{
    color: {text};
    font-weight: 600;
}}
QLabel#GgsAboutKey {{ color: {text_dim}; }}
QLabel#GgsAboutVal {{ color: {text}; }}
QLabel#GgsAboutNote {{ color: {text_dim}; font-size: 8.5pt; }}

   /* 原来这里给它画了一张**卡片**（`border` + `border-radius` + `padding: 2px`）——
   **全项目只有这一棵树**是这么画的：浏览器树 / 图层树走的是
   `GgsDockBody` 下那条规则（无框、背景透明、直接融进面板），悬停 / 选中的高亮
   因此**铺满整行**；
   而这里因为多了 1px 描边 + 2px 内边距，高亮块四周都缩进去一截，看着就是
   "另一种列表"。实测（`build/_r492j77j_tree.py` → `_r492j77j_out/对比.txt`）：
   两棵树的行高（28）、缩进（16）、图标（16）本来一模一样，唯一的差别就在这层框。
   ⇒ 现在对齐标准列表：去掉外框与内边距，悬停 / 选中完全交给通用 `::item:*` 规则。 */
/* 坐标系那棵树的**专属规则已删** —— 它现在与其它六棵树共用
   `ggis/ui/treeview.py` 的同一套底层（objectName 也统一成 `GgsTree`），
   样式走上面的通用 `::item` 规则。**别再给某一棵树单开规则**：
   。 */
/*
   左侧那棵列表按**浏览器面板的目录树**来读 —— 16px 图标 + 16px 缩进
   （代码里设），行高与左右留白沿用上面那条通用 `QTreeWidget::item`
   （浏览器树也没有自己的规则，两处因此一模一样）。 */
/* 「新建坐标系」按钮（）：**纯图标 + 下拉菜单**，不要文字。
   给它按钮本体的边框与悬停，再把被全局规则按掉的展开箭头**只在这一处**
   放回来 —— 不然用户看不出它是个菜单。 */
/* **导入样式**按钮（`GgsStyleImportButton`）—— 符号系统与标注
   设置**共用同一颗**（`#GgsImportStyleBtn`）：图标 + **下拉箭头**。
   ⚠ 箭头必须**显式给图**：不给就只剩一颗图标，看不出它其实是菜单。 */

   /* **照抄功能区小按钮（GgsSmallButtonStyle3）**，不再自造一套。 */

   /* 3-3 的真实规格（`ribbon.RibbonGroup.add_action` 的 `else` 分支）：
       ToolButtonTextBesideIcon + iconSize=SMALL_ICON(16)
       QSS `padding: 2px 1px` + 最小宽 = 文本宽 + 16 + 10 + **9**(给箭头留位)
       箭头由 `SmallDropButton.paintEvent` 画在 `w - 7`（距右边缘 7px）
   ⇒ 箭头**紧贴文本右侧**。 */

   /* ⚠⚠⚠ **坑**：本文件是 `str.format` 模板。
      **规则块**要写两个花括号，而**颜色占位符只能写一个花括号**。
      我先把占位符写成了两个花括号 ⇒ 渲染后留下字面的花括号 ⇒
      。
      更狠的是：**注释里也不许出现单个花括号**（模板一样会去解析它）——
      我补这段说明时又在注释里写了单个花括号，当场 IndexError。
      ⇒ 注释里要提花括号就用文字说（"两个花括号"），别写符号。
      ⇒ **改完必须自检**：渲染后的 QSS 里"一个花括号 + 小写名字 + 一个
        花括号"这种残留必须为 **0 次**（light / dark 都查）。
   ⚠ **水平内边距必须是 1px**：上一版我写成 `padding: 5px 14px 5px 5px`
     （想给箭头留位置）⇒ 文本与自绘箭头之间空出十几像素，用户一眼看出
     "不是同一个样式"。留位要靠**最小宽公式里的 +9**，不是靠 padding。
   ⚠ 垂直仍取 **5px** —— 与通用 `QPushButton`（`padding: 5px 16px`）同公式
     ⇒ 与同一行的「应用」按钮**自然等高**；**不要** `min-height` /
     `setFixedHeight` / 功能区 `ROW_H`。 */
QToolButton#GgsImportStyleBtn {{
    background: transparent; border: 1px solid transparent;
    border-radius: 6px; padding: 5px 1px; color: {text};
}}
QToolButton#GgsImportStyleBtn:hover {{ background: {panel_hi}; }}
QToolButton#GgsImportStyleBtn:checked,
QToolButton#GgsImportStyleBtn:pressed {{
    background: {panel_dn}; border: 1px solid {border};
}}
/* **Ggs 中等图标按钮**（GgsMediumButtonStyle1/2/3，控件画廊）
   —— 观感从「导入样式」按钮移植：图标 + 文本 + 圆角底；样式2 可勾选，
   **选中（checked）保留 1px 边框线**（用户点名）。规格与
   QToolButton#GgsImportStyleBtn 逐项一致（padding 5px 1px、圆角 6px）。 */
QToolButton#GgsMediumBtn {{
    background: {panel}; border: 1px solid {border};
    border-radius: 6px; padding: 5px 10px; color: {text};
    spacing: 4px;
}}
QToolButton#GgsMediumBtn:hover {{ background: {panel_hi}; border-color: {text_dim}; }}
QToolButton#GgsMediumBtn:checked,
QToolButton#GgsMediumBtn:pressed {{
    background: {panel_dn}; border: 1px solid {border};
}}
QLabel#GgsCrsSection {{
    color: {text_dim};
}}
/* 原来这里还有一条给「坐标系信息」那一整块 HTML 用的颜色规则
   （对象名 `GgsCrs` + `Info`）。信息卡片现在改成**键值行**，用的是
   `#GgsAboutKey` / `#GgsAboutVal`（与「关于」同一套）⇒ 那条规则已无使用者，
   删掉别留孤儿。 */
/* 关于对话框的主操作按钮（唯一的主按钮，给主题强调色） */
QPushButton#GgsAboutOkButton {{
    background: {app_btn};
    color: {accent_text};
    border: 1px solid {app_btn};
    border-radius: 6px;
    padding: 5px 16px;
    font-weight: 600;
}}
QPushButton#GgsAboutOkButton:hover {{
    background: {app_btn_hi};
    border-color: {app_btn_hi};
}}
QPushButton#GgsAboutOkButton:pressed {{ background: {app_btn}; }}
QTextBrowser#GgsNoticesView {{
    background: {input};
    border: 1px solid {border_soft};
    border-radius: 6px;
    color: {text};
    padding: 6px 8px;
}}

QToolButton {{
    background: transparent; color: {text}; border: 1px solid transparent;
    padding: 3px; border-radius: 6px;
}}
QToolButton:hover {{ background: {panel_hi}; }}
QToolButton:pressed, QToolButton:checked {{
    /* 按压/勾选态去 accent 深蓝描边——中性按压色即可，
       蓝色 1px 边框在状态栏小按钮上还会因弹层吃掉 release 事件
       而"粘滞"在按钮上（用户报坐标/比例按钮发蓝的根因）
       ：
       **边框宽度恒为 1px**——基础规则给 transparent 描边、按压只换
       border-color。原来"基础 border:none → 按压 border:1px"会让内容
       盒在按下瞬间收窄 2px（图标/文字明显缩一下再弹回 = "缩小动画"）。 */
    background: {panel_dn};
    border: 1px solid {border_soft};
    color: {text};
}}
QToolButton:disabled,
QToolButton:checked:disabled,
QToolButton:pressed:disabled {{
    /* 禁用态不允许带「点击态」外观——用户反馈"按钮处于不可
       用状态时不能处于点击状态"。上面 :checked/:pressed 只声明了
       background/border，:disabled 若只改 color 就盖不住它们（同特异
       度靠后声明胜），灰按钮会残留一块 panel_dn 按下底色 + 描边。这
       里显式清空；border 用 none 与基础规则一致，几何不跳变。 */
    background: transparent;
    border: none;
    color: {text_disabled};
}}
QToolButton::menu-indicator {{ image: none; }}

/* 颜色按钮（GgsColorButton）：项目标准下拉观感——细描边圆角、
   零内边距。通用 QToolButton 的 3px padding 会把内部色块/箭头
   挤得互相重叠（选项对话框色块 ▼ 压色块的根因） */
GgsColorButton {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 0;
}}
GgsColorButton:hover {{ border-color: {focus}; }}
GgsColorButton::menu-indicator {{ image: none; width: 0; }}

/* 选项对话框色块下拉（_ColorField）：QComboBox 同构——外框细描边
   圆角，左色块右箭头，箭头区与色块以 1px 竖线分隔，互不重叠 */
/* 样式格（`GgsSymbolCellButton`）**本身就是那个符号** ——
   它的 `paintEvent` 把符号样片按整个控件矩形 1:1 铺满，**不画任何按钮面板**。
   ⇒ 这里**不能**给 `border` / `background` / 圆角：
     * 写了 `background`：样片是画在最上面的（不透明）⇒ **根本看不见**；
     * 写了 `border`：那一圈就是"**按钮的外壳**" ⇒ 又变回"套进按钮里"。
   ⚠ 悬停 / 按下的反馈由 `paintEvent` 用**整片不透明度**（0.85 / 0.70）给 ——
     那是唯一既看得出"能点"、又不引入边框的做法（且与主题深浅无关）。 */
QToolButton#GgsSymbolCellButton {{
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}}
QWidget#GgsColorField {{
    background: {input};
    border: 1px solid {border};
    border-radius: 6px;

       /* 「拉伸」是 `QComboBox`、「百分位 / 区间」是 `QDoubleSpinBox` —— 它们都吃
       上面那条 `min-height: 24px`（**同一档高度**）；只有「值」那一行里的
       本控件（色块 + 箭头）是**按内容自己长**的，比旁边那几个高一截 ⇒
       同一组里三行三种高度。
       ⇒ 在这里把它**钉到和下拉框同一档**（24px + 1px 边框，与
       `QLineEdit / QComboBox / QDoubleSpinBox` 完全一致）。
       ⚠ 它内部是"自绘色块 + 箭头按钮"的横向布局，限高不会裁内容
       （色块按容器高度自适应）。 */
    min-height: 24px;
    max-height: 24px;
}}
QWidget#GgsColorField:hover {{ border-color: {focus}; }}
/*
   视觉上也要看得出禁用 —— 外框与箭头退成弱边框、悬停不再提亮；
   色块自己的淡化在 `GgsColorSwatch.paintEvent` 里按 `isEnabled()` 画
   （它是自绘控件，QSS 管不到它的内容）。
   ⚠ 「不可点」的口径在 `GgsColorField.eventFilter` / `choose()` / `pick()`：
   色块不是按钮，Qt 不会替它拦事件。 */
QWidget#GgsColorField:disabled,
QWidget#GgsColorField:disabled:hover {{
    background: {panel};
    border-color: {border_soft};
}}
QToolButton#GgsColorArrow:disabled,
QToolButton#GgsColorArrow:disabled:hover {{
    background: transparent;
    /* 箭头**一条边都不画**。这里原来写的是
       `border-left: 1px solid {border_soft}` —— 那就是"箭头左边那道边框"的来源；
       用户先要"换成一条竖线"，随后又定"**分隔线也去掉**" ⇒ 现在两边都不画，
       色块与箭头之间**什么线都没有**。 */
    border: none;
}}
/* ⚠ 类型必须写 `QWidget`：`GgsColorSwatch` 继承的是 **QWidget**，原来写成
   `QLabel#GgsColorSwatch` ⇒ 选择器永远不匹配（静默失效）。它自己是自绘的
   （`WA_StyledBackground=False`），这条只是兜底：**色块/颜色预览一律无边框**
   。 */
QWidget#GgsColorSwatch {{
    background: transparent; border: none; border-radius: 3px;
}}
/* **色带选择控件**（分类 / 分级 / 规则都用它）。
   与 `#GgsColorField` 同一个观感：细描边 + 圆角 + 面板底，hover 边框转主题色。
   它的"内容"是**图标**（自绘色带，见 `colors.ramp_strip_pixmap`），
   所以这里只管外框。 */
/* 三条抱怨其实**一一对应**原来的三个值 ——
   * `border_soft`（最弱的 #2a2e36）⇒ "边框不明显"；
   * `border-radius: 3px` + 底色 `panel` ⇒ 与**同族的色块控件**
     （`QWidget#GgsColorField`：`input` 底 + 4px 圆角）不齐 ⇒ "不像主题样式"；
   * `:hover` 只改 `border-color` 且用的是 `accent`（#3d7fd1 蓝）⇒ "悬停变蓝"。
   ⚠ 本模板走 `str.format()` ⇒ **注释里也不能出现花括号**（`py_compile` 查不出，
     只有 import 才炸；这一段刚连着踩了两次）。
   ⇒ 现在**逐项对齐 `GgsColorField`**（同族控件就该同观感）。 */
QToolButton#GgsRampField {{
    background: {input};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 1px 2px;
}}
QToolButton#GgsRampField:hover {{
    border-color: {focus};
}}
QToolButton#GgsRampField:disabled {{
    background: {panel};
    border-color: {border_soft};
}}
QToolButton#GgsColorArrow {{
    background: transparent;
    /* —— 最终口径：
       * 箭头**一条边都不画** —— 原来这里是 `border-left: 1px solid {border_soft}`，
         既被当成"箭头自带的那圈外框"，颜色又是最弱的 `border_soft`、高度还只有
         20px（比行高矮一截）；
       * 色块与箭头之间**不加分隔线**（中途加过一个 1px 的 `#GgsColorSep`，
         用户明确不要 —— 那条规则已删，别再加回来）。 */
    border: none;
    /* 外框 `#GgsColorField`
       是 4px 圆角、箭头在 1px 内边距里 ⇒ 它的**右侧两角取 3px**。原来写
       `border-radius: 0`，hover 底色（panel_hi）会铺满一个直角方块，
       右下角直接顶破外框圆角 —— 看着就是"箭头那块是方的"。 */
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 0;
}}
QToolButton#GgsColorArrow:hover {{ background: {panel_hi}; }}

QComboBox QAbstractItemView::item {{ min-height: 22px; padding: 2px 6px; }}

/* 单选框（）：原来这条规则是空的，indicator 交给原生样式画；
   应用了全局 QSS 之后 Windows 原生样式画出来**两个状态都是实心圆**
   （只差颜色，且取的是系统强调色），用户根本分不出选了哪一个——在
   「只修改坐标系定义 / 重投影数据」这种选错就动数据的场合是硬伤。
   这里显式接管，与复选框一族同款：白底 + 边框，选中态贴实心点 SVG
   （⚠ 不能用 qradialgradient 画点，Qt 把 cx/cy 当绝对像素）。 */
QRadioButton {{ color: {text}; spacing: 6px; }}
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {border}; border-radius: 8px;
    background: {input};
}}
QRadioButton::indicator:hover {{ border-color: {focus}; }}
QRadioButton::indicator:checked {{
    border-color: {check_border};
    image: {radio_dot};
}}
QRadioButton::indicator:checked:disabled {{
    background: {border_soft}; border-color: {border_soft};
}}
QRadioButton::indicator:disabled {{ border-color: {border_soft}; }}
QRadioButton:disabled {{ color: {text_disabled}; }}

QLabel:disabled, QCheckBox:disabled {{ color: {text_disabled}; }}
"""


def _render(p):
    if "arrow" not in p:
        p = dict(p, arrow=_arrow_url("combo_arrow_dark.svg"))
    try:
        return _TEMPLATE.format(**p)
    except KeyError as e:
        raise KeyError(
            "themes: 模板里用了 {%s}，但主题字典里没有这个键 —— "
            "键名以 `_DARK` / `_LIGHT` 为准（例如是 `text_disabled`，"
            "不是 `text_dis`）" % (e.args[0] if e.args else "?")) from None


_ARROWS_DARK = """
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QAbstractSpinBox::up-arrow,
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover,
QAbstractSpinBox::up-arrow:hover {
  image: %(up)s; width: 10px; height: 10px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow,
QAbstractSpinBox::down-arrow,
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover,
QAbstractSpinBox::down-arrow:hover {
  image: %(down)s; width: 10px; height: 10px;
}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:off,
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {
  image: %(up_d)s; width: 10px; height: 10px;
}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:off,
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {
  image: %(down_d)s; width: 10px; height: 10px;
}
QDateEdit::down-arrow, QDateTimeEdit::down-arrow,
QDateEdit::down-arrow:on, QDateEdit::down-arrow:hover,
QDateEdit::down-arrow:focus,
QDateTimeEdit::down-arrow:on, QDateTimeEdit::down-arrow:hover,
QDateTimeEdit::down-arrow:focus {
  image: %(down)s; width: 10px; height: 10px;
}
""" % {
    "up": _arrow_url("arrow_up_dark_normal.svg"),
    "down": _arrow_url("arrow_down_dark_normal.svg"),
    "up_d": _arrow_url("arrow_up_dark_disabled.svg"),
    "down_d": _arrow_url("arrow_down_dark_disabled.svg"),
}

_DIALOG_PATCH = """

/* **三个分页对话框的右侧页容器**（选项 / 工程属性 / 图层属性
   都是 `app._NavDialog` 的子类）—— 用户："**右侧面板应当是主题
   背景色！**"（第一版我用了 `panel_hi`，太重、被否）。

   取 **`panel`** 的依据：对话框卡片自己铺的是 `window`
   （`ggs_base.GgsFramelessMixin.paintEvent` 那句 `fillPath(..., pal["window"])`），
   而 `panel` 正是主题里"工具栏 / 面板标题 / 表头"的底色 ⇒ 两种主题下都与
   卡片底**有明显区分**（浅：#ffffff 面板 vs #f3f4f7 卡片底；深：#242932 vs
   #1e2229），并且是**主题自己的面板色**、不是另造的颜色。
   ⚠ 别换成 `input`：浅色主题下 input 与 window、panel 全是近白（`_card_bg`
   踩过同一个坑）。圆角 6px 与卡片 / 输入控件同档。 */
/* 页底从 `panel` 换成 **`window`**（= 对话框自己的面底色，见
   `ggs_base.GgsFramelessMixin.paintEvent`）—— 浅色主题下 `panel` 是纯白
   （#ffffff）、`window` 是 #f3f4f7，"一整块白面板"正是用户看到的那片白；
   深色下 #242932 → #1e2229，右侧页与对话框外壳连成一体。
   分组卡片（`GgsAboutCard`，底 `group_bg`）因此**浮在这层底色上**，边界由
   卡片自己的 1px `border_soft` 给 —— 与「关于 GmaGIS」的运行环境卡片同规格。 */
QStackedWidget#GgsPageStack {
  background: %(window)s;
  border-radius: 6px;
}
/*
   导航列表（`_NavDialog.nav`）现用项目标准列表控件 `GgsListWidget`（无框、
   融进容器）。**边框 + 背景交给左列容器 `GgsNavHost`**（对话框左面板），
   列表本身透明融进去 ⇒ 选项 / 图层属性左侧恢复成"带边框的面板底"。
   ⚠ 本段 `_DIALOG_PATCH` 由百分号格式化串渲染（见文件末尾 `LIGHT_QSS`/
   `DARK_QSS`）：占位符必须写成"百分号(键名)s"形式且键在 `_DIALOG_KEYS`
   内（`panel` / `border` 都在）；不要写花括号形式（format 风格，本段不替换）。 */
QWidget#GgsNavHost {
  background: %(panel)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
  padding: 6px;
}
/* 分页对话框的页面**外包了一层 `QScrollArea`**
   （`_NavDialog._wrap_page` —— 窗口变矮时出滚动条，而不是把每行压扁）。
   滚动区**不在这里写样式**：上面那两条全局规则
   （`QScrollArea` 与 `QScrollArea > QWidget > QWidget` = viewport）
   已经把背景与边框都设成透明无框了 ⇒ 再写一条 `#GgsPageScroll` 是冗余。
   ⚠ 万一以后给某类 QScrollArea 单独上底色，记得给这里的 viewport 补透明，
   否则会把 `#GgsPageStack` 的 panel 底色盖成 viewport 白底。 */
/* 颜色快选面板（`ui/dialogs/color.py::GgsColorPopup`）——
   它是 `Qt.Popup` 无边框窗口，不写背景的话在深色主题下就是一块刺眼的白。 */
QFrame#GgsColorPopup {
  background: %(input)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
}
/* 同一块面板**嵌进菜单**时（`embedded=True` 会换成这个
   objectName）—— **不能再带自己的边框与底色**：菜单条目本身就有一层底，
   两层叠起来就是用户报的"**两层边框嵌套**"。这里只留一圈内边距。 */
QWidget#GgsColorPopupEmbedded {
  background: transparent;
  border: none;
}
/* 7 点需求②（树图标 / 树外观统一）：`GgsShortcutTree`（快捷键速查表）与
   `GgsToolboxTree`（模型构建器算法树）原先各有专属 QSS（外框 / 自定义行高 /
   自定义 padding / 自定义选中底色），导致它们和浏览器树、图层树、识别树等
   **标准树长得不一样**。现统一撤掉专属规则，让它们**继承**项目标准树的通用
   `QTreeWidget::item` 外观（悬停 / 选中 / 行高 24px / 图标 16px 均由
   `treeview.py::_apply_tree_common` + 上方通用 QSS 一处给）。
   ⚠ 两棵本就是 `GgsTreeWidget` 子类，只因 `setProperty("ggsStdTree", False)`
   + 专属 objectName 才走了差异化样式；撤掉专属 QSS 后即与其它树逐像素一致。
   （`GgsToolboxTree` 的 objectName 在重构时已随算法树改 `GgsTreeWidget` 而停用，
   此处一并清理死规则；快捷键树仍用 objectName `GgsShortcutTree`，但不再有专属
   样式，仅保留表头 / 隔行色等由代码开关控制的表格特征。） */
QLabel#GgsDimLabel {
  color: %(text_dim)s;
  padding-top: 2px;
}
/* 功能区里的「小标签」（布局设计器顶栏的 纸张/方向/分辨率 与
   页边距那四个字）。比正文小一档、用弱化色，才不会跟组标题抢视线。 */
QLabel#GgsRibbonMini {
  color: %(text_dim)s;
  font-size: 11px;
}
/* ---- 样式管理器（界面重构补的专属样式）----
   此前这个窗口**一条规则都没有**（搜 GgsStyle 零命中），列表选中走的是系统
   Highlight（饱和蓝底 + 深色字，对比很差），预览框与状态条也是没有边界的白。

   1. 两个列表的选中 / 悬停：与分页对话框的导航列表同口径 —— 选中用
      accent_soft 底、悬停用 panel_hi 底。左侧分类列表的文字由
      `_CatDelegate` 自绘（取调色板 Text 角色）⇒ 选中态**不要**在这里写
      color，否则 QSS 与自绘两套颜色会打架。
   2. 预览框 / 状态条：浅底 + 6px 圆角（与卡片窗体同档）。状态条**不描边**
      —— 它是常驻的一条，加了边框会变成一块悬在按钮上方的空框。 */
QListWidget#GgsStyleCats::item:selected,
QListWidget#GgsStyleItems::item:selected {
  background: %(accent_soft)s;
}
QListWidget#GgsStyleCats::item:hover:!selected,
QListWidget#GgsStyleItems::item:hover:!selected {
  background: %(panel_hi)s;
}
QLabel#GgsStyleHint {
  color: %(text_dim)s;
}
QLabel#GgsStylePreview {
  background: %(panel)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
}
QLabel#GgsStyleStatus {
  background: %(panel)s;
  border-radius: 6px;
  padding: 3px 8px;
  color: %(text_dim)s;
}
"""

_RIBBON_PATCH = """
/* ---- 功能区（Ribbon）---- */
QWidget#GgsRibbon {
  /* round41u：功能区外层也用窗口背景色（标题栏+页签行统一扁平） */
  background: %(window)s;
  border: 0;
}
/* **布局设计器自带的那条 Ribbon**（`GgsLayoutRibbon`）。
   嵌入视图页时它就是顶上那一行（工程按钮 + 开始/页面/视图 页签），必须与主
   功能区同底色 —— 否则标题栏下面那条会露出另一种灰。 */
QWidget#GgsLayoutRibbon {
  background: %(window)s;
  border: 0;
}
/* **模型构建器自带的那条 Ribbon**（`GgsModelRibbon`）—— 同一条
   口径（顶上那一行与主功能区同底色）。 */
QWidget#GgsModelRibbon {
  background: %(window)s;
  border: 0;
}
QTabBar#GgsRibbonTabs {
  /* round41u：功能区页签行（功能区标题栏）直接用窗口背景色 */
  background: %(window)s;
  border: 0;
}
QTabBar#GgsRibbonTabs::tab {
  min-width: 0;
  /* 纵向 padding 5 → 4 —— 页签条是**固定高 25**（`tabs
     .setFixedHeight(HEADER_H + 1)`），而 tab 的自然高 = 文字高 + 上下 padding：
     9pt 文字 ~17 + 5+5 = 27 > 25 ⇒ 上下各被裁掉 1px；收到 4 ⇒ 25，
     正好占满不裁切，且文字离底边更近（贴底的横线也就离文字更近）。
     ⚠ 字号最终定 **9.5pt**（9/9.5/10 来回五轮，用户拍板 9.5）：
     9pt 时 17 + 4+4 = 25（= 页签条高，正好）；9.5pt 时 18 + 4+4 = 26
     ⇒ 内容与页签条**同款**（#450 那版就是这个组合，用户已验收过、无裁切）。
     ⚠ 若以后把字号再往上调（10pt 及以上），这里要让回 1px/号，别让
     "文字高 + 上下 padding" 超出页签条太多，否则贴底的横线离文字又变远。
     左右 10 → **7**（每枚页签窄 6px ⇒ 整排更紧凑）。
     ⚠⚠ 同日再续：`margin` 2 → **3**（页签
     **之间**的间隔各加 1px ⇒ 相邻两枚间距 4 → 6）。
     ⚠⚠⚠ **这个 margin 必须与 `ribbon.TAB_MARGIN_X` 同数**：`tabRect()`
     含这层 margin，底部横线的"铺满宽度"和上下文页签底色块都按它内收，
     已统一走那个常量 —— 只改这里不改代码，横线会宽出可见块（静默错位）。 */
  padding: 4px 7px;
  margin: 0 3px;
  /* **常态就是正文色** —— 上一轮把常态改成了 `text_dim`，看着
     整条页签都发灰。"浅"那一档是**悬停**专用的（见 `:hover`），常态/选中
     一律正文色，靠"加粗 + 指示线"区分选中。 */
  color: %(text)s;
  /* 这一条来回了五轮：9 → 9.5 → 10 → 9.5 → 9，
     用户最后："**不行，还是用 9.5 吧**" ⇒ **定稿 9.5pt**（别再改了）。
     ⚠ 比应用字体（9pt）大半号，是用户**明确**要的；「工程」按钮仍是 9pt。
     ⚠⚠ **两处必须同号**：`ribbon.TAB_FONT_PT`（代码里量文字宽度用，
     底部横线要按文字长度画）与这里的 9.5pt —— 改一个就得改另一个，
     只改这里 ⇒ 线比文字短一截（QSS 的 font-size **不改控件 font**）。 */
  font-size: 9.5pt;
  background: transparent;
  border: none;
  border-radius: 5px;
}
QTabBar#GgsRibbonTabs::tab:hover {
  /* 底色去掉；**文字反而浅一档**
     （`text_dim`）—— 悬停是"轻提示"，靠"文字变浅 + 底部一条淡线"表达，
     不靠深色和底色（那会让悬停比选中还重）。
     底部那条横线由 `_RibbonTabBar._paint_hover_line` **自绘** —— 这条
     QTabBar 上 QSS 的 border 根本不渲染（选中指示线也是自绘的，见下）。
     ⚠ 别在这里补 `border-bottom`，写了也不会画出来。 */
  color: %(text_dim)s;
  background: transparent;
}
QTabBar#GgsRibbonTabs::tab:selected {
  color: %(text)s;
  /* **无 font-weight（也不能加）**——r710 离屏实测（windows 原生平台 +
     offscreen 双验证，build/_r710b_env_probe.py / _r710c_fix_probe.py）：
     QSS 加粗后 Qt 用**粗体度量**做文字居中 ⇒ 文字**上移 1px**（墨迹
     top 10→9），且 QSS 渲染的 Bold 字形比 Regular **高 1px**（bbox
     31x15→31x16、宽零变化）＝用户报的"瘦高+上移"。
     选中态的加粗改走 `_RibbonTabBar._draw_tab_label`：Regular 字形
     **横向对称加宽**（竖笔画每侧 +0.3px）——实测雅黑 Bold 的墨迹比
     Regular 高 1 设备像素（"变高"，用户已否），shift 方案墨迹高度
     与 Regular 逐像素一致、粗细可调（_SEL_BOLD_SHIFT）。
     ⚠ 所有页签（选中/未选中）统一自绘、共用同一基线公式，故不再需要
     按字体/DPR 实测的 dy 校准；选中与未选中墨顶差实测恒为 0。
     ⚠ `tabSizeHint` 不预留粗体宽度、`_line_geom` 按常规体量线宽
     （加粗字形不参与布局测量，见 ribbon.py）。 */
  background: %(window)s;
}
/* 选中页签下方的指示线（QSS 的 border-bottom 在该 QTabBar 上
   不渲染，用子控件实现更可靠）—— 蓝 → 主题灰 → 现与 accent 同色。
   ⚠ 实际颜色由 `ribbon._update_tab_indicator` 用内联样式表按主题重写
   （这里只是兜底）；厚度 `TAB_LINE_H` 也在代码里（由 2 加到 3：
   用户报"选中选项卡底部的横线有点细"）。
   ⚠ 用户明确"不是改下面的横线" ⇒ 横线保持 accent，不去碰它；
   选中文字的加粗改走原地重画（见上方 `::tab:selected` 注释）。 */
QFrame#GgsRibbonTabIndicator {
  background-color: %(accent)s;
  border: 0;
  border-radius: 0;
}
QToolButton#GgsAppButton::menu-indicator {
  image: none;
  width: 0;
}
/* 下拉按钮整键弹菜单（InstantPopup）后，原生气泡指示器与自定义
   箭头条重复，统一隐藏 */
QToolButton::menu-indicator {
  image: none;
  width: 0;
}
/* 功能区里的容器必须显式声明背景：浅色主题的 style.qss 有一条
   `QWidget { background-color: white }`，不写会被整片刷白。
   Office 布局：页签行用面板色，内容区（页/堆栈）统一铺略深一档的
   底色，组本身透明、组间只用竖线分隔。 */
QWidget#GgsRibbonBody,
QWidget#GgsRibbonGroup {
  background: transparent;
  border: 0;
  padding: 0;
}
QWidget#GgsRibbonPage,
QStackedWidget#GgsRibbonStack {
  background: %(group_bg)s;
  border: 0;
  border-radius: 6px;
  padding: 0;
}
/* 页签下方的内容区整体一圈圆角边界（ArcGIS Pro 同款观感） */
QStackedWidget#GgsRibbonStack {
  border: 1px solid %(border_soft)s;
  border-radius: 6px;
}
/* 页签内容的横向滚动容器（窄窗口按需出滚动条）也要透明 */
QScrollArea#GgsRibbonScroll,
QScrollArea#GgsRibbonScroll > QWidget > QWidget {
  background: transparent;
  border: 0;
}
QScrollArea#GgsRibbonScroll QScrollBar:horizontal {
  height: 8px;
}
QWidget#GgsRibbonGroup {
  background: transparent;
  border-right: 1px solid %(border_soft)s;
  margin: 1px 0 2px 0;
}
QLabel#GgsRibbonCaption {
  color: %(text)s;
  font-size: 8.5pt;
  background: transparent;
}
QFrame#GgsRibbonSep {
  background: %(border_soft)s;
}
/* 用"祖先 + ID"提高优先级：style.qss 里的裸 QToolButton 规则不少，
   只写 ID 有可能被同权重的后随规则盖掉。 */
/* **去掉祖先限定 `QWidget#GgsRibbon`** —— 布局设计器那条 Ribbon
   （objectName 是 `GgsLayoutRibbon`）里的「工程」按钮要用**同一份样式**：
   全区域视图下顶上那一行是设计器自己的 Ribbon（[工程][开始|页面|视图]），
   与地图视图的 [工程][地图|分析|…] 必须是同一个版式。
   ⚠ 全仓只有 `Ribbon.app_button` 用这个 objectName，去掉限定不会波及其它控件。 */
QToolButton#GgsAppButton {
  /* 纵向 padding 必须为 0——25px 高 - 上下 2px 后内容区
     21px 装不下 9.5-10pt 雅黑粗体行高（19-22px），"工程"二字顶部
     被裁 1px（同 GgsProjectBtn 的病灶） */
  padding: 0 8px;
  color: %(accent_text)s;
  background: %(accent)s;
  border: 0;
  border-radius: 6px;
  font-weight: 600;
}
QToolButton#GgsAppButton:hover {
  background: %(accent_hi)s;
}
QToolButton[ribbonBig="true"] {
  padding: 2px 2px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: %(text)s;
}
QToolButton[ribbonBig="true"]:hover {
  background: %(panel_hi)s;
}
QToolButton[ribbonBig="true"]:checked,
QToolButton[ribbonBig="true"]:pressed {
  background: %(panel_dn)s;
  border: 1px solid %(border)s;
}
QToolButton[ribbonBig="true"]:disabled,
QToolButton[ribbonBig="true"]:checked:disabled,
QToolButton[ribbonBig="true"]:pressed:disabled {
  /* 同上——大按钮灰显时不得残留 :checked/:pressed 的
     panel_dn 底 + 描边（"不可用却像被按下"）。 */
  background: transparent;
  border: 1px solid transparent;
  color: %(text_disabled)s;
}
/* 下拉分裂按钮容器：「主体 + 箭头条」两行合成一个按钮框，
   悬停 / 按下态画在容器上（事件过滤器同步，见 ribbon.add_dropdown） */
QFrame#GgsRibbonDrop {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
}
QFrame#GgsRibbonDrop[ddHover="true"] {
  background: %(panel_hi)s;
}
QFrame#GgsRibbonDrop[ddDown="true"] {
  background: %(panel_dn)s;
  border: 1px solid %(border)s;
}
/* 容器内的按钮本体不再自绘高亮，避免"图标和箭头不是一个整体" */
QFrame#GgsRibbonDrop QToolButton[inDrop="true"] {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0;
}
QFrame#GgsRibbonDrop QToolButton[inDrop="true"]:hover,
QFrame#GgsRibbonDrop QToolButton[inDrop="true"]:pressed,
QFrame#GgsRibbonDrop QToolButton[inDrop="true"]:checked {
  background: transparent;
  border: 1px solid transparent;
}
/* ---- 按钮样式2（Office 同款，用户参考图定稿）----
   大图标菜单：
   悬停 = 容器 1px 圆角描边提示（DropWrap 自绘，见 ribbon.py）
          + 局部背景（图标按钮 / 文本箭头区各自浅蓝）；
   按下/菜单打开 = 整个大按钮浅底背景（DropWrap 自绘） */
QFrame#GgsRibbonDrop[style2="true"] {
  background: transparent;
  border: none;   /* 基础规则的 1px transparent border 会把
                     contentsMargins 撑大 1px，68px 行骨架只剩 66，
                     图标行/文本行互相挤压错位 */
  border-radius: 6px;
}
/* 图标按钮：图标墨迹在 32px 画布里偏上（行 1..21，中心 11.0），
   通用 padding 2px 时墨迹中心只有 15.3，比样式1 图标中心 17.0
   偏高 1.7px——padding-top 5px 下压到 17.3（d=+0.3）。实测响应
   曲线 pt=2→15.3 / 3,4→16.1 / 5→17.3 / 6→17.7（round41q） */
QFrame#GgsRibbonDrop[style2="true"] QToolButton[style2Icon="true"] {
  padding: 5px 1px 2px;
  /* （用户"大图标按钮点击图标部分，图标会有缩小
     动画？我哪里说要加动画了！详细案例是新建文件按钮！"）：**常态就要把
     1px transparent border 占住**。
     原因：`:pressed` 那条（下一段）带 `border: 1px solid transparent`
     —— QSS 的 border 会**占盒模型**（不像 background 那样不影响内容
     区），而**常态这条原来没有 border** ⇒ 按下瞬间内容区四周各少 2px
     ⇒ `QToolButton` 把图标重排进更小的可用区（`BIG_ICON` 是按可用区
     算的）⇒ **视觉上图标缩小一像素**。
     ⚠ 那段注释写的是"显式 1px transparent border **占位**：按下时图标不
       因边框有无而跳动"—— 意图完全正确，但**只做了一半**：只给 pressed
       加了、没给常态加，等于用一个新问题（按下有框/常态无框）替换掉
       原来那个（按下有下划线）。⇒ 两侧必须同宽。
     ⚠ 顺带修掉`GgsBigButtonStyle1/2` 的"按下图标缩小"（两者共用
       `[style2Icon]`，走同一条 `_add_style01`）。 */
  border: 1px solid transparent;
}
/* 图标按钮局部悬停背景 = panel_hi（主题悬停灰——用户定稿：悬停
   一律用主题灰，不是淡蓝）；pressed 时局部视觉消失——按下按整个
   大按钮处理（DropWrap 画整体背景），避免两层反馈 */
QFrame#GgsRibbonDrop[style2="true"] QToolButton[style2Icon="true"]:hover {
  background: %(panel_hi)s;
  border-radius: 4px;
  /* **必须重复一遍占位 border**（不能靠上面那条常态规则）。
     本规则与常态规则**特异度相同**（都是 2 个 #id + 1 类 + 1 属性/伪类）
     ⇒ QSS 同特异度**后声明胜** ⇒ 只写 background 会把常态的
     `border: 1px solid transparent` **一并重置为 0**（QSS 是整体替换，
     不是逐属性合并）⇒ 鼠标移上去的那一帧图标又会缩1px。
     ⇒凡是"常态有、状态态也要有"的 border，**每个规则都要写全**。 */
  border: 1px solid transparent;
}
QFrame#GgsRibbonDrop[style2="true"] QToolButton[style2Icon="true"]:pressed {
  background: transparent;
  /* 显式 1px transparent border 占位：按下时图标不因边框有无而跳动
     （round41t 起通用 pressed 规则已无 accent 下划线，此处只为占位） */
  border: 1px solid transparent;
  border-radius: 4px;
}
/* checked 态压制（round41u 统一修复）：图标/文本按钮挂 checkable
   主体动作（测量/选择），菜单里选完功能后动作进勾选态——不压会
   常驻 panel_dn 背景+描边，混同按下反馈（样式1 系列的 inDrop 规则
   本就全状态压制；样式2 只压 checked，hover/pressed 设计保留） */
QFrame#GgsRibbonDrop[style2="true"] QToolButton[style2Icon="true"]:checked,
QFrame#GgsRibbonDrop[style2="true"] QFrame#GgsRibbonDropZone QToolButton:checked {
  background: transparent;
  /* 勾选态也必须保留 1px transparent 占位，与常态/hover/
     pressed 同宽——否则勾选瞬间内容区四周各多 2px，图标放大 1px
     。`background:
     transparent` 已压制 panel_dn，border 占位不影响原 intent。 */
  border: 1px solid transparent;
}
/* 下部「文本+箭头」合体按钮：独立可点（弹菜单），悬停灰色局部
   背景（panel_hi，同上）。不用 QSS border——border（含 transparent）
   会把 contentsMargins 撑大 1px，行放不下被挤压 */
QFrame#GgsRibbonDropZone {
  background: transparent;
  border-radius: 6px;
}
QFrame#GgsRibbonDropZone:hover {
  background: %(panel_hi)s;
}
/* 禁用态（容器 ddOff，见 ribbon._sync_off）：不画任何悬停背景，
   只保留悬停提示。zone / 图标按钮未必跟随动作禁用，QSS 的 :hover
   拦不住，靠这条后代规则整段压制（特异度高于上面的裸 :hover） */
QFrame#GgsRibbonDrop[ddOff="true"] QFrame#GgsRibbonDropZone:hover {
  background: transparent;
}
/* 图标按钮**单独**一条（不能与DropZone 合并）——
   占位 border 必须在每个状态规则里重复写全（QSS 是整段替换，
   只写 background 会把常态的 border 重置为 0 ⇒ 图标缩 1px）。
   ⚠ DropZone（文本行）**故意不带** border：它常态就没有，
     给了会把 17px 文本行压窄 2px ⇒ 换一种抖动。 */
QFrame#GgsRibbonDrop[ddOff="true"] QToolButton[style2Icon="true"]:hover {
  background: transparent;
  border: 1px solid transparent;
}
/* 文本行字形完整（round41q）：通用规则的 padding: 2px 1px 会把
   17px 行的内容区压到 11px，字形下部被裁（用户反馈"文本下部显示
   不全"）——这里清掉纵向 padding，内容区 15px 恰好容下字形
   fm.height()≈15。双 ID 选择器特异性更高，不受声明顺序影响 */
QFrame#GgsRibbonDrop[style2="true"] QFrame#GgsRibbonDropZone QToolButton {
  padding: 0 1px;
}
/* 用户独立大图标按钮（_add_style01，GgsBigButtonStyle1/2）
   的文本行 txt 挂 s2Seg=true、不在 DropZone 内，会落到基础规则
   `QWidget#GgsRibbonPage QToolButton{padding:2px 1px}` 把 17px 文本行
   。这里清掉纵向 padding，与 DropZone 文本行同口径
   释放；双 ID + 属性选择器特异度压过基础规则。本规则不命中 DropZone
   内的文本/箭头行（那条由上一行以更高特异度覆盖），只作用于独立
   大按钮的文本行。 */
QFrame#GgsRibbonDrop[style2="true"] QToolButton[s2Seg="true"] {
  padding: 0 1px;
}
/* 按下/菜单打开期间（ddDown）：局部背景全部让位，只显示大按钮的
   整体样式（DropWrap 自绘，参考样式1 按下态） */
QFrame#GgsRibbonDrop[ddDown="true"] QFrame#GgsRibbonDropZone {
  background: transparent;
}
/* 同上，图标按钮单独一条（这条正好在"按下期间"生效，
   只写 background ⇒ border 被重置为 0 ⇒ **按下图标缩小**）。 */
QFrame#GgsRibbonDrop[ddDown="true"] QToolButton[style2Icon="true"] {
  background: transparent;
  border: 1px solid transparent;
}
/* ---- 样式2 变体（round41t 新增，仅样式预览页）----
   1-1 = 样式2 三行骨架整体化：图标按钮同样挂 inDrop（press 统一
   拦截弹菜单，见 ribbon.add_dropdown），无任何子按钮局部视觉。
   压制必须不带伪状态整段覆盖（特异度 (1,2,2) 高于页面规则
   (1,1,1)）：txt_btn 挂 checkable 主体动作（测量/选择），菜单里
   选完功能后动作进 checked 态，只压 :hover 会在文本行残留 checked
   背景+描边（round41u 用户报"点击某个功能后文本部分背景残存"
   根因）；border 用 none 不占位，避免撑大 17px 文本行内容区 */
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigMenuButtonStyle1"] QToolButton,
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigMenuButtonStyle1"] QFrame#GgsRibbonDropZone {
  background: transparent;
  border: none;
  border-radius: 4px;
}
/* 用户GgsBigMenuButtonStyle1 图标按钮——常态/悬停/按下/
   勾选四态共用同一盒模型（padding 5px 1px 2px + 1px transparent 占位
   边框）。根因：上面那条把本变体子按钮的 `border` 设成 `none`（不占位，
   避免撑大 17px 文本行），但图标按钮在 `:hover`（rule2186 / rule2229 带
   1px 边框）时内容区四周各少 2px ⇒ 图标被重排缩小 ⇒ "悬停图标会缩小"。
   用户指明"缩小态才是正常态" ⇒ 给图标按钮在**所有态**补回 1px transparent
   占位、与 hover 同宽，图标尺寸恒定、悬停不再变化。仅压图标按钮
   （style2Icon），文本/箭头行（s2Seg，DropZone 内）保持 border:none 不动。
   特异性 (1,4,2) 高于 2330 那条 (1,2,2) 与 2186 / 2229。 */
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigMenuButtonStyle1"] QToolButton[style2Icon="true"],
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigMenuButtonStyle1"] QToolButton[style2Icon="true"]:hover,
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigMenuButtonStyle1"] QToolButton[style2Icon="true"]:pressed,
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigMenuButtonStyle1"] QToolButton[style2Icon="true"]:checked {
  padding: 5px 1px 2px;
  border: 1px solid transparent;
  background: transparent;
}
/* 0-1 = 样式2 规格两行（图标 33 / 文本 17）合体整体按钮，无箭头
   无菜单，点击任意处触发动作——子按钮全部无局部视觉（含 checked：
   挂 checkable 动作的按钮点完后动作进勾选态，不压会残留背景）。
   0-2 = 0-1 + 激活态容器级底色（动作勾选时 DropWrap 自绘
   accent_soft 整块填充），同样压制子按钮的 checked 局部背景 */
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigButtonStyle1"] QToolButton,
QFrame#GgsRibbonDrop[style2="true"][s2variant="GgsBigCheckButtonStyle1"] QToolButton {
  background: transparent;
  /* `border` 这里**不能**写 `none`，要写 `1px solid transparent`
     占位。常驻可见的是**图标按钮**（`_add_style01` 给它挂了
     `[style2Icon]`，padding 5px 1px 2px），而图标按钮那条
     `:pressed` 规则（`[style2Icon="true"]:pressed`）**带** 1px 边框
     —— QSS 的 border 占盒模型，于是"按下有框 / 常态无框"⇒ 内容区
     。
     ⚠ 特异度要算对：`:pressed` 那条是 **(2,1,3)**（两个 #id），
       本条是 **(1,1,3)** ⇒ pressed **本来就赢** ⇒ 就算这里写占位
       border，常态与按下仍同宽，图标不抖。 */
  border: 1px solid transparent;
  border-radius: 4px;
}
/* 小图菜单样式2：悬停 = 浅蓝高亮（图3）；
   按下/菜单打开 = 浅底 + 描边（图4） */
QWidget#GgsRibbonPage QToolButton[style2="true"]:hover {
  background: %(s2_hover)s;
  border: 1px solid transparent;
}
QWidget#GgsRibbonPage QToolButton[style2="true"]:pressed,
QWidget#GgsRibbonPage QToolButton[style2="true"]:checked {
  background: %(s2_down)s;
  border: 1px solid %(s2_border)s;
}
/* 小图菜单（样式5/6，SmallDropButton）checked 压制（round41u）：
   主体是 InstantPopup 弹菜单、不触发动作——动作被外部置勾选态
   （工具激活同步）时按钮不得渲染 checked 背景，否则常驻一块
   s2_down/panel_dn 混同按下反馈。:pressed 保留（弹菜单按下反馈）；
   声明在 [style2]:checked 之后，同特异度后声明胜。独立小按钮
   （样式3/4）直接触发动作，checked 高亮是激活反馈，不受本规则 */
QWidget#GgsRibbonPage QToolButton[dropSmall="true"]:checked {
  background: transparent;
  border: none;
}
QWidget#GgsRibbonPage QToolButton {
  /* 功能按钮不吃 style.qss 的 `QToolButton{background:white}`：
     浅色下按钮不能自带底色，悬停/按下才出现高亮 */
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 2px 1px;
  color: %(text)s;
}
QWidget#GgsRibbonPage QToolButton:hover {
  background: %(panel_hi)s;
}
QWidget#GgsRibbonPage QToolButton:checked,
QWidget#GgsRibbonPage QToolButton:pressed {
  background: %(panel_dn)s;
  border: 1px solid %(border)s;
}
/* 页面内按钮的禁用态一律「零装饰」——用户反馈「按钮处于不
   可用状态时不能处于点击状态」。上面 :checked/:pressed（含
   [style2]/[dropSmall] 变体）都只声明 background/border，靠 :disabled
   改 color 是盖不住的：同特异度后声明胜，而那些规则的特异度更高（带
   属性选择器）。这里把各种「禁用 + 勾选/按下」组合显式列全清空。
   灰显按钮保留悬停提示（tooltip 不经 QSS），只是不再有任何点击暗示 */
QWidget#GgsRibbonPage QToolButton:disabled,
QWidget#GgsRibbonPage QToolButton:disabled:hover,
QWidget#GgsRibbonPage QToolButton:disabled:checked,
QWidget#GgsRibbonPage QToolButton:disabled:pressed,
QWidget#GgsRibbonPage QToolButton[style2="true"]:disabled,
QWidget#GgsRibbonPage QToolButton[style2="true"]:disabled:checked,
QWidget#GgsRibbonPage QToolButton[style2="true"]:disabled:pressed,
QWidget#GgsRibbonPage QToolButton[dropSmall="true"]:disabled:checked {
  background: transparent;
  border: 1px solid transparent;
  color: %(text_disabled)s;
}

/* ---- 快速访问工具栏（已并入自定义标题栏，样式见 #GgsTitleBtn） ---- */

/* ---- 功能区折叠按钮 ---- */
/* 选择器带祖先 ID 提权：压过上面的 #GgsRibbonPage QToolButton 规则 */
QWidget#GgsRibbon QToolButton#GgsRibbonCollapseBtn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: %(text_dim)s;
  font-size: 9pt;
  padding: 0 2px;
}
QWidget#GgsRibbon QToolButton#GgsRibbonCollapseBtn:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
  color: %(text)s;
}
QWidget#GgsRibbon QToolButton#GgsRibbonCollapseBtn:pressed {
  background: %(panel_dn)s;
}

/* ---- 功能区「>>」溢出按钮（页行右缘，分组放不下时出现） ---- */
QWidget#GgsRibbon QToolButton#GgsRibbonOverflow {
  background: %(panel)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
  color: %(text_dim)s;
  font-size: 9pt;
  font-weight: 600;
  padding: 0 2px;
}
QWidget#GgsRibbon QToolButton#GgsRibbonOverflow:hover {
  background: %(panel_hi)s;
  border-color: %(focus)s;
  color: %(text)s;
}

/* ---- 分组折叠按钮：**已改用现成的「GgsBigMenuButtonStyle3」骨架**（） ----
   这里曾有一条自创的 QToolButton#GgsRibbonGroupBtn 规则。用户明确要求
   "使用GgsBigMenuButtonStyle3，不要乱新增样式" ⇒ 折叠按钮现在直接复用
   GgsRibbonDrop[style2] + [s2variant="GgsBigMenuButtonStyle3"] 那套规则，本段已删除。 */

/* ---- 自定义标题栏 ---- */
/* GgsTitleHost：标题栏 + 经典菜单栏的宿主（QMainWindow 的 menuWidget），
   必须显式上底色，否则露出的基础窗口是黑的 */
QWidget#GgsTitleHost,
QWidget#GgsTitleBar {
  /* round41u：标题栏直接用窗口背景色（不再用 panel 色，更扁平） */
  background: %(window)s;
  border: 0;
}
QWidget#GgsTitleBar {
  spacing: 0;
  padding: 0;
}
/* 标题栏工程名按钮（ArcGIS Pro 同款：工程名 + 下拉箭头）
   纵向 padding 清零——按钮固定 24px 高，再扣 2px padding
   + 1px 边框后内容区只剩 18px，YaHei 9.5-10pt 粗体行高 18-19px，
   文字顶部正好被裁 1px（用户报"工程按钮顶部显示不全"的根因） */
QToolButton#GgsProjectBtn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: %(text)s;
  font-size: 10pt;
  /* 右侧留 22px 给 menu-indicator 的下拉箭头（纵向仍必须为 0，
     见上面的 说明：加了纵向 padding 文字会被裁 1px） */
  padding: 0 22px 0 8px;
}
QToolButton#GgsProjectBtn:hover {
  background: %(panel_dn)s;
  border-color: %(border)s;
}
/* 工程名按钮的下拉箭头（）
   用户："向下箭头应该在文字右边"。走 menu-indicator 而不是按钮图标：
   subcontrol 按定义就贴在内容区右侧，也能按主题换深浅两色贴图
   （%(combo_arrow)s = combo_arrow_dark / light.svg，与下拉框同一份资源）。
   右侧 padding 留到 22px，否则文字右缘会压到箭头上。 */
QToolButton#GgsProjectBtn::menu-indicator {
  image: %(combo_arrow)s;
  width: 10px; height: 10px;
  subcontrol-origin: padding;
  subcontrol-position: right center;
  right: 6px;
}
/* 标题栏里的快速访问小按钮（复用共享 QAction） */
QToolButton#GgsTitleBtn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: %(text)s;
  /* 图标严格居中：通用 QToolButton 有 3px padding，且 menu-indicator
     子控件即使 image 设成 none 仍会在内容区一侧留白，把 18px 图标推偏
     —— 用户报「图标不在按钮中部、似乎偏右」。这里 padding / margin
     归零，下面再把 indicator 的宽高也归零，左右就完全对称了。 */
  padding: 0;
  margin: 0;
}
QToolButton#GgsTitleBtn::menu-indicator {
  image: none;
  width: 0;
  height: 0;
}
QToolButton#GgsTitleBtn:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
}
/* 标题栏「自动保存」组合控件里的文字标签：两个主题下都要用正文色，
   否则深色主题会沿用默认灰色、和旁边工程名按钮的明度对不上。 */
QLabel#GgsAutoSaveLabel { color: %(text)s; }
/* 自动保存开关改用 GgsSwitch 自绘控件（标题栏里固定 30×16），
   不再有可勾选的 QToolButton，故这里无需 checked 规则。 */
/* 窗口控制按钮 */
QToolButton#GgsWinBtn {
  background: transparent;
  border: 0;
  color: %(text)s;
}
QToolButton#GgsWinBtn:hover { background: %(panel_hi)s; }
/* HTMAXBUTTON 区域是非客户区，Qt 悬停事件不可用，
   悬停高亮由 nativeEvent 打 hot 属性驱动（见 mainwindow._set_max_hot） */
QToolButton#GgsWinBtn[hot="true"] { background: %(panel_hi)s; }
QToolButton#GgsWinBtn[hot="true"]:pressed { background: %(border)s; }
QToolButton#GgsWinClose {
  background: transparent;
  border: 0;
  color: %(text)s;
}
QToolButton#GgsWinClose:hover {
  background: #e81123;
  color: #ffffff;
}

/* ---- 标题栏中部的全局功能搜索（） ----
   标题栏固定 32px 高，搜索框取 24px 居中，上下各留 4px；
   浅底 + 圆角，在一排透明按钮里视觉上能一眼认出"这里可以打字"。
   圆角 12px（胶囊）→ 6px，与项目其它输入控件
   （_TEMPLATE 里 QLineEdit 的 border-radius: 6px）保持一致。 */
QFrame#GgsSearchBar { background: transparent; border: none; }
QLineEdit#GgsSearchEdit {
  background: %(input)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
  /* 收紧 leading 放大镜图标与文字间距——左 padding 10→2
     （图标贴左、与文字之间只留 action 自身小间隙），右 8 给 clear 按钮。
     影响全部 GgsSearchEdit（标题栏与工具箱一致）。 */
  padding: 0 8px 0 2px;
  color: %(text)s;
  selection-background-color: %(accent_soft)s;
  selection-color: %(text)s;
  /* ：
     这条规则原来**没有高度** —— 于是它吃 `_TEMPLATE` 里那条
     `QLineEdit { min-height: 24px }`，那个高度是**内容高**，加上下各 1px
     边框就是 26 总高；而容器是 `ui.framework.searchbar._BAR_H`（代码里的逻辑 px）
     —— 输入框比容器高，**底部（连那 1px 边框）被父容器裁掉**，
     看着就是"底部被遮挡"。
     ⇒ 起高度**分两处写**（见下面 `QFrame#GgsSearchBar` 那条与
     本模板通用 `QLineEdit` 那条）：
       · 标题栏里 = 22 内容 + 2 边框 = 24（容器 26，上下各留 1）；
       · 对话框里（`_NavDialog` 的同一个对象名）**不吃**那条 ⇒ 回落到
         通用 `QLineEdit` 的 24 内容 = 26 总高，与对话框里其它输入框齐平。
     ⚠⚠ 这段属于 `_RIBBON_PATCH`，那是一张**用百分号做占位符的模板** ⇒
     注释里**不许出现裸的百分号**（哪怕只是写"百分之百"三个字也不行 ——
     要写就写中文，别写那个符号），否则 import 期直接 TypeError。 */
}
QLineEdit#GgsSearchEdit:focus { border-color: %(focus)s; }

   /* 标题栏里的搜索框钉在 **22 内容 + 2 边框 = 24 总高**，容器
   `ui.framework.searchbar._BAR_H = 26` ⇒ 容器内上下各 1px（原来 1.5），框本身高 3px。
   ⚠ 特异性：`QFrame#GgsSearchBar QLineEdit#GgsSearchEdit`（两个 ID、两个
   类型）**高于**上面的 `QLineEdit#GgsSearchEdit` ⇒ 只有标题栏那一个吃这条；
   `_NavDialog` 的搜索框不在 `#GgsSearchBar` 里，不受影响。
   ⚠ 与 `ui.framework.searchbar._EDIT_H`（= `_BAR_H` - 2）**必须对得上**：QSS 的
   min/max-height 会覆盖 python 侧的 setMinimumHeight，两处不一致时
   python 那个数字就是假的，边框被裁往往就是这么来的。 */
QFrame#GgsSearchBar QLineEdit#GgsSearchEdit {
  min-height: 22px;
  max-height: 22px;
}
QListWidget#GgsSearchPopup {
  background: %(panel)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
  padding: 4px;
  outline: 0;
}
QListWidget#GgsSearchPopup::item {
  height: 24px;
  padding-left: 8px;
  border-radius: 4px;
  color: %(text)s;
}
QListWidget#GgsSearchPopup::item:selected {
  background: %(accent_soft)s;
  color: %(text)s;
}

/* ---- 量测浮窗（；改自绘圆角） ----
   贴在画布右上角的小卡片：底色与描边由 paintEvent 自绘（圆角外真
   透明，与消息卡片同工艺），QSS 里只保留透明底防止双重绘制。
   结果数字用琥珀色（与画布上的量测线同色），一眼能对上。 */
QFrame#GgsMeasurePanel {
  background: transparent;
  border: none;
}
QLabel#GgsMeasureTitle {
  color: %(text)s;
  font-weight: bold;
}
QToolButton#GgsMeasureClose {
  background: transparent;
  border: none;
  border-radius: 3px;
  color: %(text_dim)s;
  padding: 0 4px;
}
QToolButton#GgsMeasureClose:hover {
  background: #e81123;
  color: #ffffff;
}
QLabel#GgsMeasureResult {
  color: #FFB300;
  font-size: 11pt;
  font-weight: bold;
}
QLabel#GgsMeasureDetail {
  color: %(text_dim)s;
  font-size: 8.5pt;
}
QLabel#GgsMeasureHint {
  color: %(text_disabled)s;
  font-size: 8pt;
}
/* ---- 上下文选项卡（选中图层时出现） ----
   上下文页签与主页签共用同一个 QTabBar#GgsRibbonTabs，没有独立控件。
   标题文字色由代码 setTabTextColor 设为强调色，下方指示线颜色在
   _update_tab_indicator 里按当前页签类型切换（accent / 强调色），
   因此这里无需额外的 CSS 规则。 */

/* ---- 状态栏 ---- */
QStatusBar {
  /* round41u：状态栏直接用窗口背景色；上边框取消 */
  background: %(window)s;
  color: %(text)s;
  border: 0;
  padding: 0 6px;
}
QStatusBar::item { border: 0; }
/* 状态栏分组竖线分隔 = 1px 细线（色走通用 `border`，随主题切换），
   上下留白 5px 内缩、左右各 3px 呼吸位。控件本身 `WA_TransparentForMouseEvents`
   ⇒ 纯装饰。sep 是 QFrame（`statusbar._status_vsep`），不是 QLabel。 */
QFrame#GgsStatusSep {
  border: none;
  border-left: 1px solid %(border)s;
  margin: 5px 3px;
  background: transparent;
}
QStatusBar QLabel {
  color: %(text)s;
  padding: 0 4px;
  background: transparent;
}
/*
   渲染状态**图标格**必须零内边距。上面那条通用 `QStatusBar QLabel` 会命中它
   （它就是状态栏里的一只 QLabel）⇒ 20×20 的格子被 `padding: 0 4px` 挤成
   12px 内容区，铺满格子的位图左右各被切 4px（实测 contentsRect=(4,0,12,20)）。
   对象名选择器（ID）特异度高于通用类型选择器，放哪都赢 ⇒ 别再给这只格子
   加任何 padding / margin。 */
QLabel#GgsRenderStatusIcon {
  padding: 0;
  background: transparent;
}
/* CPU/内存：窄边距，与竖线/坐标贴近 */
QStatusBar QLabel#GgsSysStats {
  padding: 0 2px;
  background: transparent;
}
/* 状态栏坐标标签（简单显示光标 XY，宽度自适应） */
QLabel#GgsCoordsValue {
  background: transparent;
  border: none;
  padding: 0 2px;
  color: %(text)s;
  font-family: Consolas, 'Microsoft YaHei UI';
}
/* 状态栏的**渲染状态文字** ——
   用次要色（text_dim）与坐标那种主文字区分开；空闲时控件直接隐藏
   （见 statusbar._set_render_label），所以不需要"空文字占位"的样式。 */
QLabel#GgsRenderStatus {
  background: transparent;
  border: none;
  padding: 0 4px;
  color: %(text_dim)s;
}
QStatusBar QProgressBar#GgsStatusProgress {
  background: %(input)s;
  border: 1px solid %(border)s;
  border-radius: 4px;
  text-align: center;
  color: %(text)s;
}
QStatusBar QProgressBar#GgsStatusProgress::chunk {
  background: %(accent_soft)s;
}
QStatusBar QToolButton {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: %(text)s;
}
/* 状态栏坐标系按钮（Ggs 小图标样式2：图标 + 文本并排，见 statusbar.py）。
   无底无框、悬停才浮起，与 GgsSmallButtonStyle1 同一口径；给足左右留白。 */
QToolButton#GgsSmallButtonStyle2 {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 5px;
  /* **左右不等宽**是刻意的
     光学补偿，别"顺手改成对称"：
       · 图标位图被压成 14×14（内容区只有 14px 高 ⇒ 等比缩小），落在 18px 宽的
         图标区里 ⇒ 左右各空 2px；
       · 图标字形在 24 视框里从 3.5 起 ⇒ 换到 14px 再内缩 ~2px；
       · 文本墨迹几乎顶到 rect 右端（内缩 ≈ 0）。
     等宽 padding 下 ⇒ 左 1+6+2+2 = **11px**、右 1+6 = **7px**（实测差 4px，
     看着就是"图标离左边远、文字贴右边"）。左压到 2 ⇒ 两侧同为 ~7px。
     ⚠ 与 `standard._tight_icon_text_width(btn, pad_l, pad_r)` 的 2/6 必须同步。 */
  padding: 2px 6px 2px 2px;
  color: %(text)s;
}
QToolButton#GgsSmallButtonStyle2:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
}
QToolButton#GgsSmallButtonStyle2:pressed {
  background: %(border_soft)s;
}
QToolButton#GgsSmallButtonStyle2:disabled {
  background: transparent; border-color: transparent;
}
/* 小按钮
   （勾选）样式2 —— **图标 + 文本并排**的**可切换**小按钮。常态与
   `#GgsSmallButtonStyle2` 同一口径（透明底 + **左右对称**留白）；勾选态给
   accent_soft 底 + **中性**边框（与 `#GgsSmallCheckButtonStyle1:checked` 一致，
   不得用蓝 accent —— 蓝色只留给工程按钮）。 */
QToolButton#GgsSmallCheckButtonStyle2 {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 5px;
  /* 与 `#GgsSmallButtonStyle2` 同款光学补偿（左 2 / 右 6，理由见那里） */
  padding: 2px 6px 2px 2px;
  color: %(text)s;
}
QToolButton#GgsSmallCheckButtonStyle2:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
}
QToolButton#GgsSmallCheckButtonStyle2:pressed {
  background: %(border_soft)s;
}
QToolButton#GgsSmallCheckButtonStyle2:checked {
  background: %(accent_soft)s;
  border-color: %(border)s;
}
QToolButton#GgsSmallCheckButtonStyle2:disabled {
  background: transparent; border-color: transparent;
}
QStatusBar QToolButton:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
}
/* 状态栏比例锁（锁形图标，`GgsStatusScaleLock`）。
   它原来**只有 `:checked` 这一条** QSS ⇒ 常态走平台默认外观（带边框的方按钮），
   在状态栏里既不紧凑、也不像项目里那批"Ggs 小图标按钮"。
   现在常态 / 悬停 / 按下按 `#GgsSmallButtonStyle1`（"标注设置"那批）的**同一口径**写：
   透明底 + 透明边框 + 5px 圆角 + hover 用 panel_hi。
   ⚠ 尺寸（20x20）与图标（14px）由代码 `setFixedSize` / `icons.bind(size=14)`
     钉死，这里**不要**写 width/height（会和代码打架）。
   ⚠ 锁定态保留原来那条**中性**底 —— 不用 `:checked` 默认的 accent_soft
     （偏蓝），与全局"去蓝"的口径一致。 */
QStatusBar QToolButton#GgsStatusScaleLock {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 5px;
  padding: 2px;
}
QStatusBar QToolButton#GgsStatusScaleLock:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
}
QStatusBar QToolButton#GgsStatusScaleLock:pressed {
  background: %(border_soft)s;
}
QStatusBar QToolButton#GgsStatusScaleLock:checked {
  background: %(panel_dn)s;
  border: 1px solid %(border)s;
  color: %(text)s;
}

QLabel#GgsWelcomeTitle {
  font-size: 17pt;
  font-weight: 600;
  color: %(text)s;
}
QLabel#GgsWelcomeSub {
  font-size: 10pt;
  color: %(text_dim)s;
}
QFrame#GgsWelcomeSep {
  background: %(border)s;
  border: 0;
}
QToolButton#GgsWelcomeTile {
  background: %(panel)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
  color: %(text)s;
  font-size: 10pt;
  padding: 4px;
}
QToolButton#GgsWelcomeTile:hover {
  background: %(panel_hi)s;
  border-color: %(focus)s;
}
QToolButton#GgsWelcomeTile:pressed {
  background: %(panel_dn)s;
}
/* ---- 独立起始主页窗口（方案 B：无原生标题栏 + 无左边栏）---- */
QMainWindow#GgsHomeWindow {
  background: %(window)s;
  border: 1px solid %(border)s;
}
QWidget#GgsHomeCentral, QWidget#GgsHomeMain { background: %(window)s; }
/* 主页品牌行（照 ArcGIS Pro）：白色背景与内容区（window 灰）区分，
   左侧 LOGO + 粗体产品名，右侧窗口按钮复用全局 GgsWinBtn/GgsWinClose 样式 */
QFrame#GgsHomeTitleBar { background: %(panel)s; border: 0; }
QLabel#GgsHomeBrandIcon { background: transparent; }
QLabel#GgsHomeBrand { color: %(text)s; font-size: 17pt; font-weight: 700; }
/* 左下角纯图标按钮（选项） */
QToolButton#GgsHomeIconBtn {
  background: transparent; border: 0; border-radius: 6px;
  padding: 5px; min-width: 18px; min-height: 18px;
}
QToolButton#GgsHomeIconBtn:hover { background: %(panel_hi)s; }
QLabel#GgsHomeSection { color: %(text)s; font-size: 11pt; font-weight: 600; }
QToolButton#GgsHomeNewCard {
  background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px;
  color: %(text)s; font-size: 9pt; padding: 4px 2px;
}
QToolButton#GgsHomeNewCard:hover { background: %(panel_hi)s; border-color: %(focus)s; }
QLineEdit#GgsHomeSearch {
  background: %(panel)s; border: 1px solid %(border)s; border-radius: 6px;
  color: %(text)s; padding: 4px 9px;
}
QPushButton#GgsHomeOpenBtn {
  background: %(panel)s; border: 1px solid %(border)s; border-radius: 6px;
  color: %(focus)s; padding: 4px 12px;
}
QPushButton#GgsHomeOpenBtn:hover {
  background: %(panel_hi)s; border-color: %(focus)s;
}
/* 最近工程滚动区 */
QScrollArea#GgsHomeScroll { background: transparent; border: 0; }
QWidget#GgsHomeListHost { background: transparent; }
/* 全宽最近工程行 */
QWidget#GgsHomeRecentRow {
  background: %(panel)s; border: 1px solid %(border)s; border-radius: 6px;
}
QWidget#GgsHomeRecentRow:enabled:hover {
  background: %(panel_hi)s; border-color: %(focus)s;
}
QToolButton#GgsHomeRecentBtn {
  background: transparent; border: 0; color: %(text)s; font-size: 10pt;
  font-weight: 600; text-align: left; padding: 0;
}
QToolButton#GgsHomeRecentBtn:hover { color: %(focus)s; }
QToolButton#GgsHomeRecentBtn:disabled { color: %(text_dim)s; }
QFrame#GgsHomeSep { background: %(border)s; border: 0; }
QLabel#GgsHomeHint { color: %(text_dim)s; font-size: 9pt; padding-top: 2px; }
/* 新建工程对话框（文件路径 + 视图类型图标卡片） */
QLabel#GgsNewProjSection { color: %(text)s; font-size: 9pt; font-weight: 600; }
QFrame#GgsNewProjCard {
  background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px;
  padding: 2px;
}
QFrame#GgsNewProjCard[checked="true"] {
  background: %(panel_hi)s; border: 1px solid %(focus)s;
}
/* 名称恒用正文深色：勾选态不再染 focus 灰（#6e7480 与禁用行 text_dim
   #5c6572 亮度几乎相同，可选行会被看成禁用）；选中感交给卡片描边+底色。 */
QFrame#GgsNewProjCard:disabled { background: %(panel_dn)s; border-color: %(border)s; }
QCheckBox#GgsNewProjCheck { color: %(text)s; }
QCheckBox#GgsNewProjCheck:disabled { color: %(text_dim)s; }
/* ⚠ 伪态必须写在 ::indicator **之后**（::subcontrol:state）。写成
   ":disabled::indicator" 时 Qt 会把声明落到控件本身而非指示器，
   指示器仍吃全局白底（build/_diag_qss_order.py 实测定罪）。 */
QCheckBox#GgsNewProjCheck::indicator:disabled {
  background: %(panel_dn)s; border: 1px solid %(border)s;
}
QLabel#GgsNewProjIcon { background: transparent; border: 0; }
QLabel#GgsNewProjName { color: %(text)s; font-size: 9pt; }
QWidget#GgsNewProjectDialog QLabel:disabled { color: %(text_dim)s; }
/* ---- 任务面板条目（任务 DOCK，ui/panels/task_dock.py）----
   条目卡片 = panel 底 + border 细边；悬停 = panel_hi（与项目列表类控件
   同一悬停口径，用户 #5：此前用 accent 描边与主题不符，已改）；名称
   加粗、阶段/百分比/结果行走弱文字色。终止按钮 = GgsSmallButtonStyle1
   （QSS 在它自己的 objectName 块里，这里不再另写）。 */
QFrame#GgsTaskItem {
  background: %(panel)s;
  border: 1px solid %(border)s;
  border-radius: 6px;
}
QFrame#GgsTaskItem:hover {
  background: %(panel_hi)s;
  border-color: %(border)s;
}
QLabel#GgsTaskName {
  color: %(text)s;
  font-weight: 600;
}
QLabel#GgsTaskStage { color: %(text_dim)s; }
QLabel#GgsTaskPct { color: %(text_dim)s; }
QLabel#GgsTaskResult {
  color: %(text_dim)s;
  font-size: 8pt;
}
QLabel#GgsTaskEmpty { color: %(text_dim)s; }
/* 用户 #5：Ggs 标准进度条（工具对话框就地运行进度区，
   objectName=GgsProgressBar，tool_dialog 底部内联进度行）—— accent
   蓝色块；具体高度由代码 setFixedHeight
   控制。 */
/* 定稿：圆角 **6px** = 项目主流口径（全项目 QSS 里 6px 用了
   59 处、4px 23 处、2px 只有 4 处，按 2px 做出来跟别的控件不是一个路数）；
   无描边，底槽 border_soft；**百分比回到条内居中**（text-align: center，
   中途按 B 方案挪到条外右侧过，那颗小字跟状态文字挤在一起反而更乱）。
   高度由代码 setFixedHeight(14) 控制 —— 与 6px 圆角相称，也装得下条内
   百分比（14 是"装得下字"的下限，再矮字就会被画到条外悬空）。 */
QProgressBar#GgsProgressBar {
  background: %(border_soft)s;
  border: none;
  border-radius: 6px;
  text-align: center;
  color: %(text)s;
}
QProgressBar#GgsProgressBar::chunk {
  background: %(accent)s;
  border-radius: 6px;
}
/* 用户 #5：任务 DOCK 条目里的**小**进度条（12px）—— chunk 同样走
   accent 蓝（原先吃全局 accent_soft，看着发灰，用户 #4）。 */
QFrame#GgsTaskItem QProgressBar {
  background: %(input)s;
  border: 1px solid %(border)s;
  border-radius: 4px;
}
QFrame#GgsTaskItem QProgressBar::chunk {
  background: %(accent)s;
  border-radius: 3px;
}
/* 工具对话框**主行动键**与**进度区**的分态配色。
   配色**一律取自任务 DOCK 那套语义色**（本模块 OK_COLOR / ERR_COLOR，
   见上方注释；已取消 = 当前主题的 text_dim，照 task_dock 的
   `_theme_dim()` —— 那边"已取消"徽标画的就是主题弱文字色，不是自造灰）。
   ⚠ 实现机制：**不靠"动态属性 + 本文件
   [state=...] / [face=...] 规则 + unpolish/polish"**。那条路要
   setProperty 之后 Qt 重算 QSS，而本项目 实测"polish 之后改
   对象名，QSS 不会重算，unpolish/polish 同样无效"（主窗口 dock 页签栏）；
   。改为在**对话框代码里
   直接写控件级样式表**（setStyleSheet：Qt 文档承诺的可靠路径"属性值变了
   就 unset 再 set 一次"，本项目 msgbar 级别色点 / settings 的 lbl_restart
   同款惯例），颜色值由 `progress_face_color(state)` 统一给
   （run=None ⇒ 传空串清掉，回落下面这套 accent 基础规则）。
   ⇒ 本文件只留**基础规则**（= 运行态外观）。 */
"""

_RIBBON_KEYS = ("panel", "panel_hi", "panel_dn", "border", "border_soft",
                "text", "text_dim", "text_disabled", "status_cap", "accent",
                "accent_hi", "accent_soft", "accent_text", "contextual",
                "app_btn", "app_btn_hi", "window", "input", "group_bg",
                "group_hi", "s2_hover", "s2_down", "s2_border", "focus")


def _ribbon_params(theme, key):
    p = {k: theme[k] for k in key}
    p["arrow_down"] = _arrow_url("arrow_down_dark_normal.svg"
                                 if theme is _DARK
                                 else "arrow_down_light_normal.svg")
    p["combo_arrow"] = _arrow_url("combo_arrow_dark.svg"
                                  if theme is _DARK
                                  else "combo_arrow_light.svg")
    return p

_DIALOG_KEYS = ("input", "border", "text", "text_dim", "accent",
                "accent_text", "panel", "panel_hi", "panel_dn", "accent_soft",
                "window", "focus")


_COMBO_PATCH_DARK = """
/* ==== QComboBox fixup (dark, appended by themes.py) ==== */
QComboBox {
  background: #171b22; color: #d9dee6;
  border: 1px solid #333b46; border-radius: 6px;

     /* ① 纵向 padding 1px → **0** —— 它与 `_TEMPLATE` 里那一族输入控件
        （QLineEdit/QSpinBox…**没有**纵向 padding）不是一个口径，多出来的 2px
        正是"下拉框比纯文本框高一截"的来源（纵向不再加 padding 之后，
        两者的"内容高 + 2px 边框"完全同构 ⇒ 在任何字号缩放下都等高）；
     ② `min-height` 1.25em → **24px** —— 24 = 项目自己的单行控件口径
        （搜索框 `ui.framework.searchbar._BAR_H = 24`、`standard._MenuRow` 24、
        多处 `setFixedHeight(24)`）；顶高之后文本框与下拉框都恰好 24。
     ⚠ 显式 `setFixedHeight(22)` 的紧凑控件（功能区小格、工具条下拉）不受影响：
     布局取最小尺寸时**显式最小优先于样式的最小尺寸提示**。 */
  /*
     横向 2px → **6px** —— 与弹层条目的 `QComboBox QAbstractItemView::item
     { padding: 2px 6px }` 对齐（两者各带 1px 边框 ⇒ 文字都在 7px 上）。 */
  /* ① 圆角 4px → **6px** —— 它和
     `QLineEdit / QSpinBox` 是**同一行里的控件**，而那一族是 6px
     （`_TEMPLATE` 里的 `border-radius: 6px`）⇒ 4/6 混排一眼能看出来；
     ② 补 **`max-height: 24px`** —— 模板里那条 `QLineEdit, QComboBox, …`
     虽然给了上限，但这条 patch 在它**之后**、特异性又相同 ⇒ 覆盖时只写了
     min 就等于把上限交给模板；补上之后下拉框与文本框**完全同构**
     （24 内容 + 上下各 1px 边框 = 26 总高），任何字号缩放下都严格等高。 */
  padding: 0px 6px; min-height: 24px; max-height: 24px;
}
/* **悬停不再改边框** —— 原来 `:hover` 与 `:focus` 同一行
   （`#969ca8` 是"输入焦点"的中性灰），于是**只有下拉框**会"鼠标一划就亮边框"，
   同一张表单里的文本框 / 数字框都没有这个反馈 ⇒ 用户看着就是"悬停样式有问题"。
   现在只留 `:focus`（真的拿到焦点）与 `:on`（下拉已展开），与那一族输入控件
   完全一致。 */
QComboBox:focus, QComboBox:on { border: 1px solid #969ca8; }
QComboBox::drop-down {
  subcontrol-origin: padding; subcontrol-position: center right;
  width: 18px; border: none; background: transparent;
}
QComboBox::down-arrow,
QComboBox::down-arrow:on, QComboBox::down-arrow:hover,
QComboBox::down-arrow:focus {
  image: %(arrow)s; width: 10px; height: 10px;
}
QComboBox::indicator { background: transparent; border: none; }
QComboBox QAbstractItemView {
  background: #252b34; color: #d9dee6;
  border: 1px solid #333b46; border-radius: 6px;
  selection-background-color: #3c4758; selection-color: #d9dee6;
  outline: 0; show-decoration-selected: 0;
}
QComboBox QAbstractItemView:hover {
  background: #252b34; color: #d9dee6;
}
QComboBox QAbstractItemView:selected {
  background: #3c4758; color: #d9dee6;
}
QComboBox QAbstractItemView:alternate {
  background: #171b22;
}
QComboBox QAbstractItemView::item {
  height: 22px; padding: 2px 6px; border-radius: 4px;
  background: transparent; color: #d9dee6;
}
QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:selected:active {
  background: #3c4758; color: #d9dee6;
}
/* 原规则把弹层条目的勾选框整框
   隐藏（透明底 + 无边框 = 看不见），导致光谱「图层」多选下拉的复选框不显示。
   给回与图层树同款的 12px 圆角方框 + 主题色对钩贴图（menu_check_* 图标）。 */
QComboBox QAbstractItemView::indicator {
  width: 12px; height: 12px;
  border: 1px solid #4a5563; border-radius: 4px;
  background: #1c2129;
}
/* 边框用图层树同款的**中性** check_border（不蓝）—— 蓝色只留给工程按钮；
   与 QTreeView::indicator:checked 同口径（background=input / border=check_border
   / image=menu_check_* 对钩贴图）。 */
QComboBox QAbstractItemView::indicator:checked {
  border: 1px solid %(check_border)s; background: #1c2129;
  image: %(check)s;
}
/* 日期/时间下拉也统一箭头 */
QDateEdit::down-arrow, QDateTimeEdit::down-arrow,
QDateEdit::down-arrow:on, QDateEdit::down-arrow:hover,
QDateEdit::down-arrow:focus,
QDateTimeEdit::down-arrow:on, QDateTimeEdit::down-arrow:hover,
QDateTimeEdit::down-arrow:focus {
  image: %(arrow)s; width: 10px; height: 10px;
}
""" % {"arrow": _arrow_url("combo_arrow_dark.svg"),
       "check": _arrow_url("menu_check_dark.svg"),
       "check_border": _DARK["check_border"]}


DARK_QSS = (_render(_DARK) + _ARROWS_DARK + _COMBO_PATCH_DARK
            + (_DIALOG_PATCH % {k: _DARK[k] for k in _DIALOG_KEYS})
            + (_RIBBON_PATCH % _ribbon_params(_DARK, _RIBBON_KEYS)))

_THEME_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "resources")
_RC_REGISTERED = False
_RC_MODULE = None


def _register_theme_resources():
    global _RC_REGISTERED, _RC_MODULE
    if _RC_REGISTERED:
        return
    _RC_REGISTERED = True
    try:
        rc_path = os.path.join(_THEME_DIR, "style_rc.py")
        if os.path.isfile(rc_path):
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location("ggis_style_rc", rc_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            _RC_MODULE = mod
    except Exception:
        exc_note("_register_theme_resources @ ggis/common/styling/themes.py:3270")
        pass


_COMBO_PATCH_LIGHT = """

/* ==== QComboBox fixup (appended by themes.py) ==== */
QComboBox {
  background: #ffffff; color: #19232D;
  border: 1px solid #C9CDD0; border-radius: 6px;
  /* —— 纵向 padding 归零、
     高度口径统一到 24px，理由见上面 `_COMBO_PATCH_DARK` 的注释。 */
  /*
     横向 2px → **6px** —— 与弹层条目的 `QComboBox QAbstractItemView::item
     { padding: 2px 6px }` 对齐（两者各带 1px 边框 ⇒ 文字都在 7px 上）。 */
  /* 与深色那份同一处改动（圆角 4 → 6、补 `max-height: 24px`），
     理由见 `_COMBO_PATCH_DARK` 上面那段注释。 */
  padding: 0px 6px; min-height: 24px; max-height: 24px;
}
/* `:hover` 撤掉（只留 `:focus` / `:on`）—— 原来只有下拉框会
   "鼠标一划就亮边框"，与同族的文本框 / 数字框不是一个口径。 */
QComboBox:focus, QComboBox:on { border: 1px solid #6e7480; }
QComboBox::drop-down {
  subcontrol-origin: padding; subcontrol-position: center right;
  width: 18px; border: none; background: transparent;
}
QComboBox::down-arrow,
QComboBox::down-arrow:on, QComboBox::down-arrow:hover,
QComboBox::down-arrow:focus {
  image: %(arrow)s; width: 10px; height: 10px;
}
QComboBox::indicator { background: transparent; border: none; }
QComboBox QAbstractItemView {
  background: #ffffff; color: #19232D;
  border: 1px solid #C9CDD0; border-radius: 6px;
  selection-background-color: #E2E7EE; selection-color: #19232D;
  outline: 0; show-decoration-selected: 0;
}
/* style.qss 里有"视图级 :hover / :selected"规则（整个列表变灰、
   选中字压成浅灰），specificity 比项级高，这里必须一并覆盖 */
QComboBox QAbstractItemView:hover {
  background: #ffffff; color: #19232D;
}
QComboBox QAbstractItemView:selected {
  background: #E2E7EE; color: #19232D;
}
QComboBox QAbstractItemView:alternate {
  background: #ffffff;
}
QComboBox QAbstractItemView::item {
  height: 22px; padding: 2px 6px; border-radius: 4px;
  background: transparent; color: #19232D;
}
QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:selected:active {
  background: #E2E7EE; color: #19232D;
}
/* 原规则把弹层勾选框整框隐藏，
   导致光谱「图层」多选下拉复选框不显示。给回与图层树同款的方框 + 对钩贴图。 */
QComboBox QAbstractItemView::indicator {
  width: 12px; height: 12px;
  border: 1px solid #C9CDD0; border-radius: 4px;
  background: #ffffff;
}
/* 边框用图层树同款的**中性** check_border（不蓝）—— 蓝色只留给工程按钮；
   与 QTreeView::indicator:checked 同口径（background=input / border=check_border
   / image=menu_check_* 对钩贴图）。 */
QComboBox QAbstractItemView::indicator:checked {
  border: 1px solid %(check_border)s; background: #ffffff;
  image: %(check)s;
}
/* 日期/时间下拉也统一箭头（style.qss 里常态用的是 disabled 灰图） */
QDateEdit::down-arrow, QDateTimeEdit::down-arrow,
QDateEdit::down-arrow:on, QDateEdit::down-arrow:hover,
QDateEdit::down-arrow:focus,
QDateTimeEdit::down-arrow:on, QDateTimeEdit::down-arrow:hover,
QDateTimeEdit::down-arrow:focus {
  image: %(arrow)s; width: 10px; height: 10px;
}
/* 数值框上下箭头（原文件用位图 + disabled 图，观感差） */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QAbstractSpinBox::up-arrow,
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover,
QAbstractSpinBox::up-arrow:hover {
  image: %(arrow_up)s; width: 10px; height: 10px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow,
QAbstractSpinBox::down-arrow,
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover,
QAbstractSpinBox::down-arrow:hover {
  image: %(arrow_down)s; width: 10px; height: 10px;
}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:off,
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {
  image: %(arrow_up_disabled)s; width: 10px; height: 10px;
}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:off,
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {
  image: %(arrow_down_disabled)s; width: 10px; height: 10px;
}
""" % {
    "arrow": _arrow_url("combo_arrow_light.svg"),
    "arrow_up": _arrow_url("arrow_up_light_normal.svg"),
    "arrow_down": _arrow_url("arrow_down_light_normal.svg"),
    "arrow_up_disabled": _arrow_url("arrow_up_light_disabled.svg"),
    "arrow_down_disabled": _arrow_url("arrow_down_light_disabled.svg"),
    "check": _arrow_url("menu_check_light.svg"),
    "check_border": _LIGHT["check_border"],
}


LIGHT_QSS = (_render(_LIGHT) + _COMBO_PATCH_LIGHT
             + (_DIALOG_PATCH % {k: _LIGHT[k] for k in _DIALOG_KEYS})
             + (_RIBBON_PATCH % _ribbon_params(_LIGHT, _RIBBON_KEYS)))

QSS_BY_NAME = {
    "dark": DARK_QSS,
    "light": LIGHT_QSS,
}

CANVAS_COLORS = {
    "dark": "#12161c",
    "light": "#ffffff",
}


def _has_cjk(s):
    for ch in s:
        o = ord(ch)
        if (0x3000 <= o <= 0x303F or 0x3040 <= o <= 0x30FF
                or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFFEF):
            return True
    return False

def _is_prose(st):
    if not st:
        return False
    if _has_cjk(st):
        return True
    if st.startswith("*"):
        return True
    if "**" in st:
        return True
    if st.startswith("——"):
        return True
    return False

def _looks_like_qss(ln, st):
    if "{" in ln or "}" in ln:
        return True
    if re.match(r'^\s*[\w-]+\s*:', st):
        return True
    if "#" in st or "::" in st or "," in st:
        return True
    if re.match(r'^\s*[A-Za-z][\w\s]*#', st):
        return True
    return False

def _strip_comments(qss):
    n = len(qss); i = 0; in_c = False; out = []
    while i < n:
        two = qss[i:i+2]
        if not in_c and two == "/*":
            in_c = True; i += 2; continue
        if in_c and two == "*/":
            in_c = False; i += 2; continue
        if not in_c and two == "*/":
            while out and out[-1] != "\n":
                out.pop()
            i += 2; continue
        if in_c:
            i += 1; continue
        out.append(qss[i]); i += 1
    return "".join(out)

def _normalize_qss(qss):
    cleaned = _strip_comments(qss)
    out = []; depth = 0
    for ln in cleaned.split("\n"):
        st = ln.strip()
        depth += ln.count("{") - ln.count("}")
        if ln.count("{") or ln.count("}"):
            out.append(ln); continue
        if not st:
            out.append(ln); continue
        if _is_prose(st):
            continue
        if depth > 0:
            out.append(ln); continue
        if _looks_like_qss(ln, st):
            out.append(ln); continue
        continue
    return "\n".join(out)

_QSS_CACHE = {}

def qss(name):
    if name not in _QSS_CACHE:
        _QSS_CACHE[name] = _normalize_qss(QSS_BY_NAME.get(name, DARK_QSS))
    return _QSS_CACHE[name]


def tree_item_colors(name):
    pal = _theme_of(name)
    return pal["accent_soft"], pal["panel_hi"]


def theme_colors(name):
    return _theme_of(name)

def canvas_color(name):
    return CANVAS_COLORS.get(name, "#12161c")

def palette(name):
    from PySide6.QtGui import QPalette, QColor

    src = _theme_of(name)

    def c(key):
        return QColor(src[key])

    pal = QPalette()
    role = QPalette.ColorRole
    pal.setColor(role.Window, c("window"))
    pal.setColor(role.WindowText, c("text"))
    pal.setColor(role.Base, c("input"))
    pal.setColor(role.AlternateBase, c("panel"))
    pal.setColor(role.ToolTipBase, c("tooltip_bg"))
    pal.setColor(role.ToolTipText, c("tooltip_fg"))
    pal.setColor(role.Text, c("text"))
    pal.setColor(role.Button, c("panel"))
    pal.setColor(role.ButtonText, c("text"))
    pal.setColor(role.BrightText, c("accent_text"))
    pal.setColor(role.Highlight, c("panel_hi"))
    pal.setColor(role.HighlightedText, c("text"))
    pal.setColor(role.Link, c("link"))
    try:
        pal.setColor(role.PlaceholderText, c("text_dim"))
    except Exception:
        exc_note("palette @ ggis/common/styling/themes.py:3562")
        pass
    grp = QPalette.ColorGroup
    for r in (role.WindowText, role.Text, role.ButtonText):
        pal.setColor(grp.Disabled, r, c("text_disabled"))
    return pal


def text_dim(name=None):
    src = _theme_of(name or "dark")
    return src["text_dim"]


def text(name=None):
    src = _theme_of(name or "dark")
    return src["text"]


def accent(name=None):
    src = _theme_of(name or "dark")
    return src["accent"]


def theme_color(key, dark):
    src = _DARK if dark else _LIGHT
    return src[key]


def contextual(name=None):
    src = _theme_of(name or "dark")
    return src["contextual"]
