# -*- coding: utf-8 -*-

from PySide6.QtCore import QTranslator

QT_CONTEXTS = frozenset({
    "QLineEdit", "QLineControl", "QTextEdit", "QPlainTextEdit", "QTextBrowser",
    "QWidgetTextControl", "QTextControl", "QAbstractScrollArea",
    "QAbstractItemView", "QHeaderView", "QTreeView", "QTableView", "QListView",
    "QColumnView", "QFileSystemModel", "QCompleter", "QItemDelegate",
    "QStyledItemDelegate",
    "QFileDialog", "QColorDialog", "QFontDialog", "QInputDialog", "QMessageBox",
    "QErrorMessage", "QProgressDialog", "QWizard", "QWizardPage",
    "QPrintPreviewDialog", "QPageSetupDialog", "QPrintDialog", "QDialog",
    "QDialogButtonBox", "QCommandLinkButton",
    "QDockWidget", "QTabBar", "QTabWidget", "QKeySequenceEdit",
    "QCalendarWidget", "QDateTimeEdit", "QDateEdit", "QTimeEdit",
    "QSpinBox", "QDoubleSpinBox", "QAbstractSpinBox", "QComboBox",
    "QFontComboBox", "QMenu", "QToolBar", "QStatusBar", "QWhatsThis",
    "QPlatformTheme", "QShortcut", "QUndoStack", "QUndoGroup", "QUndoView",
    "QToolBox", "QSplitter", "QMdiArea", "QMdiSubWindow", "QScrollArea",
    "QErrorMessagePrivate",
})

COMMON = {
    "&Undo": "撤销(&U)",
    "&Redo": "重做(&R)",
    "Undo": "撤销",
    "Redo": "重做",
    "Cu&t": "剪切(&T)",
    "Cut": "剪切",
    "&Copy": "复制(&C)",
    "Copy": "复制",
    "&Paste": "粘贴(&P)",
    "Paste": "粘贴",
    "Delete": "删除",
    "&Delete": "删除(&D)",
    "Select All": "全选",
    "&Select All": "全选(&A)",
    "Clear": "清除",
    "&Clear": "清除(&C)",
    "Undo %1": "撤销 %1",
    "Redo %1": "重做 %1",
    "&Insert Unicode control character": "插入 Unicode 控制字符(&I)",
    "Insert Unicode control character": "插入 Unicode 控制字符",

    "OK": "确定", "&OK": "确定(&O)",
    "Cancel": "取消", "&Cancel": "取消(&C)",
    "Apply": "应用", "&Apply": "应用(&A)",
    "Close": "关闭", "&Close": "关闭(&C)",
    "Help": "帮助", "&Help": "帮助(&H)",
    "Open": "打开", "&Open": "打开(&O)",
    "Save": "保存", "&Save": "保存(&S)",
    "Save All": "全部保存", "Save &All": "全部保存(&A)",
    "Yes": "是", "&Yes": "是(&Y)",
    "No": "否", "&No": "否(&N)",
    "Yes to &All": "全部是(&A)", "No to &All": "全部否(&A)",
    "Do &not Save": "不保存(&N)",
    "Discard": "放弃", "&Discard": "放弃(&D)",
    "Abort": "中止", "&Abort": "中止(&A)",
    "Retry": "重试", "&Retry": "重试(&R)",
    "Ignore": "忽略", "&Ignore": "忽略(&I)",
    "Reset": "重置", "&Reset": "重置(&R)",
    "Restore Defaults": "恢复默认值",
    "Done": "完成", "&Done": "完成(&D)",
    "Finish": "完成", "&Finish": "完成(&F)",
    "Print": "打印", "&Print": "打印(&P)",
    "Print…": "打印…", "Print...": "打印...",
    "Preview": "预览", "&Preview": "预览(&P)",
    "Warning": "警告", "Error": "错误", "Information": "信息",
    "Question": "询问", "Critical": "严重",

    "Name": "名称", "Size": "大小", "Type": "类型", "Kind": "种类",
    "Date Modified": "修改日期",
    "Font": "字体", "Color": "颜色", "Value": "值", "Text": "文本",
    "Empty": "空", "None": "无",
}

BY_CONTEXT = {
    "QFileDialog": {
        "Open": "打开", "&Open": "打开(&O)",
        "Save": "保存", "&Save": "保存(&S)",
        "Save As": "另存为",
        "Back": "后退", "Forward": "前进",
        "Parent Directory": "向上一级",
        "Create New Folder": "新建文件夹",
        "List View": "列表视图", "Detail View": "详细信息",
        "&Look in:": "查找范围(&I):", "Look in:": "查找范围:",
        "File &name:": "文件名(&N):", "File name:": "文件名:",
        "Files of type:": "文件类型:", "File &type:": "文件类型(&T):",
        "All Files (*)": "所有文件 (*)",
        "Directory:": "目录:", "Recent Files": "最近的文件",
        "Recent Places": "最近的位置", "Computer": "计算机",
        "My Computer": "我的电脑", "Drive": "驱动器",
    },
    "QColorDialog": {
        "Select Color": "选择颜色",
        "&Basic colors": "基本颜色(&B)", "Basic colors": "基本颜色",
        "&Custom colors": "自定义颜色(&C)", "Custom colors": "自定义颜色",
        "&Pick Screen Color": "选取屏幕颜色(&P)",
        "Pick Screen Color": "选取屏幕颜色",
        "&Add to Custom Colors": "添加到自定义颜色(&A)",
        "Add to Custom Colors": "添加到自定义颜色",
        "Hu&e:": "色调(&E):", "&Sat:": "饱和度(&S):",
        "&Val:": "明度(&V):", "&Red:": "红色(&R):",
        "&Green:": "绿色(&G):", "&Blue:": "蓝色(&B):",
        "Alpha channel:": "Alpha 通道:", "&HTML": "HTML(&H)",
        "Cursor at": "光标位置", "&OK": "确定(&O)", "&Cancel": "取消(&C)",
    },
    "QFontDialog": {
        "Select Font": "选择字体",
        "Font": "字体", "Font style": "字形", "Size": "大小",
        "Effects": "效果", "Strikeout": "删除线", "Underline": "下划线",
        "Writing System": "书写系统", "Sample": "示例",
        "Regular": "常规", "Italic": "倾斜", "Bold": "加粗",
        "Bold Italic": "加粗倾斜", "&OK": "确定(&O)",
        "&Cancel": "取消(&C)",
    },
    "QInputDialog": {
        "Enter a value:": "输入值：", "Enter a comment:": "输入注释：",
        "Enter a label:": "输入标签：", "OK": "确定", "Cancel": "取消",
    },
    "QMessageBox": {
        "Show Details…": "显示详细信息…", "Hide Details…": "隐藏详细信息…",
        "Show Details...": "显示详细信息...",
        "Hide Details...": "隐藏详细信息...",
        "Don't show this message again": "不再显示此消息",
        "OK": "确定", "Cancel": "取消", "Yes": "是", "No": "否",
    },
    "QErrorMessage": {
        "&Show this message again": "再次显示此消息(&S)",
        "Debug Message:": "调试消息：", "Warning": "警告", "OK": "确定",
    },
    "QProgressDialog": {"Cancel": "取消", "Cancel…": "取消…"},
    "QWizard": {
        "< &Back": "< 上一步(&B)", "&Back": "上一步(&B)",
        "&Next >": "下一步(&N) >", "&Next": "下一步(&N)",
        "&Finish": "完成(&F)", "&Cancel": "取消", "&Help": "帮助",
    },
    "QDockWidget": {
        "Float": "浮动", "&Float": "浮动(&F)", "Close": "关闭",
        "&Close": "关闭(&C)", "Move": "移动", "&Move": "移动(&M)",
        "Detach": "分离", "Attach": "附着",
    },
    "QTabBar": {"Close Tab": "关闭标签页", "Close": "关闭"},
    "QKeySequenceEdit": {
        "Clear": "清除", "Press shortcut": "按下快捷键",
        "Shortcut": "快捷键",
    },
    "QCalendarWidget": {"Today": "今天"},
    "QWhatsThis": {"What's This?": "这是什么？", "Close": "关闭"},
    "QPrintPreviewDialog": {
        "Print Preview": "打印预览", "Portrait": "纵向",
        "Landscape": "横向", "Fit Page": "适合页面",
        "Fit Width": "适合宽度", "Pages": "页",
    },
    "QPageSetupDialog": {
        "Page Setup": "页面设置", "Paper": "纸张", "Margins": "页边距",
        "Orientation": "方向", "Left:": "左：", "Right:": "右：",
        "Top:": "上：", "Bottom:": "下：", "millimeters": "毫米",
        "inches": "英寸",
    },
}

QGIS_EXTRA = {
    "Base CRS": "基准 CRS",
    "Origin latitude": "原点纬度",
    "Origin longitude": "原点经度",
    "Base CRS:": "基准 CRS:",
    "Origin latitude:": "原点纬度:",
    "Origin longitude:": "原点经度:",
}


class QtZhTranslator(QTranslator):

    def translate(self, context, source, disambiguation=None, n=-1):
        if not source:
            return None
        table = BY_CONTEXT.get(context)
        if table is not None:
            hit = table.get(source)
            if hit:
                return hit
        if context in QT_CONTEXTS:
            hit = COMMON.get(source)
            if hit:
                return hit
        if context.startswith("Qgs"):
            return QGIS_EXTRA.get(source)
        return None
