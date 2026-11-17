# -*- coding: utf-8 -*-

import os

from PySide6.QtCore import QTranslator
import logging
_log = logging.getLogger("gmagis")

_current = "zh_CN"

_translators = []


def resolve_lang(setting):
    if setting in ("zh_CN", "en_US"):
        return setting
    try:
        from PySide6.QtCore import QLocale

        name = QLocale.system().name()
        return "zh_CN" if name.startswith("zh") else "en_US"
    except Exception:
        _log.exception("silent exception in resolve_lang")
        return "zh_CN"


def init(setting):
    global _current
    _current = resolve_lang(setting)
    return _current


def lang():
    return _current


def is_zh():
    return _current == "zh_CN"


def tr(text):
    if _current == "zh_CN":
        return text
    return _EN.get(text, text)


_EN = {
    "未知视图类型": "unknown view type",
    "布局视图必须指定布局对象": "layout view requires a layout object",
    "视图壳创建失败": "view shell creation failed",
    "视图图层树不可用": "view layer tree unavailable",
    "模型视图必须指定模型": "model view requires a model id",
    "工程中不存在指定的模型": "model not found in project",
    "布局视图正在优化": "Layout view is being optimized",
    "模型管理器视图正在优化": "Model builder view is being optimized",
    "排列": "Arrange",
    "上移一层": "Bring forward",
    "下移一层": "Send backward",
    "左对齐": "Align left",
    "水平居中": "Align center",
    "右对齐": "Align right",
    "顶端对齐": "Align top",
    "垂直居中": "Align middle",
    "底端对齐": "Align bottom",
    "按页面对齐选中元素": "Align the selected item on the page",
    "请先在左侧选中一个元素": "Select an item on the left first",
    "开始": "Home",
    "标注面板初始化失败：{}": "Failed to initialize the labeling panel: {}",
    "插入": "Insert",
    "分辨率": "Resolution",
    "把整页缩放到窗口": "Fit the whole page in the window",
    "重新渲染底图": "Re-render the preview",
    "添加矢量图层 (Ctrl+Shift+V)": "Add Vector Layer (Ctrl+Shift+V)",
    "添加栅格图层 (Ctrl+Shift+R)": "Add Raster Layer (Ctrl+Shift+R)",
    "平移": "Pan",
    "浏览": "Explore",
    "放大": "Zoom In",
    "缩小": "Zoom Out",
    "全图显示": "Zoom Full",
    "识别要素": "Identify Features",
    "框选要素（Ctrl 加选 / Shift 减选）":
        "Select by Rectangle (Ctrl add / Shift subtract)",
    "测量距离": "Measure Distance",
    "测量面积": "Measure Area",
    "测量": "Measure",
    "矩形": "Rectangle",
    "套索": "Lasso",
    "选择要素：左键点选 / 拖动框选；Shift 加选，Ctrl 减选，Ctrl+Shift 交集":
        "Select: click to pick / drag to box-select; "
        "Shift adds, Ctrl subtracts, Ctrl+Shift intersects",
    "多边形选择：逐点点击，双击 / 右键 / 回车闭合；Esc 取消，Backspace 退一点":
        "Polygon select: click points, double-click / right-click / Enter "
        "to close; Esc cancels, Backspace removes the last point",
    "套索选择：按住左键拖出任意形状，松手完成":
        "Lasso select: hold the left button and drag any shape, "
        "release to finish",
    "圆形选择：按下定圆心，拖动定半径":
        "Circle select: press to set the centre, drag to set the radius",
    "折线选择：逐点点击，双击 / 右键 / 回车结束；选中与折线相交的要素":
        "Line select: click points, double-click / right-click / Enter to "
        "finish; selects features crossing the line",
    "矩形框选折点：拖出一个矩形，选中框内的所有折点":
        "Rectangle-select vertices: drag a box to select them all",
    "套索选择折点：按住拖出任意形状，选中圈内的所有折点":
        "Lasso-select vertices: drag any shape to select them all",
    "选择折点：拖出矩形框选，或按住拖出套索圈选":
        "Select vertices: drag a box, or drag a lasso",
    "折点：拖出矩形，框选范围内的折点":
        "Vertices: drag a box to select vertices in range",
    "折点：按住拖出套索，圈选范围内的折点":
        "Vertices: drag a lasso to select vertices inside",
    "已选中 {0} 个折点": "Selected {0} vertices",
    "搜索功能": "Search",
    "单波段伪彩 · {0}": "Single-band pseudocolor · {0}",
    "单波段灰度": "Single-band grayscale",
    "单波段伪彩色": "Single-band pseudocolor",
    "多波段合成（RGB）": "Multiband composite (RGB)",
    "最大 {0}": "Max {0}",
    "最小 {0}": "Min {0}",
    "显示正常消息（数据加载成功等）":
        "Show normal messages (e.g. data loaded)",
    "显示成功消息（操作完成）": "Show success messages",
    "显示警告消息": "Show warning messages",
    "显示错误消息": "Show error messages",
    "只影响地图上方的消息条；任何级别的消息一律写入日志面板，不会丢。":
        "This affects the message bar above the map only; messages of every "
        "level are always written to the Log panel.",
    "临时矢量格式": "Temporary vector format",
    "临时栅格格式": "Temporary raster format",
    "临时文件": "Temporary files",
    "关联文件": "Related files",
    "「{0}」有未保存的编辑，请先点「保存」或用「撤销」回退":
        "“{0}” has unsaved edits; save first or undo to roll back",
    "瓦片尺寸": "Tile Size",
    "缩放层级": "Zoom Levels",
    "切片方案": "Tiling Scheme",
    "行号约定": "Row Numbering",
    "版权信息": "Attribution",
    "（未命名）": "(Unnamed)",
    "TMS（{ -y }，自下而上）": "TMS ({ -y }, bottom-up)",
    "XYZ（自上而下）": "XYZ (top-down)",
    "在线瓦片图层的坐标系由服务切片方案决定"
    "（常见为 EPSG:3857 Web 墨卡托或 EPSG:4326），"
    "不能修改。":
        "A tile layer's CRS is fixed by the service's tiling scheme "
        "(usually EPSG:3857 Web Mercator or EPSG:4326) and cannot be "
        "changed.",
    "瓦片服务按固定的金字塔切片发布影像，坐标换算在渲染时"
    "实时完成；需要其他坐标系的底图时，请添加对应切片方案"
    "的服务，或使用「导出」把当前视野另存为栅格。":
        "Tile services publish pre-cut pyramid imagery; reprojection "
        "happens on the fly while rendering. For a basemap in another "
        "CRS, add a service with that tiling scheme, or export the "
        "current view as a raster.",
    "导出瓦片图层 — {0}": "Export Tile Layer — {0}",
    "自定义范围": "Custom Extent",
    "瓦片层级": "Tile Zoom Level",
    "层级": "Zoom level",
    "最小经度": "Min Longitude",
    "最小纬度": "Min Latitude",
    "最大经度": "Max Longitude",
    "最大纬度": "Max Latitude",
    "请先选择一个瓦片图层": "Select a tile layer first",
    "瓦片图层没有有效的数据源": "The tile layer has no valid data source",
    "已导出瓦片图层 → {0}": "Exported tile layer → {0}",
    "导出瓦片失败：{0}": "Tile export failed: {0}",
    "导出瓦片：{0} → {1}": "Tile export: {0} → {1}",
    "请先确定导出范围": "Set the export extent first",
    "瓦片数量或尺寸超出上限，请缩小范围或降低层级":
        "Too many tiles or too large; shrink the extent or lower the zoom",

    "预计下载 {0} 张瓦片，拼接成 {1} × {2} 像元（当前视图约第 {3} 级）":
        "About to download {0} tiles into a {1} × {2} px mosaic "
        "(current view ≈ zoom {3})",
    "米/像素": "m/pixel",
    "范围（当前：{0}）": "Extent (current: {0})",
    "分辨率 ≈ {0} 米/像素": "Resolution ≈ {0} m/pixel",
    "预计 {0} 张瓦片 / {1} × {2} 像元 —— 超出上限，请缩小范围或降低层级":
        "Estimated {0} tiles / {1} × {2} px — exceeds limit; shrink "
        "extent or lower zoom level",
    "JPEG 不支持透明通道，背景将写为不透明":
        "JPEG has no alpha channel; background will be opaque",
    "BMP 不支持透明通道，背景将写为不透明":
        "BMP has no alpha channel; background will be opaque",
    "该格式只输出 8 位整型（瓦片本就是 8 位，无影响）":
        "This format is 8-bit only (tiles are already 8-bit, no effect)",
    "自定义范围无效（请检查经纬度）":
        "Invalid custom extent (check the long/lat values)",
    "正在下载瓦片… ({0}/{1})": "Downloading tiles… ({0}/{1})",
    "打开属性表": "Open Attribute Table",
    "基础工具箱": "Basic Toolbox",
    "周长 {}": "Perimeter {}",
    "周长：": "Perimeter: ",
    "原始坐标（每行一个：X, Y）：":
        "Source coordinates (one per line: X, Y):",
    "转换结果（X, Y）：": "Converted results (X, Y):",
    "设置地图坐标系…": "Set Map CRS…",
    "设置…": "Settings…",
    "收藏夹": "Favorites",
    "添加到收藏夹": "Add to Favorites",
    "添加到收藏夹…": "Add to Favorites…",
    "（也可以右键任意文件夹加入）":
        "(or right-click any folder to add it)",
    "关于": "About",
    "光标 --, --": "Cursor --, --",
    "比例尺 --": "Scale --",
    "图层 0": "Layers 0",
    "光标 {}, --": "Cursor {}, --",
    "光标 {}, {}": "Cursor {}, {}",
    "比例尺 1:0": "Scale 1:0",
    "图层 {}": "Layers {}",
    "图层：": "Layer: ",
    "日志": "Log",
    "任务": "Tasks",
    "暂无任务": "No tasks",
    "清除已完成": "Clear Finished",
    "显示窗口": "Show Window",
    "终止任务": "Stop Task",
    "终止": "Stop",
    "清除此条目": "Remove Entry",
    "已完成 · 用时 {0} 秒": "Finished · {0} s",
    "失败：{0}": "Failed: {0}",
    "运行中 {0}": "Running {0}",
    "已结束 {0}": "Finished {0}",
    "失败 {0}": "Failed {0}",
    "任务面板初始化失败：{}": "Task panel init failed: {}",
    "双击显示工具窗口": "Double-click to show the tool window",
    "加载中": "Loading",
    "加载中…": "Loading…",
    "结果：{0}": "Result: {0}",
    "任务已取消，未产生输出": "Task cancelled; no output produced",
    "运行完成": "Finished",
    "完成（有警告）": "Finished (with warnings)",
    "警告：{0}": "Warning: {0}",
    "全部任务": "All Tasks",
    "已完成": "Completed",
    "有警告": "With Warnings",
    "失败": "Failed",
    "无匹配任务": "No matching tasks",
    "只显示指定状态的任务": "Show only tasks of the selected status",
    "样例演示": "Sample Demo",
    "打开任务演示样例窗口": "Open the task demo sample window",
    "任务面板演示样例": "Task Panel Demo",
    "运行模式": "Run Mode",
    "模式": "Mode",
    "正常完成（约 1 秒）": "Finish normally (~1 s)",
    "完成但带警告": "Finish with a warning",
    "较慢（约 5 秒，期间可到任务面板点终止 → 查看已取消样式）":
        "Slower (~5 s; click Stop in the task panel to see the cancelled style)",
    "必定失败": "Always fails",
    "演示步骤 {0}/{1}": "Demo step {0}/{1}",
    "演示任务失败（故意注入的错误）": "Demo task failed (deliberate error)",
    "演示任务第 {0} 次运行完成": "Demo run #{0} finished",
    "演示：结果置信度较低，请人工复核":
        "Demo: low confidence result, please review manually",
    "消息": "Messages",
    "展开全部": "Expand All",
    "移除选中图层": "Remove Selected Layers",
    "折叠全部": "Collapse All",
    "新建组…": "New Group…",
    "缩放到图层(Z)": "Zoom to Layer(s)(Z)",
    "缩放到所选择要素(S)": "Zoom to Selection(S)",
    "显示要素数量(C)": "Show Feature Count(C)",
    "重命名图层(N)": "Rename Layer(N)",
    "移除(R)": "Remove(R)",
    "图层顺序": "Layer Order",
    "移到顶层(T)": "Move to Top(T)",
    "上移一层(U)": "Move Up One(U)",
    "下移一层(D)": "Move Down One(D)",
    "移到底层(B)": "Move to Bottom(B)",
    "编辑要素": "Edit Features",
    "保存编辑": "Save Edits",
    "放弃编辑": "Discard Edits",
    "过滤要素(F)": "Filter Features(F)",
    "打开属性表(A)": "Open Attribute Table(A)",
    "符号系统(Y)": "Symbology(Y)",
    "显示标注(S)": "Show Labels(S)",
    "标注属性(L)": "Labeling Properties(L)",
    "导出": "Export",
    "图层属性(P)": "Layer Properties(P)",
    "设置图层坐标系…": "Set Layer CRS…",
    "GeoPackage…": "GeoPackage…",
    "ESRI Shapefile…": "ESRI Shapefile…",
    "GeoJSON…": "GeoJSON…",
    "CSV…": "CSV…",
    "KML…": "KML…",
    "设置": "Settings",
    "外观": "Appearance",
    "通用": "General",
    "主题": "Theme",
    "深色": "Dark",
    "浅色": "Light",
    "界面字体大小": "UI Font Size",
    "小": "Small",
    "中": "Medium",
    "大": "Large",
    "画布背景色": "Canvas Background",
    "跟随主题": "Follow Theme",
    "语言": "Language",
    "跟随系统": "System Default",
    "简体中文": "简体中文",
    "English": "English",
    "确定": "OK",
    "取消": "Cancel",
    "恢复默认": "Reset Defaults",
    "语言更改在重启后完全生效；右键菜单立即生效。":
        "Language change takes full effect after restart; "
        "the layer context menu updates immediately.",
    "工程": "Project",
    "编辑": "Edit",
    "视图": "View",
    "书签": "Bookmarks",
    "处理": "Processing",
    "帮助": "Help",
    "面板": "Panels",
    "新建工程": "New Project",
    "打开工程…": "Open Project…",
    "保存工程": "Save Project",
    "工程另存为…": "Save Project As…",
    "导出画布快照…": "Export Canvas Snapshot…",
    "移动要素（拖动落位）": "Move Feature(s) (drag & drop)",
    "移动": "Move",
    "保存": "Save",
    "回滚编辑": "Revert Edits",
    "创建": "Create",
    "全屏模式": "Full Screen Mode",
    "过滤要素…": "Filter Features…",
    "过滤要素": "Filter Features",
    "新建组": "New Group",
    "新建书签…": "New Bookmark…",
    "（暂无书签）": "(no bookmarks yet)",
    "识别结果": "Identify Results",
    "鹰眼图": "Overview",
    "暂无图层，无法生成鹰眼图": "No layers yet — cannot build the overview",
    "鹰眼图已关闭": "Overview is turned off",
    "图层样式": "Layer Styling",
    "浏览器": "Browser",
    "编辑工具栏": "Edit Toolbar",
    "主工具栏": "Main Toolbar",
    "确认": "Confirm",
    "当前工程未保存，继续将丢弃其中的图层。确定继续？":
        "The current project has unsaved layers and they will be lost. Continue?",
    "已新建空工程。": "New empty project created.",
    "保存工程失败": "Save Project",
    "读取工程失败：{}": "Failed to read project: {}",
    "工程已打开：{}（{} 个图层）": "Project opened: {} ({} layers)",
    "保存失败：{}": "Failed to save: {}",
    "工程已保存：{}": "Project saved: {}",
    "快照已保存：{}": "Snapshot saved: {}",
    "请先选中一个矢量图层": "Select a vector layer first",
    "请先开始编辑再编辑折点": "Start editing before editing vertices",
    "没有选中的折点": "No vertices selected",
    "已移动 {} 个折点": "{} vertex(es) moved",
    "已删除 {} 个折点": "{} vertex(es) deleted",
    "折点数不足：删除被拒绝（线至少 2 点 / 面至少 3 点）":
        "Not enough vertices: delete rejected (line >= 2 / polygon >= 3)",
    "编辑折点：单击选中要素，拖动折点移动（多选一起动）、双击线段加点、Delete 删除所选折点":
        "Edit vertices: click to select a feature, drag to move (selection moves together), double-click a segment to add, Delete removes selection",
    "选择折点：单击折点选中（Ctrl 加选 / 减选）、空白处拖框多选、Esc 清除":
        "Select vertices: click to select (Ctrl adds/toggles), drag a box for multiple, Esc clears",
    "添加折点：在要素线段上单击插入新折点":
        "Add vertex: click on a segment to insert a new vertex",
    "移动折点：按住任一所选折点拖动，整组一起移动":
        "Move vertices: drag any selected vertex to move the whole selection",
    "已进入编辑状态：{}": "Editing started: {}",
    "已保存 {} 个图层的编辑": "Saved edits in {} layer(s)",
    "已回滚所有未保存的编辑": "All unsaved edits reverted",
    "没有选中的要素": "No features selected",
    "确定删除“{}”中选中的 {} 个要素？":
        "Delete {} selected feature(s) from \"{}\"?",
    "已删除 {} 个要素（记得保存编辑）":
        "Deleted {} feature(s) (remember to save edits)",
    "删除要素": "Delete Features",
    "剪切要素": "Cut Features",
    "图层「{0}」有未保存的编辑。\n\n{1}之前要先保存这些改动吗？":
        "Layer \"{0}\" has unsaved edits.\n\n"
        "Save them before {1}?",
    "编辑状态": "Editing",
    "“{}”有未保存的修改。保存并退出编辑？":
        "\"{}\" has unsaved changes. Save and stop editing?",
    "已保存编辑": "Edits saved",
    "已回滚编辑": "Edits reverted",
    "已添加要素 #{} 到“{}”": "Added feature #{} to \"{}\"",
    "添加要素失败": "Failed to add feature",
    "已自动进入编辑状态：{}": "Editing started automatically: {}",
    "已移动 {} 个要素": "Moved {} feature(s)",
    "编辑折点": "Vertex Editor",
    "分割": "Split",
    "修整": "Reshape",
    "打断": "Break",
    "概化": "Simplify",
    "对齐线至少需要两个点": "Align line needs at least two points",
    "请先选择要对齐的要素": "Select features to align first",
    "已对齐 {} 个要素（记得保存编辑）":
        "Aligned {} feature(s) (remember to save edits)",
    "对齐失败（要素质心已在线上或几何无效）":
        "Align failed (centroids already on the line or invalid geometry)",
    "打断线至少需要两个点": "Break line needs at least two points",
    "打断目前仅支持线图层": "Break currently supports line layers only",
    "已打断 {} 个要素（记得保存编辑）":
        "Broke {} feature(s) (remember to save edits)",
    "打断失败（打断线需与线要素相交）":
        "Break failed (the break line must cross a line feature)",
    "请先选中要素再概化": "Select features to simplify first",
    "概化容差（图层单位）：": "Simplify tolerance (layer units):",
    "已概化 {} 个要素（记得保存编辑）":
        "Simplified {} feature(s) (remember to save edits)",
    "概化失败（容差过小或几何无效）":
        "Simplify failed (tolerance too small or invalid geometry)",
    "融合": "Merge",
    "合并": "Combine",
    "拆分": "Split Multipart",
    "点": "Point",
    "线": "Line",
    "面": "Polygon",
    "多部件": "Multi",
    "集合": "Geometry collection",
    "新建形状": "New Shape",
    "新建": "New",
    "形状文件": "Shapefile",
    "Esri 文件地理数据库": "Esri file geodatabase",
    "文件": "Files",
    "数据库": "Database",
    "请先在图层树中选择一个图层": "Select a layer in the layer tree first",
    "已复制图层：{}": "Layer copied: {}",
    "已剪切图层：{}（粘贴可恢复）": "Layer cut: {} (paste to restore)",
    "图层正在编辑，请先停止编辑后再剪切":
        "Layer is being edited; stop editing before cutting",
    "图层剪贴板为空：先复制或剪切一个图层":
        "Layer clipboard is empty: copy or cut a layer first",
    "已粘贴图层：{}": "Layer pasted: {}",
    "粘贴失败：无法按源重建图层": "Paste failed: cannot rebuild layer from source",
    "已移动折点": "Vertex moved",
    "移动折点失败": "Failed to move vertex",
    "已添加折点": "Vertex added",
    "已删除折点": "Vertex deleted",
    "删除折点失败": "Failed to delete vertex",
    "分割线至少需要两个点": "Split line needs at least two points",
    "修整线至少需要两个点": "Reshape line needs at least two points",
    "要素已沿分割线切开（记得保存编辑）":
        "Features split along the line (remember to save edits)",
    "分割失败（分割线需穿过要素）":
        "Split failed (the line must cross a feature)",
    "已修整 {} 个要素（记得保存编辑）":
        "Reshaped {} feature(s) (remember to save edits)",
    "修整失败（修整线需穿过要素）":
        "Reshape failed (the line must cross a feature)",
    "修整目前仅支持多边形图层":
        "Reshape currently supports polygon layers only",
    "融合至少需要选中两个要素":
        "Select at least two features to merge",
    "融合失败（几何并集为空）":
        "Merge failed (union geometry is empty)",
    "融合失败": "Merge failed",
    "已融合 {} 个要素（记得保存编辑）":
        "Merged {} feature(s) (remember to save edits)",
    "已拆分出 {} 个要素（记得保存编辑）":
        "Split into {} feature(s) (remember to save edits)",
    "所选要素中没有多部件要素":
        "No multipart features in the selection",
    "请至少选择两个要素": "Select at least two features",
    "所选要素中没有可合并的几何":
        "No combinable geometries in the selection",
    "已合并为 1 个多部件要素（记得保存编辑）":
        "Combined into 1 multipart feature (remember to save edits)",
    "已添加书签：{}": "Bookmark added: {}",
    "书签名称:": "Bookmark name:",
    "书签 {}": "Bookmark {}",
    "已定位到 {:.4f}, {:.4f}": "Zoomed to {:.4f}, {:.4f}",
    "坐标跳转失败：{}": "Failed to go to coordinates: {}",
    "载入图层：{}": "Layer loaded: {}",
    "识别：未命中要素": "Identify: no features found",
    "请先在图层面板选中一个矢量图层":
        "Select a vector layer in the Layers panel first",
    "选中一个矢量图层后可在此编辑其样式。":
        "Select a vector layer to edit its style here.",
    "栅格样式请使用图层属性对话框。":
        "Use the layer properties dialog for raster styling.",
    "该图层不支持样式编辑。": "This layer does not support style editing.",
    "工程书签": "Project bookmarks",
    "用户书签": "User bookmarks",
    "透明度": "Opacity",
    "填充颜色…": "Fill Color…",
    "边框/线条颜色…": "Stroke / Line Color…",
    "标注设置…(L)": "Label Settings…(L)",
    "灰度拉伸": "Contrast Enhancement",
    "无拉伸(O)": "No Stretch(O)",
    "最小-最大拉伸(M)": "Min-Max Stretch(M)",
    "裁剪 2% ~ 98%(P)": "Clip 2% ~ 98%(P)",
    "波段组合…": "Band Combination…",
    "统计信息…": "Statistics…",
    "PNG 图片…": "PNG Image…",
    "JPEG 图片…": "JPEG Image…",
    "标注设置 — {}": "Label Settings — {}",
    "(无 — 关闭标注)": "(none — disable labels)",
    "标注字段": "Label Field",
    "字号 (pt)": "Font Size (pt)",
    "加粗": "Bold",
    "字体颜色": "Font Color",
    "标注样式": "Label Style",
    "波段组合 — {}": "Band Combination — {}",
    "红色波段(R)": "Red Band(R)",
    "绿色波段(G)": "Green Band(G)",
    "蓝色波段(B)": "Blue Band(B)",
    "(无)": "(none)",
    "RGB 波段映射": "RGB Band Mapping",
    "统计信息 — {}": "Statistics — {}",
    "波段": "Band",
    "最小值": "Minimum",
    "最大值": "Maximum",
    "均值": "Mean",
    "标准差": "Std Dev",
    "极差": "Range",
    "空间分析": "Spatial Analysis",
    "空间分析…": "Spatial Analysis…",
    "矢量空间分析：缓冲 / 相交 / 联合 / 擦除 / 裁剪 / 融合":
        "Vector analysis: buffer / intersect / union / erase / clip / dissolve",
    "算法": "Algorithm",
    "（算法）": "(algorithm)",
    "操作": "Operation",
    "输入": "Input",

    "从文件…": "From file…",
    "读不出这个矢量文件：{0}": "Cannot read this vector file: {0}",
    "输出格式": "Output format",
    "创建选项": "Creation options",
    "空间索引": "Spatial index",
    "标识符": "Identifier",
    "字符编码": "Encoding",
    "严格 RFC 7946（WGS84）": "Strict RFC 7946 (WGS84)",
    "保留原生属性类型": "Keep native field types",
    "GML 版本": "GML version",
    "名称字段": "Name field",
    "内置样式": "Built-in styles",
    "我的样式": "My styles",
    "大图标": "Large icons",
    "列表": "List",
    "预设的显示方式": "How presets are displayed",
    "{0}（{1}）": "{0} ({1})",
    "搜索名称…": "Search name…",
    "（另有 {0} 个内存图层未写盘）": "({0} in-memory layer(s) were not written to disk)",
    "编辑已收下，但未写盘：{0}（内存图层，要落盘请用「另存为 / 导出」）":
        "Edits kept in memory only, NOT written to disk: {0} "
        "(in-memory layer(s) - use Save As / Export to persist)",
    "已收下编辑（内存图层，未写盘）：{0}":
        "Edits kept in memory (NOT written to disk): {0}",
    "写入被取消": "Write cancelled",
    "保存被取消：{0}": "Save cancelled: {0}",
    "删除：先单击要素选中（Ctrl 加选），再点工具条上的「删除」按钮":
        "Delete: click a feature to select it (Ctrl to add), then click the "
        "Delete button on the toolbar",
    "折点：单击折点即删除（双击 = 确认）":
        "Vertex: click a vertex to delete it (double-click = confirm)",
    "折点编辑：拖动折点调整（原要素保留）→ 双击确认 → Esc 取消":
        "Vertex edit: drag a vertex to adjust (the original feature is kept) "
        "-> double-click to confirm -> Esc to cancel",
    "没有待确认的折点编辑": "No pending vertex edits to confirm",
    "已删除 {0} 个要素": "Deleted {0} feature(s)",
    "已确认 {0} 个要素的折点编辑（原要素已替换）":
        "Confirmed vertex edits for {0} feature(s) (originals replaced)",
    "当前在途的渲染工作": "Render jobs currently in flight",
    "表达式，例如：value >= 500 AND category = 'B'":
        "Expression, e.g. value >= 500 AND category = 'B'",
    "取样值（前 100 个唯一值）": "Sample values (first 100 unique values)",
    "标准差拉伸的范围 = 均值 ± 该倍数 × 标准差":
        "Std-dev stretch range = mean \u00b1 (factor \u00d7 std dev)",
    "计算唯一值": "Compute unique values",
    "分类 / 分级数超过 {0} 个以后，符号与图例的生成、以及每次重绘都会明显变慢；"
    "分位数 / 自然断点这类算法在类数很多时会额外耗时。\n\n"
    "可以继续使用；如果只是想要好看的渐变色，建议改用「拉伸」。\n\n"
    "（这条提醒的开关与阈值，可在「选项 → 渲染」里调整。）":
        "Beyond {0} classes, symbol/legend generation and every repaint "
        "become noticeably slower; algorithms such as quantile / natural "
        "breaks also cost extra time at high class counts.\n\n"
        "You can keep using it; if you only want a nice gradient, consider "
        "switching to Stretch.\n\n"
        "(This reminder\u2019s toggle and threshold live under "
        "Options -> Rendering.)",
    "填充样式": "Fill style",
    "线端样式": "Line cap",
    "拐角样式": "Line join",
    "短虚线": "Short dash",
    "长虚线": "Long dash",
    "十字线": "Cross",
    "交叉线": "Diagonal cross",

    "虚线图案（线宽倍数）": "Dash pattern (× line width)",
    "如 4, 2, 1, 2 —— 画/空成对，单位=线宽倍数":
        "e.g. 4, 2, 1, 2 - dash/gap pairs, in multiples of line width",
    "尖角": "Miter",
    "斜角": "Bevel",
    "叠加图层": "Overlay Layer",
    "复制这 {0} 项": "Copy {0} items",
    "剪贴这 {0} 项": "Cut {0} items",
    "在组内新建组": "New Group Inside",
    "粘贴到组内": "Paste Into Group",
    "已复制 {0} 项到剪贴板": "Copied {0} item(s) to clipboard",
    "已剪切 {0} 个图层（按 Ctrl+V 可恢复）":
        "Cut {0} layer(s) (press Ctrl+V to restore)",
    "已剪切（按 Ctrl+V 可恢复）": "Cut (press Ctrl+V to restore)",
    "已粘贴 {0} 个图层": "Pasted {0} layer(s)",
    "这些条目不包含可复制的图层": "These items contain no copyable layer",
    "组": "Group",
    "叠加图层在画布上连入：把另一个图层的输出口，连到这个节点的第二个输入口。":
        "Wire the overlay layer on the canvas: connect another layer's output "
        "port to this node's second input port.",
    "（未连接 —— 把它连到本节点的第二个输入口）":
        "(Not connected — wire it into this node's second input port)",
    "（未连接）": "(Not connected)",
    "（图层已不在工程中）": "(Layer is no longer in the project)",
    "仅处理选中要素": "Selected features only",
    "参数": "Parameters",
    "缓冲距离": "Buffer distance",
    "地图单位": "Map units",
    "米（按椭球换算）": "Meters (geodesic)",
    "圆弧分段（每 1/4 圆）": "Segments per quarter circle",
    "线端头": "Cap style",
    "拐角": "Join style",
    "圆头": "Round", "平头": "Flat", "方头": "Square",
    "圆角": "Round", "斜接": "Mitre", "斜切": "Bevel",
    "合并为一个要素（融合）": "Merge into a single feature (dissolve)",
    "融合字段（分组）": "Dissolve field (group by)",
    "质心落在面内（内部点）": "Centroid inside polygon (point on surface)",
    "输出": "Output",
    "正在加载运行时…": "Loading runtime…",
    "正在注册数据提供者…": "Registering data providers…",
    "正在读取工程…": "Reading project…",
    "正在创建工程…": "Creating project…",
    "正在创建地图视图…": "Creating map views…",
    "正在创建视图…": "Creating views…",
    "正在装载图层…": "Loading layers…",
    "正在装载视图…": "Loading views…",
    "正在创建面板与功能区…": "Creating panels and the ribbon…",
    "正在加载处理框架…": "Loading the processing framework…",
    "正在构建界面…": "Building the interface…",
    "正在准备动作与图标…": "Preparing actions and icons…",

    "正在创建面板…": "Creating panels…",
    "正在构建功能区…": "Building the ribbon…",
    "正在应用设置…": "Applying settings…",
    "就绪": "Ready",
    "专业桌面 GIS 平台 · 空间数据管理与分析":
        "Professional Desktop GIS · Spatial Data Management & Analysis",
    "正在运行": "Running",
    "准备中…": "Preparing…",
    "统计中…": "Calculating…",
    "统计": "Statistics",
    "筛选中…": "Filtering…",
    "出图中…": "Exporting…",
    "正在导出栅格…": "Exporting raster…",
    "计算中…": "Calculating…",
    "按位置选择失败：{0}": "Select by location failed: {0}",
    "正在取消…": "Cancelling…",
    "读取输入图层": "Reading input layer",
    "计算几何": "Computing geometry",
    "整理输出": "Preparing output",
    "批处理完成": "Batch finished",
    "（内存，未写盘）": "(in memory, not written to disk)",
    "「{0}」的编辑已应用（内存图层，未写盘）":
        "Edits to “{0}” applied (in-memory layer, not written to disk)",
    "已新建 {0} 图层，在地图上单击开始绘制（内存图层，无需保存到文件）":
        "Created {0} layer; click on the map to start drawing "
        "(in-memory layer, no file needed)",
    "写入内存": "Write to memory",
    "将结果加入到地图": "Add result to map",
    "写入文件": "Write to file",
    "视图：{0} 个（{1}）": "Views: {0} ({1})",
    "视图：0 个": "Views: 0",
    "最近保存：{0}": "Last saved: {0}",
    "尚未保存": "Not saved yet",
    "图层自身范围": "Layer extent",
    "度量单位": "Measurement unit",
    "度量字段": "Measure fields",
    "空间关系字段": "Spatial relation fields",
    "要计算的字段": "Fields to compute",
    "请至少勾选一个要计算的字段":
        "Check at least one field to compute",
    "周长": "Perimeter",
    "顶点数": "Vertex count",
    "部件数": "Part count",
    "环数": "Ring count",
    "最小间隙": "Minimum clearance",
    "圆度": "Circularity",
    "内含于": "Within",
    "相接": "Touches",
    "叠置": "Overlaps",
    "穿越": "Crosses",
    "分离": "Disjoint",
    "相等": "Equals",
    "覆盖": "Covers",
    "被覆盖": "Covered by",
    "最近距离": "Nearest distance",
    "裁剪栅格": "Clip raster",
    "裁剪掩模（矢量，可选）": "Clip mask (vector, optional)",
    "请先设置裁剪范围或选择掩模图层":
        "Set a clip extent or pick a mask layer first",
    "影像镶嵌": "Mosaic",
    "波段合成": "Stack bands",
    "镶嵌方式": "Mosaic method",
    "先到先得（按勾选顺序）": "First comes first (by check order)",
    "后层覆盖": "Later layers overwrite",
    "输入栅格（勾选多个）": "Input rasters (check one or more)",
    "请至少勾选一个输入栅格图层":
        "Check at least one input raster layer",
    "几何不变，一趟加多列度量字段：面积 / 长度 / 周长 / 顶点数 / 部件数 / 环数 / 最小间隙 / 圆度，按需勾选（可多选）。":
        "Keep geometries and add several measure columns in one pass: area / "
        "length / perimeter / vertex count / part count / ring count / "
        "minimum clearance / circularity — check what you need.",
    "几何不变，一趟加多列与叠加层的关系字段：相交 / 包含 / 内含于 / 相接 / 叠置 / 穿越 / 分离 / 相等 / 覆盖 / 被覆盖 / 距离内 / 最近距离，按需勾选（可多选）。":
        "Keep geometries and add several relation columns against the overlay "
        "layer in one pass: intersects / contains / within / touches / "
        "overlaps / crosses / disjoint / equals / covers / covered by / "
        "within distance / nearest distance — check what you need.",
    "把栅格裁出来：给了矢量掩模按掩模裁（范围外记 nodata），否则按所选范围裁（图层自身范围 / 自定义矩形）。":
        "Clip the raster: with a vector mask, clip by mask (outside = nodata); "
        "otherwise clip to the chosen extent (layer extent / custom rectangle).",
    "把多个栅格拼成一幅：网格取范围并集 + 最细分辨率，逐波段重采样后按所选方式合并（列表勾选顺序即图层处理顺序）。":
        "Mosaic rasters into one: union of extents at the finest resolution, "
        "reproject band by band and merge with the chosen method (check order "
        "= layer order).",
    "把多个栅格的波段按勾选顺序堆成一个多波段影像（网格对齐与影像镶嵌同口径：范围并集 + 最细分辨率）。":
        "Stack bands of several rasters into one multi-band image (grid "
        "alignment as mosaic: union of extents at the finest resolution).",
    "结果图层名": "Result layer name",
    "留空自动命名": "leave blank to auto-name",
    "留空创建内存工程": "Leave empty for an in-memory project",
    "输出文件": "Output file",
    "选择输出文件…": "Choose an output file…",
    "浏览…": "Browse…",
    "加入队列": "Add to queue",
    "（不分组，全部融合）": "(no grouping — dissolve all)",
    "运行": "Run",
    "保存分析结果": "Save analysis result",
    "搜索算法…": "Search algorithms…",
    "运行算法…": "Run algorithm…",
    "运行算法": "Run algorithm",
    "双击算法打开参数对话框":
        "Double-click an algorithm to open its parameters",
    "工具箱初始化失败：{}": "Toolbox failed to initialize: {}",
    "缓冲区": "Buffer",
    "相交": "Intersect",
    "联合": "Union",
    "擦除": "Erase",
    "对称差": "Symmetrical Difference",
    "标识": "Identity",
    "裁剪": "Clip",
    "凸包": "Convex Hull",
    "包络矩形": "Bounding Box",
    "质心": "Centroid",
    "修复几何": "Fix Geometries",
    "多部件转单部件": "Multipart to Singlepart",
    "要素去重": "Delete Duplicates",
    "简化几何": "Simplify",
    "加密几何": "Densify",
    "坐标取整": "Round Coordinates",
    "矢量分析": "Vector Analysis",
    "矢量处理": "Vector Processing",
    "几何派生": "Geometry Extraction",
    "修掉自相交 / 环自切等无效几何，修不出来的丢掉":
        "Repair self-intersections and bad rings; unrepairable ones are dropped",
    "多部件要素的每个部件拆成独立要素":
        "Split each part of a multipart feature into its own feature",
    "按几何（或按字段取值）去重，只留第一条":
        "Drop duplicates by geometry (or by field value), keeping the first",
    "Douglas-Peucker 概化，按容差减点":
        "Douglas-Peucker generalisation, thinned by tolerance",
    "按最大间距沿几何插点": "Insert vertices along geometries at a max spacing",
    "坐标按小数位取整，顺便抹掉浮点噪声":
        "Round coordinates to N decimals, removing floating-point noise",
    "容差 / 间距（地图单位）": "Tolerance / spacing (map units)",
    "简化容差（地图单位）": "Simplify tolerance (map units)",
    "最大间距（地图单位）": "Maximum spacing (map units)",
    "小数位": "Decimal places",
    "去重字段（留空则按几何去重）":
        "Duplicate field (blank = deduplicate by geometry)",
    "（按几何去重）": "(deduplicate by geometry)",
    "自相交、环自切等无效几何会被修成有效几何；修完变成空的要素直接丢掉。":
        "Invalid geometries (self-intersections, bad rings) are repaired; "
        "features that become empty are dropped.",
    "多部件要素的每个部件拆成独立要素，属性照抄一份。":
        "Each part of a multipart feature becomes its own feature, with the "
        "attributes copied.",
    "几何相同（选字段则改为字段取值相同）的只保留第一条。":
        "Features with identical geometry (or identical field value when a "
        "field is chosen) keep only the first.",
    "Douglas-Peucker 概化：把偏离不超过容差的顶点去掉，并保证结果不自相交。":
        "Douglas-Peucker generalisation: drop vertices within the tolerance "
        "while keeping the result free of self-intersections.",
    "在几何上按最大间距插入顶点（点要素不变）。":
        "Insert vertices along geometries at the maximum spacing (points are "
        "unchanged).",
    "坐标按小数位吸附到网格，顺便抹掉浮点噪声。":
        "Snap coordinates to a grid of N decimals, removing floating-point "
        "noise.",
    "按距离外扩或收缩；地理坐标系可选按米计算":
        "Expand or shrink by a distance; geographic CRS can use meters",
    "保留两层相交部分，属性来自两层":
        "Keep where both layers overlap, with attributes from both",
    "两层充分剖分，输出全部碎块":
        "Partition both layers fully and output every piece",
    "输入层减去叠加层": "Subtract the overlay from the input",
    "去掉重叠部分，两层各留一份":
        "Drop the overlap, keeping one copy from each layer",
    "保留输入层全部范围，叠加层只用来切开":
        "Keep the whole input; the overlay only cuts it up",
    "用叠加层裁剪输入层，只保留输入层属性":
        "Clip the input with the overlay (input attributes only)",
    "每个要素的质心 / 内部点": "Centroid / interior point of each feature",
    "所有要素的最小凸多边形":
        "Smallest convex polygon covering all features",
    "所有要素的外接矩形": "Bounding box of all features",
    "缓冲…": "Buffer…",
    "相交…": "Intersect…",
    "联合…": "Union…",
    "裁剪…": "Clip…",
    "融合…": "Dissolve…",
    "批处理…": "Batch…",
    "按距离外扩或收缩要素": "Expand or shrink features by a distance",
    "保留两层相交的部分（两层属性都带出来）":
        "Keep the overlapping parts of both layers (attributes from both)",
    "两层充分剖分后输出全部碎块":
        "Fully partition both layers and output every piece",
    "用叠加图层裁剪输入图层（只保留输入层属性）":
        "Clip the input layer with the overlay layer (input attributes only)",
    "按字段分组做并集": "Union features grouped by a field",
    "对多个图层依次执行同一操作，结果合并成一个图层":
        "Run the same operation over several layers and merge the results",
    "按给定距离外扩（距离为负则收缩）。":
        "Expand by the given distance (negative shrinks).",
    "只保留两层相交的部分，两层属性都带出来。":
        "Keep only where the two layers overlap, with attributes from both.",
    "两层几何在交点处切开，输出全部碎块。":
        "Split both layers at intersections and output every piece.",
    "输入层减去叠加层，只保留输入层属性。":
        "Subtract the overlay layer from the input layer (input attributes "
        "only).",
    "两层互相减去对方，输出去掉重叠后的部分。":
        "Subtract each layer from the other, dropping the overlap.",
    "保留输入层全部范围，被叠加层切开的部分带上叠加属性。":
        "Keep the whole input layer; parts split by the overlay get its "
        "attributes.",
    "用叠加层裁剪输入层，只保留输入层属性。":
        "Clip the input layer with the overlay (input attributes only).",
    "按字段分组做并集；不选字段则全部融成一个要素。":
        "Union grouped by a field; with no field everything is merged.",
    "所有输入要素的最小凸多边形。":
        "Smallest convex polygon covering all input features.",
    "所有输入要素的外接矩形。":
        "Bounding box of all input features.",
    "每个要素的质心（可改为一定落在面内的内部点）。":
        "Centroid of each feature (optionally a guaranteed interior point).",
    " 叠加层与输入层 CRS 不一致时会自动投影。":
        " The overlay layer is reprojected automatically if its CRS differs.",
    "请先在图层树中选中一个矢量图层":
        "Select a vector layer in the layer tree first",
    "空间分析失败：{0}": "Spatial analysis failed: {0}",
    "批处理有 {0} 个作业失败": "{0} batch job(s) failed",
    "批处理作业失败：{0}": "Batch job failed: {0}",
    "批处理没有产生任何结果": "The batch produced no result",
    "批处理结果": "Batch result",
    "分析已取消": "Analysis cancelled",
    "「{0}」没有产生任何要素": "\u201c{0}\u201d produced no feature",
    "已写出分析结果：{0}（{1} 个要素）":
        "Analysis result written: {0} ({1} features)",
    "已写出分析结果：{0}": "Analysis result written: {0}",
    "「{0}」完成：{1} 个要素（{2:.0f} ms）":
        "\u201c{0}\u201d finished: {1} features ({2:.0f} ms)",
    "结果": "result",
    "几何编辑": "Geometry Editing",
    "度量": "Measure",
    "聚合": "Aggregate",
    "全层合并": "Merge Layer",
    "全层范围": "Layer Extent",
    "内含于字段": "Within Field",
    "内点": "Interior Point",
    "凹包": "Concave Hull",
    "分离字段": "Disjoint Field",
    "包含字段": "Contains Field",
    "去重复点": "Remove Repeated Points",
    "叠置字段": "Overlaps Field",
    "合并线": "Merge Lines",
    "吸附": "Snap",
    "周长字段": "Perimeter Field",
    "圆度字段": "Circularity Field",
    "外环": "Exterior Ring",
    "按类型提取": "Extract by Type",
    "收集为集合": "Collect",
    "旋转": "Rotate",
    "曲线偏移": "Offset Curve",
    "最大内切圆": "Max Inscribed Circle",
    "最小外接圆": "Min Bounding Circle",
    "最小外接矩形": "Min Bounding Rectangle",
    "最小间隙字段": "Min Clearance Field",
    "最短线": "Shortest Line",
    "环向标准化": "Normalize Orientation",
    "环数字段": "Ring Count Field",
    "相交字段": "Intersects Field",
    "相接字段": "Touches Field",
    "相等字段": "Equals Field",
    "矩形裁剪": "Clip by Rectangle",
    "穿越字段": "Crosses Field",
    "节点打散": "Break at Nodes",
    "被覆盖字段": "Covered By Field",
    "覆盖区合并": "Coverage Union",
    "覆盖字段": "Covers Field",
    "距离内字段": "Within Distance Field",
    "距离字段": "Distance Field",
    "转多部件": "To Multi-part",
    "边界": "Boundary",
    "部件数字段": "Part Count Field",
    "长度字段": "Length Field",
    "面构建": "Build Area",
    "面积字段": "Area Field",
    "顶点数字段": "Vertex Count Field",
    "以质心为原点按倍率放大缩小（SpatiaLite: ST_Scale）":
        "Scale features about their centroid by a factor "
        "(SpatiaLite: ST_Scale)",
    "几何不变，新增一列到叠加层的最近距离（SpatiaLite: ST_Distance）":
        "Geometry unchanged; adds the distance to the nearest overlay "
        "feature as a column (SpatiaLite: ST_Distance)",
    "几何不变，新增一列周长（面取边界长度）（SpatiaLite: ST_Perimeter）":
        "Geometry unchanged; adds a perimeter column (boundary length "
        "for polygons) (SpatiaLite: ST_Perimeter)",
    "几何不变，新增一列圆度 4π·面积/周长²（1 为正圆）（SpatiaLite: ST_Circularity）":
        "Geometry unchanged; adds a circularity column, 4π·area/perimeter² "
        "(1 = a perfect circle) (SpatiaLite: ST_Circularity)",
    "几何不变，新增一列最小间隙，排查自相交用（SpatiaLite: ST_MinimumClearance）":
        "Geometry unchanged; adds a minimum clearance column, handy for "
        "spotting self-intersections (SpatiaLite: ST_MinimumClearance)",
    "几何不变，新增一列环数（每个面 1 外壳 + 内部环）（SpatiaLite: ST_NRings）":
        "Geometry unchanged; adds a ring count column (each polygon: "
        "1 outer ring + interior rings) (SpatiaLite: ST_NRings)",
    "几何不变，新增一列部件数（简单几何为 1）（SpatiaLite: ST_NumGeometries）":
        "Geometry unchanged; adds a part count column (1 for simple "
        "geometries) (SpatiaLite: ST_NumGeometries)",
    "几何不变，新增一列长度；地理坐标可换算成米（SpatiaLite: ST_Length）":
        "Geometry unchanged; adds a length column; geographic coordinates "
        "can be converted to meters (SpatiaLite: ST_Length)",
    "几何不变，新增一列面积；地理坐标可换算成米（SpatiaLite: ST_Area）":
        "Geometry unchanged; adds an area column; geographic coordinates "
        "can be converted to meters (SpatiaLite: ST_Area)",
    "几何不变，新增一列顶点数（SpatiaLite: ST_NPoints）":
        "Geometry unchanged; adds a vertex count column (SpatiaLite: ST_NPoints)",
    "几何不变，标记是否与叠加层任一要素相交（SpatiaLite: ST_Intersects）":
        "Geometry unchanged; flags whether it intersects any overlay "
        "feature (SpatiaLite: ST_Intersects)",
    "几何不变，标记是否与叠加层某一要素完全相同（SpatiaLite: ST_Equals）":
        "Geometry unchanged; flags whether it is identical to an overlay "
        "feature (SpatiaLite: ST_Equals)",
    "几何不变，标记是否与叠加层要素完全分离（SpatiaLite: ST_Disjoint）":
        "Geometry unchanged; flags whether it is completely disjoint from "
        "overlay features (SpatiaLite: ST_Disjoint)",
    "几何不变，标记是否与叠加层要素边界相接（SpatiaLite: ST_Touches）":
        "Geometry unchanged; flags whether its boundary touches an "
        "overlay feature (SpatiaLite: ST_Touches)",
    "几何不变，标记是否与叠加层要素部分重叠（SpatiaLite: ST_Overlaps）":
        "Geometry unchanged; flags whether it partially overlaps an "
        "overlay feature (SpatiaLite: ST_Overlaps)",
    "几何不变，标记是否完整包含叠加层任一要素（SpatiaLite: ST_Contains）":
        "Geometry unchanged; flags whether it fully contains an overlay "
        "feature (SpatiaLite: ST_Contains)",
    "几何不变，标记是否完整落在叠加层任一要素内（SpatiaLite: ST_Within）":
        "Geometry unchanged; flags whether it lies completely inside an "
        "overlay feature (SpatiaLite: ST_Within)",
    "几何不变，标记是否穿越叠加层要素（SpatiaLite: ST_Crosses）":
        "Geometry unchanged; flags whether it crosses an overlay feature "
        "(SpatiaLite: ST_Crosses)",
    "几何不变，标记是否被叠加层任一要素覆盖（SpatiaLite: ST_CoveredBy）":
        "Geometry unchanged; flags whether it is covered by an overlay "
        "feature (SpatiaLite: ST_CoveredBy)",
    "几何不变，标记是否覆盖叠加层任一要素（SpatiaLite: ST_Covers）":
        "Geometry unchanged; flags whether it covers an overlay feature "
        "(SpatiaLite: ST_Covers)",
    "几何不变，标记给定距离内是否有叠加层要素（SpatiaLite: ST_DWithin）":
        "Geometry unchanged; flags whether any overlay feature falls "
        "within the given distance (SpatiaLite: ST_DWithin)",
    "单几何包成对应的多部件几何（SpatiaLite: ST_Multi）":
        "Wrap each single geometry into the matching multi-part geometry "
        "(SpatiaLite: ST_Multi)",
    "只取每个面的外壳轮廓（SpatiaLite: ST_ExteriorRing）":
        "Keep only the outer ring of each polygon (SpatiaLite: ST_ExteriorRing)",
    "可旋转的最小外接矩形，比轴对齐包络更贴合（SpatiaLite: ST_OrientedEnvelope）":
        "Rotatable minimum bounding rectangle; hugs the shape better than "
        "the axis-aligned envelope (SpatiaLite: ST_OrientedEnvelope)",
    "外环统一顺 / 逆时针，内环相反（SpatiaLite: ST_ForcePolygonCW/CCW）":
        "Outer rings all clockwise or counter-clockwise, inner rings the "
        "opposite (SpatiaLite: ST_ForcePolygonCW/CCW)",
    "所有相交处在节点处断开并去重复段（SpatiaLite: ST_Node）":
        "Break at every intersection into nodes and drop duplicate "
        "segments (SpatiaLite: ST_Node)",
    "把输入层顶点挪到容差内的叠加层顶点上（SpatiaLite: ST_Snap）":
        "Move input vertices onto overlay vertices within the tolerance "
        "(SpatiaLite: ST_Snap)",
    "按四至坐标裁掉界外内容（SpatiaLite: ST_ClipByRect）":
        "Cut away everything outside the given bounds (SpatiaLite: ST_ClipByRect)",
    "整层所有要素并成一个要素（SpatiaLite: ST_Union 聚合）":
        "Union all features of the layer into a single feature "
        "(SpatiaLite: ST_Union aggregate)",
    "整层所有部件装进一个几何，同类成多部件、混类成集合（SpatiaLite: ST_Collect）":
        "Pack all parts of the layer into one geometry: same type becomes "
        "multi-part, mixed types a collection (SpatiaLite: ST_Collect)",
    "整层按 X / Y 偏移量移动（SpatiaLite: ST_Translate）":
        "Move the whole layer by X / Y offsets (SpatiaLite: ST_Translate)",
    "整层的合并包围盒，输出一个矩形（SpatiaLite: ST_Extent）":
        "Combined bounding box of the layer, output as one rectangle "
        "(SpatiaLite: ST_Extent)",
    "无缝面片的高效合并，有重叠时自动退回普通并集（GEOS coverage_union）":
        "Efficient union of seamless polygons; falls back to a plain union "
        "when parts overlap (GEOS coverage_union)",
    "每个要素的代表点，保证落在要素内部（SpatiaLite: ST_PointOnSurface）":
        "A representative point of each feature, guaranteed to fall inside "
        "it (SpatiaLite: ST_PointOnSurface)",
    "每个输入要素到最近叠加要素的连线（SpatiaLite: ST_ShortestLine）":
        "The line from each input feature to its nearest overlay feature "
        "(SpatiaLite: ST_ShortestLine)",
    "比凸包更贴合形状的包络，阈值越大越接近凸包（SpatiaLite: ST_ConcaveHull）":
        "An envelope that hugs the shape better than the convex hull; a "
        "higher threshold approaches the convex hull (SpatiaLite: ST_ConcaveHull)",
    "混合几何里只保留点 / 线 / 面（SpatiaLite: ST_CollectionExtract）":
        "Keep only points / lines / polygons from mixed geometries "
        "(SpatiaLite: ST_CollectionExtract)",
    "由闭合线框直接构造面（SpatiaLite: ST_BuildArea）":
        "Build polygons directly from closed line work (SpatiaLite: ST_BuildArea)",
    "相邻的重复顶点只留一个，容差 0 表示完全相等才算重复（SpatiaLite: ST_RemoveRepeatedPoints）":
        "Keep just one of adjacent duplicate vertices; tolerance 0 means "
        "only exactly equal counts as duplicate "
        "(SpatiaLite: ST_RemoveRepeatedPoints)",
    "线按距离等距平移，负距离反向，可设圆弧平滑度（SpatiaLite: ST_OffsetCurve）":
        "Shift lines in parallel by a distance; negative goes the other "
        "way, with an arc smoothness option (SpatiaLite: ST_OffsetCurve)",
    "线的方向反向、面的环序反向（SpatiaLite: ST_Reverse）":
        "Reverse line directions and polygon ring order (SpatiaLite: ST_Reverse)",
    "绕质心或包围盒中心旋转，角度为度、逆时针为正（SpatiaLite: ST_Rotate）":
        "Rotate about the centroid or bounding-box center; angle in "
        "degrees, counter-clockwise positive (SpatiaLite: ST_Rotate)",
    "覆盖要素的最小圆（SpatiaLite: ST_MinimumBoundingCircle）":
        "The smallest circle that covers the feature "
        "(SpatiaLite: ST_MinimumBoundingCircle)",
    "面内能放下的最大圆，可调求解容差（SpatiaLite: ST_MaximumInscribedCircle）":
        "The largest circle that fits inside a polygon, with an adjustable "
        "solver tolerance (SpatiaLite: ST_MaximumInscribedCircle)",
    "面的边界成线，线的边界成端点（SpatiaLite: ST_Boundary）":
        "Polygon boundaries become lines; line boundaries become endpoints "
        "(SpatiaLite: ST_Boundary)",
    "首尾相接的线段并成一条长线（SpatiaLite: ST_LineMerge）":
        "Merge end-to-end segments into a single long line "
        "(SpatiaLite: ST_LineMerge)",
    "X 倍率": "X factor",
    "X 偏移": "X offset",
    "Y 倍率": "Y factor",
    "Y 偏移": "Y offset",
    "偏移距离": "Offset distance",
    "右下 X": "Lower-right X",
    "右下 Y": "Lower-right Y",
    "吸附容差": "Snap tolerance",
    "周长单位": "Perimeter unit",
    "外环方向": "Outer ring direction",
    "容差单位": "Tolerance unit",
    "左上 X": "Upper-left X",
    "左上 Y": "Upper-left Y",
    "斜接限制": "Miter limit",
    "旋转中心": "Rotation center",
    "旋转角度（度）": "Rotation angle (degrees)",
    "求解容差（地图单位）": "Solver tolerance (map units)",
    "目标类型": "Target type",
    "贴合阈值（0 最凹，1 即凸包）":
        "Fit threshold (0 = most concave, 1 = convex hull)",
    "包围盒中心": "Bounding-box center",
    "逆时针（CCW）": "Counter-clockwise (CCW)",
    "顺时针（CW）": "Clockwise (CW)",
    "制图出图": "Cartographic Output",
    "出图": "Output",
    "布局设计器…": "Layout Designer…",
    "新建布局": "New Layout",
    "导出 PDF": "Export PDF",
    "导出图片": "Export Image",
    "打印…": "Print…",
    "打印": "Print",
    "新建 / 编辑打印布局：图框、图例、比例尺、指北针、格网":
        "Create or edit a print layout: map frame, legend, scale bar, "
        "north arrow, grid",
    "按当前地图视图创建一个 A4 横向布局":
        "Create an A4 landscape layout from the current map view",
    "把当前布局导出为矢量 PDF（文字可选中、线条不糊）":
        "Export the current layout as vector PDF (selectable text, crisp "
        "lines)",
    "把当前布局导出为 PNG / JPG / TIFF":
        "Export the current layout as PNG / JPG / TIFF",
    "把当前布局送到打印机": "Send the current layout to a printer",
    "打印布局设计器": "Print Layout Designer",
    "布局": "Layout",
    "布局 1": "Layout 1",
    "布局设计器打开失败：{0}": "Failed to open the layout designer: {0}",
    "布局「{0}」：{1} 个页面元素":
        "Layout \u201c{0}\u201d: {1} page item(s)",
    "正在加载布局「{0}」…":
        "Loading layout \u201c{0}\u201d\u2026",
    "显示 / 隐藏": "Show / hide",
    "上一视图": "Previous view",
    "下一视图": "Next view",
    "删除选中的元素": "Delete the selected items",
    "前进到下一个视图状态": "Go to the next view state",
    "剪切选中的元素": "Cut the selected items",
    "剪贴板里没有可粘贴的元素": "Nothing to paste on the layout clipboard",
    "单击选中一个元素": "Click to select a single item",
    "参考线": "Guides",
    "参考线：从标尺上按住鼠标拖到页面上即可拉出一条": "Guides: drag from a ruler onto the page to create one",
    "参考线：拖动可移动，选中后按 Delete 删除": "Guide: drag to move, press Delete to remove",
    "参考线：拖动可移动，选中后按 Delete 删除；拖动元素靠近它会自动吸附": "Guides: drag to move, press Delete to remove; drag an item near one to snap it",
    "添加参考线失败": "Failed to add the guide",
    "添加水平参考线": "Add horizontal guide",
    "添加垂直参考线": "Add vertical guide",
    "清除全部参考线": "Clear all guides",
    "删掉所有参考线": "Delete every guide",
    "在画布中心添加一条水平参考线": "Add a horizontal guide at the canvas centre",
    "在右键的位置添加一条水平参考线": "Add a horizontal guide where you right-clicked",
    "在右键的位置添加一条垂直参考线": "Add a vertical guide where you right-clicked",
    "删除这条参考线": "Delete this guide",
    "参考线：在标尺上按住它拖动可移动，右键可删除": "Guide: hold and drag it on the ruler to move it, right-click to delete",
    "参考线：在标尺上按住拖动可移动，在标尺空白处拖动可新建，标尺上右键可删除": "Guides: drag one on a ruler to move it, drag on empty ruler space to add one, right-click a ruler to delete",
    "参考线已添加（{0} mm）：在标尺上按住拖动可移动，标尺上右键可删除": "Guide added at {0} mm: drag it on a ruler to move it, right-click the ruler to delete",
    "缩放到…": "Zoom to…",
    "缩放到…（地图视图范围 / 比例尺）": "Zoom to… (map view extent / scale)",
    "已激活": "Active",
    "所选图层": "Selected layers",
    "充满图框": "Fill the frame",
    "勾上 = 裁掉超出图框比例的范围，让数据铺满图框；取消 = 保留全部范围（图框比数据宽时会留白）": "Ticked = crop the extent to the frame's aspect so the data fills the frame; unticked = keep the whole extent (whitespace when the frame is wider than the data)",
    "在画布中心添加一条垂直参考线": "Add a vertical guide at the canvas centre",
    "添加水平 / 垂直参考线": "Add a horizontal / vertical guide",
    "参考线已添加（{0} mm）：拖动可移动，选中后按 Delete 删除": "Guide added at {0} mm: drag to move, press Delete to remove",
    "已清除 {0} 条参考线": "Cleared {0} guide(s)",
    "当前没有参考线": "There are no guides",
    "显示 / 隐藏参考线（从标尺拖出，或点右边的「添加参考线」；选中后按 Delete 删除）": "Show / hide guides (drag from a ruler, or use “Add guide” on the right; press Delete to remove)",
    "包含已隐藏的图层": "Include hidden layers",
    "勾上 = 只画图层树里可见的；取消 = 地图框包含工程里所有图层（含在图层树里被隐藏的）": "Ticked = draw only the layers visible in the layer tree; unticked = the map frame includes every layer in the project (even ones hidden in the layer tree)",
    "取不到打印机：{0}": "Cannot access the printer: {0}",
    "取消全部选中": "Deselect all",
    "回到上一个视图状态": "Go back to the previous view state",
    "在画布上边 / 左边显示毫米标尺（拖动标尺可拉出参考线）": "Show millimetre rulers on the top / left edge (drag a ruler to pull out a guide)",
    "复制布局": "Duplicate layout",
    "复制布局失败：{0}": "Failed to duplicate the layout: {0}",
    "复制当前布局（另存为一张新布局并打开）": "Duplicate this layout (saved as a new layout and opened)",
    "复制选中的元素": "Copy the selected items",
    "大小": "Size",
    "导航：拖动页面平移（再点一次退出）": "Navigate: drag the page to pan (click again to exit)",
    "已删除 {0} 个元素": "Deleted {0} item(s)",
    "已取消激活地图框": "Map frame deactivated",
    "已复制 {0} 个元素": "Copied {0} item(s)",
    "已复制布局：{0}": "Layout duplicated: {0}",
    "已按打印机中的页面设置：{0}": "Page set from the printer: {0}",
    "已激活地图框：滚轮缩放、拖动平移地图内容": "Map frame activated: wheel to zoom, drag to pan the map content",
    "已粘贴 {0} 个元素": "Pasted {0} item(s)",
    "已选中 {0} 个元素": "Selected {0} item(s)",
    "已锁定比例尺 1:{0}": "Scale locked at 1:{0}",
    "打印机中的页面": "Page from printer",
    "把剪贴板里的元素粘贴到页面": "Paste the clipboard items onto the page",
    "把激活地图框的范围设成「全图」": "Set the active map frame extent to \"full map\"",
    "拖框选中多个元素": "Drag a box to select several items",
    "按屏幕实际尺寸显示（1:1）": "Show at actual size (1:1)",
    "按默认打印机的纸张与可打印边距设置页面": "Set the page from the default printer's paper and printable margins",
    "显示 / 隐藏参考线（从标尺拖出，选中后按 Delete 删除）": "Show / hide guides (drag from a ruler, press Delete to remove)",
    "显示页边距（内容区）框": "Show the margin (content area) frame",
    "标尺": "Rulers",
    "标尺（毫米）：从这里**拖**出一条参考线": "Ruler (mm): drag from here to pull out a guide",
    "框选": "Box select",
    "清除所选内容": "Clear selection",
    "激活": "Activate",
    "激活地图框：滚轮缩放 / 拖动平移**地图内容**（元素位置不动）": "Activate the map frame: wheel zooms / drag pans the map content (items stay put)",
    "用主窗口地图视图的范围 / 比例尺": "Use the map view's extent / scale",
    "用当前地图比例尺": "Use the current map scale",
    "用当前地图视图范围": "Use the current map view extent",
    "算不出当前比例尺：请先用「用当前地图视图范围」定个范围": "Cannot compute the scale: first set an extent with \"Use the current map view extent\"",
    "粘贴到原位置": "Paste in place",
    "粘贴失败": "Paste failed",
    "纸张 / 方向 / 边距 / 分辨率": "Paper / orientation / margins / resolution",
    "纸张大小": "Paper size",
    "纸张方向": "Paper orientation",
    "缩放到 100%": "Zoom to 100%",
    "缩放到全图": "Zoom to full map",
    "缩放到地图视图": "Zoom to map view",
    "请先选中要删除的元素": "Select the items to delete first",
    "请先选中要剪切的元素": "Select the items to cut first",
    "请先选中要复制的元素": "Select the items to copy first",
    "边距": "Margins",
    "选中页面上所有元素": "Select every item on the page",
    "选择元素": "Select items",
    "选择方式": "Selection mode",
    "选择方式：框选": "Selection mode: box select",
    "选择方式：点选": "Selection mode: click select",
    "选择（点选）": "Select (click)",
    "页面设置": "Page setup",
    "页面设置…": "Page setup…",
    "页面设置失败：{0}": "Page setup failed: {0}",
    "页面里还没有地图框": "There is no map frame on the page",
    "页面里还没有地图框：先加一个地图框再激活": "There is no map frame on the page: add one before activating",
    "布局「{0}」里还没有页面元素：用「开始」页里的按钮添加地图框 / 图例 / 比例尺…":
        "Layout \u201c{0}\u201d has no page items yet: add a map frame / "
        "legend / scale bar with the buttons on the Start tab\u2026",
    "出图完成：{0}": "Export finished: {0}",
    "出图提示：{0}": "Export note: {0}",
    "出图失败：{0}": "Export failed: {0}",
    "出图失败": "Export failed",
    "出图完成": "Export finished",
    "未知原因": "unknown reason",
    "纸张": "Paper", "方向": "Orientation", "横向": "Landscape",
    "纵向": "Portrait", "页边距": "Margins", "左": "Left", "上": "Top",
    "右": "Right", "下": "Bottom",
    "适应页面": "Fit Page", "刷新预览": "Refresh Preview",
    "添加元素": "Add item", "元素清单": "Items",
    "地图框": "Map frame", "图例": "Legend", "比例尺": "Scale bar",
    "指北针": "North arrow", "格网": "Grid", "文字": "Text",
    "方里网": "Grid", "经纬网": "Graticule", "正文字号": "Body font size",
    "图片": "Image",
    "删除": "Delete", "提高绘制顺序": "Raise in draw order",
    "降低绘制顺序": "Lower in draw order", "删除选中元素":
        "Delete the selected item",
    "位置与尺寸": "Position and size", "宽": "Width", "高": "Height",
    "绘制顺序": "Draw order",
    "对齐页面内容区（页边距内）":
        "Align to the page content area (inside margins)",
    "勾选后可以一键把元素摆到内容区左上角":
        "Lets you snap the item to the content area with one click",
    "铺满内容区": "Fill content area",
    "同一位置上的元素，值大的画在上面":
        "Where items overlap, the higher value draws on top",
    "未选中元素": "No item selected", "（未选中）": "(none selected)",
    "元素设置": "Element properties",
    "移动（再点一次退出）": "Pan (click again to exit)",
    "在清单或画布上选中一个元素后编辑属性":
        "Select an item in the list or on the canvas to edit its "
        "properties",
    "图层": "Layers", "全选 / 全不选": "Check / uncheck all",
    "定位方式": "Positioning", "按比例尺": "By scale",
    "指定范围": "Fixed extent", "全图": "Full extent",
    "比例尺分母": "Scale denominator", "中心 X": "Centre X",
    "中心 Y": "Centre Y", "用当前地图视图": "Use current map view",
    "把主窗口画布当前范围填进「指定范围」":
        "Copy the current canvas extent into \u201cFixed extent\u201d",
    "绘制图框边框": "Draw frame border",
    "地图框属性": "Map frame", "图例属性": "Legend",
    "比例尺属性": "Scale bar", "指北针属性": "North arrow",
    "格网属性": "Grid", "文字属性": "Text", "图片属性": "Image",
    "（未选中）属性": "(none selected)",
    "标题字号": "Title font size", "列数": "Columns",
    "显示图层名": "Show layer names", "显示标题": "Show title",
    "边框": "Border", "按内容自动收缩高度":
        "Shrink height to fit content",
    "按内容调整到合适大小": "Fit size to content",
    "链接地图框": "Linked map frame", "（第一个地图框）":
        "(first map frame)",
    "图面单位": "Map units", "公制 (m/km)": "Metric (m/km)",
    "英制 (ft)": "Imperial (ft)", "计量单位": "Units",
    "分段数": "Divisions", "字号": "Font size", "条高": "Bar height",
    "显示单位": "Show units", "显示 1:N 比例文字": "Show 1:N text",
    "样式": "Style", "罗盘": "Compass", "玫瑰": "Rose",
    "箭头": "Arrow", "北字": "Letter N", "旋转角": "Rotation",
    "显示「北」": "Show \u201cN\u201d",
    "间隔（图面单位）": "Interval (map units)",
    "间隔（度）": "Interval (degrees)", "注记字号": "Label font size",
    "显示注记": "Show labels", "内容": "Content", "粗体": "Bold",
    "斜体": "Italic", "对齐": "Align", "居中": "Centre",
    "保持长宽比": "Keep aspect ratio",
    "导出 SVG": "Export SVG",
    "选择图片": "Choose an image",
    "图片 (*.png *.jpg *.jpeg *.bmp *.svg)":
        "Images (*.png *.jpg *.jpeg *.bmp *.svg)",
    "PNG 图片 (*.png);;JPG 图片 (*.jpg);;TIFF 图片 (*.tif)":
        "PNG image (*.png);;JPG image (*.jpg);;TIFF image (*.tif)",
    "72 dpi（屏幕）": "72 dpi (screen)", "150 dpi（草稿）": "150 dpi (draft)",
    "300 dpi（印刷）": "300 dpi (press)", "600 dpi（高清）": "600 dpi (high)",
    "1200 dpi（超清）": "1200 dpi (ultra)",
    "打印模块不可用：": "Print support unavailable: ",
    "无头环境无法弹出打印对话框":
        "Cannot open a print dialog in a headless environment",
    "主窗口当前没有可用范围": "The main window has no usable extent",
    "无头环境": "headless environment",
    "添加矢量图层 (Ctrl+Shift+V)：Shapefile / GeoPackage / GeoJSON…":
        "Add vector layer (Ctrl+Shift+V): Shapefile / GeoPackage / GeoJSON…",
    "添加栅格图层 (Ctrl+Shift+R)：GeoTIFF / IMG / ASCII Grid…":
        "Add raster layer (Ctrl+Shift+R): GeoTIFF / IMG / ASCII Grid…",
    "平移地图（拖动；按住空格临时平移）(Alt+1)":
        "Pan the map (drag; hold space bar to pan temporarily) (Alt+1)",
    "放大镜模式：点击或框选放大 (Alt+2)":
        "Zoom-in mode: click or drag a box (Alt+2)",
    "点击缩小一档 (Alt+3)": "Click to zoom out one step (Alt+3)",
    "缩放到全部图层的完整范围 (Ctrl+Shift+F)":
        "Zoom to full extent of all layers (Ctrl+Shift+F)",
    "点击地图查询要素属性 (Ctrl+Shift+I)":
        "Click the map to identify features (Ctrl+Shift+I)",
    "框选要素（Ctrl 加选 / Shift 减选）(Ctrl+Shift+A)":
        "Select by rectangle (Ctrl add / Shift subtract) (Ctrl+Shift+A)",
    "左键加点、右键结束的折线测距 (Ctrl+Shift+M)":
        "Measure distance: left-click adds vertices, right-click "
        "finishes (Ctrl+Shift+M)",
    "左键加点、右键闭合的多边形测面 (Ctrl+Shift+J)":
        "Measure area: left-click adds vertices, right-click "
        "closes (Ctrl+Shift+J)",
    "打开当前活动图层的属性表 (F6)":
        "Open the active layer's attribute table (F6)",
    "打开基础工具箱（370+ 空间分析算法）(Ctrl+Alt+T)":
        "Open the basic toolbox (370+ algorithms) (Ctrl+Alt+T)",
    "进入/退出当前活动图层的编辑状态 (Ctrl+E)":
        "Toggle editing on the active layer (Ctrl+E)",
    "添加要素：按活动图层的几何类型在地图上数字化新要素 (Ctrl+.)":
        "Add feature: digitize on the map using the layer's geometry "
        "type (Ctrl+.)",
    "移动要素：拖动选中的要素到新位置 (Ctrl+Alt+M)":
        "Move feature: drag selected features to a new position "
        "(Ctrl+Alt+M)",
    "删除活动图层中选中的要素 (Del)":
        "Delete selected features in the active layer (Del)",
    "提交所有图层中未保存的编辑 (Ctrl+Shift+E)":
        "Commit unsaved edits in all layers (Ctrl+Shift+E)",
    "放弃所有未保存的编辑，恢复到上次提交状态 (Ctrl+Alt+R)":
        "Discard all unsaved edits (restore last commit state) "
        "(Ctrl+Alt+R)",
    "缩放到活动图层范围；跨坐标系时先做坐标变换 (Ctrl+Shift+L)":
        "Zoom to the active layer (reprojected to the project CRS "
        "first) (Ctrl+Shift+L)",
    "缩放到活动图层中选中的要素 (Ctrl+J)":
        "Zoom to the selected features of the active layer (Ctrl+J)",
    "重绘全部图层 (F5)": "Redraw all layers (F5)",
    "工程标题、量算单位、坐标精度、画布底色与目标坐标系 (Ctrl+Shift+P)":
        "Project title, measurement units, coordinate precision, canvas "
        "colour and target CRS (Ctrl+Shift+P)",
    "选择工程 / 画布的目标坐标系 (Ctrl+Shift+K)":
        "Choose the project / canvas destination CRS (Ctrl+Shift+K)",
    "把当前工程另存为新文件 (Ctrl+Shift+S)":
        "Save the current project to a new file (Ctrl+Shift+S)",
    "退出程序 (Ctrl+Q)": "Quit the application (Ctrl+Q)",
    "查看全部菜单功能的快捷键 (Ctrl+F1)":
        "Show all menu shortcuts (Ctrl+F1)",
    "关于本程序": "About this application",
    "展开图层树的所有分组节点": "Expand all group nodes in the layer tree",
    "将地图范围缩放到该图层的完整范围":
        "Zoom the map to this layer's full extent",
    "就地编辑图层名称": "Rename the layer in place",
    "从工程中移除该图层（不删除源数据）":
        "Remove this layer from the project (source data is kept)",
    "用 SQL WHERE 条件只显示满足要求的要素":
        "Show only features matching an SQL WHERE clause",
    "浏览/编辑该图层的属性记录":
        "Browse / edit this layer's attribute records",
    "打开符号选择器修改渲染样式":
        "Open the symbol selector to edit the renderer",
    "用颜色选择器直接修改填充色":
        "Change the fill color directly with a color picker",
    "用颜色选择器直接修改边框或线条颜色":
        "Change the stroke / line color directly with a color picker",
    "独立设置标注字段、字体、字号与颜色":
        "Set label field, font, size and color in a standalone dialog",
    "查看各波段的最小/最大/均值/标准差":
        "View per-band min/max/mean/stddev",
    "选择 R/G/B 通道映射的波段":
        "Choose which bands map to the R/G/B channels",
    "关闭当前工程并新建空工程": "Close the current project and start empty",
    "打开 .qgz / .qgs 工程文件": "Open a .qgz / .qgs project file",
    "保存当前工程 (Ctrl+S)": "Save the current project (Ctrl+S)",
    "把当前工程另存为新文件": "Save the current project to a new file",
    "把地图画布当前内容导出为 PNG 图片":
        "Export the current map canvas to a PNG image",
    "生成内存演示图层（城市点 + 连线）":
        "Generate in-memory demo layers (city points + a line)",
    "在地图上数字化添加新要素": "Digitize a new feature on the map",
    "拖动选中的要素到新位置": "Drag selected features to a new position",
    "提交所有未保存的编辑": "Commit all unsaved edits",
    "放弃所有未保存的编辑": "Discard all unsaved edits",
    "拖动平移地图": "Pan the map by dragging",
    "点击或框选放大": "Click or drag a box to zoom in",
    "点击查询要素属性": "Click to identify features",
    "框选地图上的要素": "Select features with a rectangle",
    "折线测距": "Measure distances along a line",
    "多边形测面": "Measure areas of a polygon",
    "切换全屏显示 (F11)": "Toggle full screen (F11)",
    "用 SQL WHERE 条件过滤活动图层的要素":
        "Filter active layer features with an SQL WHERE clause",
    "独立设置活动图层的标注字段与样式":
        "Set the active layer's labeling field and style",
    "从工程中移除活动图层": "Remove the active layer from the project",
    "在图层树中新建一个分组": "Create a new group in the layer tree",
    "选择工程 / 画布的目标坐标系":
        "Choose the project / canvas destination CRS",
    "主题、语言、字体、图标大小等外观设置":
        "Appearance settings: theme, language, font, icon size…",
    "关于 GmaGIS": "About GmaGIS",
    "轻量级桌面 GIS（PySide6 + GDAL）":
        "Lightweight desktop GIS (PySide6 + GDAL)",
    "版本": "Version",
    "界面框架": "UI framework",
    "运行时": "Runtime",
    "系统": "System",
    "未安装": "not installed",
    "第三方许可声明": "Third-party license notices",
    "第三方许可声明…": "Third-party notices…",
    "打开文件位置": "Show in folder",
    "复制全文": "Copy all",
    "文件：{}": "File: {}",
    "未随发行物提供，以上为内置摘要":
        "not shipped with this build; showing the built-in summary above",
    "本产品使用 Qt6，依据 GNU Lesser General Public License v3（LGPL v3）授权。":
        "This product uses Qt6 under the terms of the GNU Lesser General "
        "Public License v3 (LGPL v3).",
    "本产品经 shapely / rasterio / pyogrio 以动态链接方式使用 GEOS，"
    "其许可为 GNU Lesser General Public License v2.1（LGPL v2.1）或更高版本。":
        "GEOS is used through shapely / rasterio / pyogrio by dynamic "
        "linking, under the GNU Lesser General Public License v2.1 (LGPL "
        "v2.1) or later.",
    "完整许可证全文见 resources/licenses/ 。":
        "Full license texts are in resources/licenses/ .",
    "未找到 THIRD_PARTY_NOTICES.md，以上为内置摘要。":
        "THIRD_PARTY_NOTICES.md was not found; the above is the built-in "
        "summary.",
    "填充颜色已更新": "Fill color updated",
    "边框/线条颜色已更新": "Stroke / line color updated",
    "标注已开启：{}": "Labels enabled: {}",
    "标注已关闭：{}": "Labels disabled: {}",
    "光标处坐标（地图坐标系 | WGS84 经纬度）":
        "Cursor coordinates (map CRS | WGS84 lon/lat)",
    "工程内图层数量与矢量要素总数":
        "Number of layers and total feature count in the project",
    "地图比例尺（可直接输入，如 1:5000）":
        "Map scale (type directly, e.g. 1:5000)",
    "暂停渲染（勾选后地图停止重绘，适合大批量加载前）":
        "Freeze rendering (map stops redrawing; useful before bulk loading)",
    "暂停/恢复地图渲染": "Freeze / resume map rendering",
    "渲染已暂停": "Rendering frozen",
    "渲染已恢复": "Rendering resumed",
    "导出要素为…": "Export Features As…",
    "导出栅格为…": "Export Raster As…",
    "过滤要素…(原生查询构建器)": "Filter Features… (native query builder)",
    "地图坐标系，点击修改。": "Map CRS, click to change.",
    "设置地图坐标系": "Set Map CRS",
    "X:--, Y:--": "X:--, Y:--",
    "光标处地图坐标": "Cursor map coordinates",
    "渲染中…": "Rendering…",
    "渲染中… {0}": "Rendering… {0}",
    "本机 CPU 与内存占用（每秒刷新）": "CPU & memory usage (refresh 1s)",
    "定位：输入可搜索图层、算法、书签和经纬度坐标":
        "Locate: search layers, algorithms, bookmarks, coordinates",
    "标注已应用：{}": "Labels applied: {}",
    "图层属性": "Layer Properties",
    "坐标系": "Coordinate Reference System",
    "布局坐标系": "Layout Coordinate System",
    "地图视图的坐标系": "Map View Coordinate System",

    "图层坐标系": "Layer Coordinate System",
    "（未指定）": "Unspecified",
    "该图层没有可显示的元数据。": "No metadata available for this layer.",
    "开始/切换该图层的编辑状态": "Toggle editing for this layer",
    "停止并保存": "Stop and Save",
    "关闭面板": "Close Panel",
    "浮动窗口": "Float Window",
    "取消浮动": "Dock Window",
    "添加到图层": "Add to Layers",
    "刷新": "Refresh",
    "全部刷新": "Refresh All",
    "打开所在目录": "Show in Explorer",
    "已拖入 {} 个图层": "{} layer(s) dropped in",
    "已从浏览器添加 {} 个图层": "{} layer(s) added from browser",
    "常规": "General",
    "基本信息": "Basic Information",
    "名称": "Name",
    "来源": "Source",
    "提供者": "Provider",
    "图层类型": "Layer Type",
    "矢量图层": "Vector Layer",
    "栅格图层": "Raster Layer",
    "影像": "Imagery",
    "几何类型": "Geometry Type",
    "要素数": "Feature Count",
    "字段数": "Field Count",
    "编码": "Encoding",
    "宽度": "Width",
    "高度": "Height",
    "波段数": "Band Count",
    "范围": "Extent",
    "字段列表": "Fields",
    "类型": "Type",
    "长度": "Length",
    "精度": "Precision",
    "波段列表": "Bands",
    "AuthID": "AuthID",
    "编码（AuthID）": "Code (AuthID)",
    "单位缩写": "Unit abbreviation",
    "米 / 单位": "Metres per unit",
    "椭球与基准": "Ellipsoid and datum",
    "基准面": "Datum",
    "椭球体": "Ellipsoid",
    "长短半轴": "Semi-major / semi-minor axis",
    "反扁率": "Inverse flattening",
    "投影参数": "Projection parameters",
    "复制定义": "Copy definition",
    "许可与声明": "License & Notices",
    "查看第三方许可声明…": "View third-party notices…",
    "组件许可": "Component licenses",
    "声明摘要": "Summary",
    "许可证": "License",
    "未找到 THIRD_PARTY_NOTICES.md（开发环境正常）：以上为内置摘要与组件清单。":
        "THIRD_PARTY_NOTICES.md not found (normal in dev builds): "
        "showing the built-in summary and component list.",
    "复制并修改": "Copy and Modify",
    "删除此坐标系": "Delete this CRS",
    "从最近使用中移除": "Remove from Recent",
    "新建投影坐标系": "New Projected CRS",
    "复制坐标系定义（WKT / PROJ 串）": "Copy CRS definition (WKT / PROJ)",
    "WKT": "WKT",
    "地理坐标系": "Geographic CRS",
    "投影坐标系": "Projected CRS",
    "单位": "Units",
    "无效": "Invalid",

    "缩放": "Zoom",
    "工具栏": "Toolbars",
    "刷新画布": "Refresh Canvas",
    "缩放至图层": "Zoom to Layer",
    "缩放至选择": "Zoom to Selection",
    "缩放至": "Zoom To",
    "按属性…": "Select by Attributes…",
    "按位置…": "Select by Location…",
    "清除": "Clear",
    "添加": "Add",
    "图层属性…": "Layer Properties…",
    "导出矢量图层…": "Export Vector Layer…",
    "导出栅格图层…": "Export Raster Layer…",
    "退出": "Exit",
    "框选要素": "Select Features by Rectangle",
    "标注设置…": "Label Settings…",
    "标注设置": "Label Settings",
    "导入样式": "Import Style",
    "导入符号系统": "Import Symbology",
    "导入标注设置": "Import Label Settings",
    "导入符号系统 / 导入标注样式": "Import from Style Library / Label Style",
    "从图层应用": "Apply from Layer",
    "没有可导入的图层": "No layer to import from",
    "工程属性…": "Project Properties…",
    "快捷键速查表…": "Keyboard Shortcuts…",

    "工程属性": "Project Properties",
    "工程标识": "Project Info",
    "工程标题：": "Project title:",
    "留空则使用默认标题": "Leave empty for the default title",
    "工程文件：": "Project file:",
    "（未保存）": "(unsaved)",
    "量算单位（用于测量工具与要素统计）":
        "Measurement units (measure tools & statistics)",
    "距离单位：": "Distance units:",
    "面积单位：": "Area units:",
    "显示": "Display",
    "坐标精度：": "Coordinate precision:",
    " 位小数": " decimal places",
    "画布背景色：": "Canvas background:",
    "自定义颜色": "Custom colour",
    "目标坐标系：所有图层都会实时重投影到该坐标系后再叠加显示。":
        "Target CRS: every layer is reprojected on the fly to it "
        "before being drawn.",
    "工程属性已应用：单位 {} / {}，坐标精度 {} 位":
        "Project properties applied: units {} / {}, {} decimals",
    "工程属性：距离单位 {}，面积单位 {}，坐标精度 {} 位":
        "Project properties: distance {}, area {}, {} decimals",

    "米": "Meters",
    "千米": "Kilometers",
    "英尺": "Feet",
    "码": "Yards",
    "英里": "Miles",
    "海里": "Nautical Miles",
    "度": "Degrees",
    "平方米": "Square Meters",
    "公顷": "Hectares",
    "平方千米": "Square Kilometers",
    "平方英尺": "Square Feet",
    "平方英里": "Square Miles",
    "英亩": "Acres",

    "功能": "Action",
    "快捷键": "Shortcut",
    "筛选：": "Filter:",
    "按功能名或按键过滤，如 保存 / Ctrl+S":
        "Filter by action name or key, e.g. Save / Ctrl+S",
    "画布操作": "Canvas",
    "缩放画布": "Zoom canvas",
    "平移画布": "Pan canvas",
    "结束量算 / 数字化": "Finish measuring / digitizing",
    "框选时加选": "Add to selection while dragging",
    "框选时减选": "Remove from selection while dragging",
    "取消当前工具": "Cancel current tool",
    "共 {} 个快捷键": "{} shortcuts in total",
    "匹配 {} 个": "{} matched",
    "{} 项": "{} items",
    "滚轮": "Mouse wheel",
    "中键拖动 / 空格+拖动": "Middle-drag / Space + drag",
    "右键 / Esc": "Right click / Esc",
    "Ctrl + 拖动": "Ctrl + drag",
    "Shift + 拖动": "Shift + drag",
    "Esc": "Esc",

    "无坐标系": "No CRS",
    "复制 AuthID": "Copy AuthID",
    "最近使用": "Recently used",
    "已复制 {}": "Copied {}",

    "源": "Source",
    "数据源与坐标系": "Data source & CRS",
    "存储驱动": "Storage driver",
    "{0}（按扩展名推断）": "{0} (inferred from the extension)",
    "磁盘占用": "Disk usage",
    "{0}（{1} 个文件）": "{0} ({1} files)",
    "读写": "Access",
    "字段名": "Field name",
    "类别": "Kind",
    "数值": "Numeric",
    "日期时间": "Date/time",
    "布尔": "Boolean",
    "其它": "Other",
    "栅格结构": "Raster structure",
    "尺寸": "Size",
    "无数据值": "No-data value",
    "可见要素数": "Visible features",
    "已过滤（子集）要素数": "Filtered (subset) features",
    "中心": "Centre",
    "像素地面尺寸": "Pixel size on the ground",
    "金字塔层级": "Overview levels",
    "属性": "Property",
    "数据源": "Source",
    "空间范围": "Spatial extent",
    "图层 ID": "Layer ID",
    "是否可编辑": "Editable",
    "像素尺寸": "Pixel size",
    "坐标系名称": "CRS name",
    "投影方法": "Projection",
    "椭球": "Ellipsoid",
    "WKT 定义：": "WKT definition:",
    "类型名": "Type name",
    "注释": "Comment",
    "数据类型": "Data type",
    "最小": "Minimum",
    "最大": "Maximum",
    "元数据": "Metadata",
    "（本部分为空）": "(this section is empty)",
    "标题": "Title",
    "摘要": "Abstract",
    "父标识": "Parent identifier",
    "图层名称": "Layer name",
    "关键字": "Keywords",
    "许可": "Licenses",
    "联系人": "Contacts",
    "链接": "Links",
    "历史记录": "History",
    "图层范围（图层坐标系）": "Layer extent (layer CRS)",
    "元数据空间范围": "Metadata spatial extent",
    "范围 CRS": "Extent CRS",
    "姓名": "Name",
    "角色": "Role",
    "邮箱": "Email",
    "地址": "URL",
    "格式": "Format",
    "复制当前页": "Copy current page",
    "已复制当前页内容": "Current page copied",
    "（本页无可复制内容）": "(nothing to copy on this page)",

    "测量角度": "Measure Angle",
    "角度：": "Angle:",
    "边1长度：": "Edge 1:",
    "边2长度：": "Edge 2:",
    "第1点为角顶点，再点两条边端点，点满3点自动结束":
        "First click sets the vertex, then click the two edge "
        "endpoints; finishes automatically at 3 points",
    "新建 Shapefile 图层…": "New Shapefile layer…",
    "新建临时图层（内存）…": "New temporary (memory) layer…",
    "新建形状文件": "New shapefile",
    "新建地理包": "New GeoPackage",
    "新建 Esri 文件地理数据库": "New Esri file geodatabase",
    "Esri 文件地理数据库 (*.gdb)": "Esri file geodatabase (*.gdb)",
    "文件已存在，请换个名称": "File already exists, choose another name",
    "已新建 Esri 文件地理数据库：{}": "Esri file geodatabase created: {}",
    "新建 GeoPackage 数据库…": "New GeoPackage database…",
    "绘制": "Drawing",
    "标注": "Labeling",
    "混合模式": "Blend mode",
    "渲染方式": "Renderer",
    "单一符号": "Single symbol",
    "唯一值": "Unique values",
    "分级": "Graduated",
    "选择色带（唯一值 / 分级渲染配色）":
        "Pick color ramp (for categorized / graduated rendering)",
    "色带用于唯一值 / 分级渲染，请先切换渲染方式":
        "Color ramps apply to categorized / graduated rendering; "
        "switch the renderer first",
    "当前渲染方式不支持色带":
        "The current renderer does not support color ramps",
    "已应用色带：{}": "Color ramp applied: {}",
    "渲染方式已切换：{}": "Renderer switched: {}",
    "没有可用于分级的数值字段": "No numeric field available for "
        "graduated rendering",
    "无法计算字段数值范围": "Cannot compute the field value range",
    "字体": "Font",
    "位置": "Placement",
    "居中覆盖": "Centered",
    "上方": "Above",
    "下方": "Below",
    "左侧": "Left",
    "右侧": "Right",
    "线上": "On line",
    "沿曲线": "Curved",
    "内部中心": "Center inside",
    "已选择的要素": "Selected features",
    "已复制测量结果": "Measurement results copied",
    "已复制换算结果": "Conversion result copied",
    "URL 模板：": "URL template:",
    "如 https://…/{z}/{x}/{y}.png": "e.g. https://…/{z}/{x}/{y}.png",
    "图层名称：": "Layer name:",
    "留空则按 URL 自动取名": "Leave empty to derive from URL",
    "坐标系：": "CRS:",
    "最大层级：": "Max zoom level:",
    "不限制": "Unlimited",
    "瓦片最大缩放级别，0 = 不限制":
        "Maximum tile zoom level, 0 = unlimited",
    "URL 模板必须包含 {x} {y} {z} 占位符（TMS 服务的行号也可写成 {-y}）":
        "The URL template needs the {x} {y} {z} placeholders "
        "(TMS services may spell the row as {-y})",    "未保存的工程": "Unsaved project",
    "当前工程有未保存的更改，是否保存？":
        "The project has unsaved changes. Save them?",
    "该图层是在线瓦片，不支持直方图":
        "This is an online tile layer; histograms are not supported",
    "在线瓦片图层不支持直方图":
        "Online tile layers do not support histograms",
    "在线瓦片…": "Online tiles…",
    "在线瓦片": "Online tiles",
    "底图": "Basemap",
    "瓦片 {0}": "tiles {0}",
    "添加在线瓦片图层（XYZ URL 模板）":
        "Add an online tile layer (XYZ URL template)",
    "Web 墨卡托 (EPSG:3857)": "Web Mercator (EPSG:3857)",
    "经纬度 (EPSG:4326)": "Latitude/Longitude (EPSG:4326)",
    "在线瓦片地址无效：{0}": "Invalid online tile URL: {0}",
    "底图已在工程中：{0}": "Basemap already in the project: {0}",
    "已加载在线底图：{0}": "Basemap loaded: {0}",
    "已复制图层：{}，可在分组或主树空白处粘贴":
        "Layer copied: {}. Paste it into a group or the tree root",
    "图层副本创建失败": "Failed to create layer copy",
    "副本": "copy",
    "属性（所选要素）": "Attributes (selected features)",
    "Selected features attributes": "Selected features attributes",
    "图层：{}　已选 {} 个要素（单击行定位要素）":
        "Layer: {}　{} feature(s) selected (click a row to locate)",
    "选择集过大，仅显示前 {} 个要素的属性":
        "Selection too large; showing attributes of the first {} features only",

    "功能区": "Ribbon",
    "最近打开": "Recent",
    "（暂无记录）": "(no records)",
    "清空记录": "Clear list",
    "清空日志": "Clear log",
    "添加图层（{}）": "Add layer ({})",
    "该文件不是受支持的数据源": "This file is not a supported data source",
    "属性表": "Attribute table",
    "属性表面板初始化失败：{}": "Failed to initialise the attribute table: {}",
    "选择或双击一个矢量图层以查看属性表":
        "Select or double-click a vector layer to view its attribute table",
    "搜索功能…（如「添加矢量」或 Ctrl+Shift+V）":
        "Search commands… (e.g. “Add vector” or Ctrl+Shift+V)",
    "等待测量…": "Waiting for measurement…",
    "关闭并退出测量": "Close and exit measuring",
    "在地图上实时显示结果": "Show results on the map live",
    "取消勾选后只在本窗显示，画布上不再浮出分段与总长":
        "Uncheck to keep results in this panel only; no segment or total "
        "labels will be drawn on the map",
    "清掉当前测量，重新开始": "Discard the current measurement and start over",
    "Esc 取消 · 双击结束": "Esc cancels · double-click finishes",
    "算法说明": "Algorithm description",
    "（暂无说明）": "(no description yet)",
    "栅格符号系统 — {0}": "Raster symbology — {0}",
    "符号系统…": "Symbology…",
    "色带（单波段着色）": "Color ramp (single band)",
    "反向": "Invert",
    "把色带高低端对调（如高程用深色表示高处时）":
        "Swap the ramp's low and high ends (e.g. darker = higher)",
    "规则": "Rules",
    "兜底规则": "Else rule",
    "无条件匹配 —— 用来兜住前面所有规则都不匹配的要素，通常放在最后一条":
        "Matches unconditionally \u2014 use it for features that no earlier "
        "rule matched; usually the last rule",
    "规则按顺序从上往下判定，第一个匹配的生效；表达式留空 = 匹配全部。":
        "Rules are evaluated top to bottom and the first match wins. "
        "An empty expression matches everything.",
    "过滤表达式": "Filter expression",
    "（兜底）": "(else)",
    "全部要素": "All features",
    "规则 {0}": "Rule {0}",
    "等间隔": "Equal interval",
    "分位数": "Quantile",
    "自然断点": "Natural breaks (Jenks)",
    "美观断点": "Pretty breaks",
    "对数刻度": "Logarithmic",
    "重采样（放大）": "Resampling (zoom in)",
    "重采样（缩小）": "Resampling (zoom out)",
    "最近邻": "Nearest neighbour",
    "双线性": "Bilinear",
    "双三次（Cubic）": "Cubic",
    "三次样条": "Cubic spline",
    "Lanczos": "Lanczos",
    "平均值": "Average",
    "高斯": "Gauss",
    "众数": "Mode",
    "分类 / 离散值用最近邻；连续影像放大可用双三次 / Lanczos。缩小时用「平均值」等比最近邻更干净（代价是细节变软）。":
        "Nearest keeps boundaries \u2014 use it for classified / discrete "
        "values. Cubic or Lanczos sharpen continuous imagery when zooming in. "
        "\u201cAverage\u201d is cleaner than nearest when zooming out "
        "(fine detail gets softer).",
    "不设色带 = 按灰度显示。连续数据（高程 / 温度）建议选一条色带，起伏更易读。":
        "No ramp = grayscale. For continuous data (elevation, temperature) "
        "a ramp makes the variation much easier to read.",
    "按拉伸后的值在选定的色带上取色，低值端在左、高值端在右。":
        "Colors are taken from the ramp by stretched value; low end on the "
        "left, high end on the right.",
    "当前是「自动（三波段彩色）」，色带不生效；请在上方「波段」里指定单波段。":
        "Currently on “Auto (3-band color)”, so the ramp has no effect. "
        "Pick a single band above to use a ramp.",
    "文件已不存在：{}": "File no longer exists: {}",

    "撤销": "Undo",
    "重做": "Redo",
    "撤销：{}": "Undo: {}",
    "重做：{}": "Redo: {}",
    "撤销活动图层最近一次编辑操作 (Ctrl+Z)":
        "Undo the last edit on the active layer (Ctrl+Z)",
    "重做活动图层上一次被撤销的编辑 (Ctrl+Y)":
        "Redo the last undone edit on the active layer (Ctrl+Y)",
    "没有可撤销的编辑操作": "Nothing to undo",
    "没有可重做的编辑操作": "Nothing to redo",

    "选择": "Selection",
    "选择统计": "Selection statistics",
    "选择统计面板不可用": "Selection statistics panel unavailable",
    "选择：{} → {} 个要素": "Selection: {} -> {} features",
    "“{}”当前选中 {} 个要素":
        "{} now has {} features selected",
    "反选：{} → {} 个要素": "Inverted selection on {}: {} features",
    "已清除“{}”的选择": "Cleared the selection on {}",

    "按属性选择": "Select by attributes",
    "按属性选择 — {0}": "Select by attributes — {0}",
    "当前已选：": "Selected: ",
    "选择方式：": "Method: ",
    "新建=丢弃旧选择；添加=并集；移除=差集；在当前选择中选择=交集":
        "New = replace; Add = union; Remove = difference; "
        "Select within = intersection",
    "请先输入一个表达式": "Enter an expression first",
    "表达式错误：{}": "Expression error: {}",
    "选择失败：{}": "Selection failed: {}",
    "按属性选择：命中 {} 个要素（共选中 {} 个）":
        "Select by attributes: {} matched ({} selected in total)",
    "按属性选择 [{}]：{} → 命中 {} 个":
        "Select by attributes [{}]: {} -> {} matched",

    "完成": "Finish",
    "撤回": "Undo",
    "还原": "Redo",

    "新建数据库": "New database",
    "新建数据库：地理包（.gpkg）/ Esri 文件地理数据库（.gdb）":
        "New database: GeoPackage (.gpkg) / Esri file geodatabase (.gdb)",
    "插入形状": "Insert shape",
    "插入形状：点 / 线 / 面（自动进入编辑，处于添加要素状态）":
        "Insert shape: point / line / polygon (starts editing "
        "automatically, in add-feature state)",
    "插入形状：点 / 线 / 面（自动创建图形图层、进入编辑并处于添加要素状态）":
        "Insert shape: point / line / polygon (creates the scratch "
        "layer, starts editing and enters add-feature state)",

    "按位置选择": "Select by location",
    "按位置选择…": "Select by location…",
    "按空间位置筛选要素：与参考图层相交 / 包含 / 位于其中 / 接触 / 距离内":
        "Select features by location: intersect / contain / within / "
        "touch / within distance of a reference layer",
    "目标图层：": "Target layer: ",
    "参考图层：": "Reference layer: ",
    "空间关系：": "Spatial relationship: ",
    "包含": "Contain",
    "位于其中": "Are within",
    "接触": "Touch",
    "距离内": "Within distance",
    "距离：": "Distance: ",
    "目标要素到参考要素的距离阈值（目标图层坐标系单位）":
        "Distance threshold from target to reference features "
        "(target layer CRS units)",
    "请先选择有效的目标图层": "Choose a valid target layer first",
    "请先选择有效的参考图层": "Choose a valid reference layer first",
    "读取参考图层失败：{}": "Failed to read the reference layer: {}",
    "参考图层没有可用要素": "The reference layer has no usable features",
    "按位置选择失败：{}": "Select by location failed: {}",
    "按位置选择：命中 {} 个要素（共选中 {} 个）":
        "Select by location: {} matched ({} selected in total)",
    "按位置选择 [{}]：{} {} [{}] → 命中 {} 个":
        "Select by location [{}]: {} {} [{}] -> {} matched",
    "距离内 {}": "within {}",

    "输入坐标（每行一个：X, Y）：": "Input coordinates (one X, Y per line):",
    "如 116.397128, 39.916527\n逗号 / 空格 / 制表符分隔均可，可一次粘贴多行":
        "e.g. 116.397128, 39.916527\nComma / space / tab separated; "
        "paste multiple lines at once",
    "地图取点": "Pick from map",
    "切换到地图取点：在地图上单击取坐标（可连续取点，Esc 结束），"
    "坐标自动换算到源坐标系并追加":
        "Switch to map picking: click the map to grab coordinates "
        "(click repeatedly, Esc to finish); points are converted to "
        "the source CRS and appended",
    "输入或取点后自动换算": "Converts automatically on input or pick",
    "换算结果（X, Y）：": "Converted (X, Y):",
    "清空": "Clear",
    "在地图上单击取点（可连续取点，Esc 结束）":
        "Click the map to pick points (repeatedly; Esc to finish)",
    "取点换算失败：{}": "Failed to convert the picked point: {}",
    "# 请选择有效的坐标系": "# Choose valid CRS first",
    "# 坐标系不可用：{}": "# Invalid CRS: {}",
    "# 第{}行格式错误（应为 X, Y）":
        "# Line {}: bad format (expected X, Y)",
    "# 第{}行无法解析": "# Line {}: unparseable",
    "# 第{}行换算失败：{}": "# Line {}: transform failed: {}",
    "已换算 {} 组": "{} point(s) converted",
    "已换算 {0} 组，{1} 组失败": "{0} point(s) converted, {1} failed",

    "添加点": "Add point",
    "地图显示": "Show on map",
    "清空点": "Clear points",
    "导出 CSV": "Export CSV",
    "导出坐标点": "Export points",
    "序号": "No.",
    "输入点": "Input point",
    "输出点": "Output point",
    "输入(X,Y)": "Input (X,Y)",
    "输出(X,Y)": "Output (X,Y)",
    "输入（源坐标系，X,Y）": "Input (source CRS, X,Y)",
    "输出（目标坐标系，X,Y）": "Output (target CRS, X,Y)",
    "输入点：X,Y；多个点用分号隔开，例如 116.39,39.90; 121.47,31.23":
        "Points as X,Y; separate several points with semicolons, "
        "e.g. 116.39,39.90; 121.47,31.23",
    "请输入至少一个点（X,Y；多个点用分号隔开）":
        "Enter at least one point (X,Y; several points separated by semicolons)",
    "没有可导出的坐标点": "No points to export",
    "已导出：{}": "Exported: {}",
    "导出失败：{}": "Export failed: {}",
    "转换失败：{}": "Transform failed: {}",
    "当前没有激活的地图视图，无法取点":
        "No active map view — cannot pick points",
    "CSV 文件 (*.csv);;所有文件 (*.*)":
        "CSV files (*.csv);;All files (*.*)",

    "重新统计当前选择": "Recompute statistics for the current selection",
    "工程里没有矢量图层": "No vector layer in the project",
    "选中 {} / {} 个要素": "{} of {} features selected",
    "未选中任何要素": "No feature selected",
    "只统计数值字段；文本字段的去重计数见「计数」列。":
        "Numeric fields only; for text fields see the Count column.",
    "{} 个非空值，另跳过 {} 个空值":
        "{} non-null values, {} null values skipped",

    "GmaGIS": "GmaGIS",
    "把 shapefile / GeoPackage / GeoTIFF 拖进画布即可加载；"
    "顶部搜索框可定位图层、算法、书签与经纬度坐标。":
        "Drop shapefiles / GeoPackages / GeoTIFFs onto the canvas to load "
        "them; the search box up top locates layers, algorithms, bookmarks "
        "and coordinates.",

    "关闭": "Close",
    "关闭其它页签": "Close other tabs",
    "关闭全部页签": "Close all tabs",
    "应用": "Apply",
    "删除失败": "Delete failed",
    "新组": "New group",
    "新建书签": "New bookmark",
    "另存为…": "Save as…",
    "导出画布快照": "Export canvas image",
    "是": "Yes",
    "否": "No",
    "识别": "Identification",
    "请先在列表中选择一个有效的坐标系。":
        "Select a valid coordinate reference system from the list first.",
    "地图画布背景色；选择“跟随主题”时无效":
        "Map canvas background colour; ignored when “Follow theme” is on",
    "状态栏光标坐标的小数位数；地理坐标系建议 6 位":
        "Decimal places for the cursor coordinates in the status bar; "
        "6 is recommended for geographic CRS",
    "快捷键速查表": "Keyboard shortcuts",
    "快速修改图层显示颜色（色块右键同款）":
        "Change the layer colour quickly (same as right-clicking the "
        "colour swatch)",
    "用 SQL 表达式只显示满足要求的要素":
        "Show only the features matching an SQL expression",
    "透明度(T)": "Transparency(T)",
    "栅格直方图(H)": "Raster histogram(H)",
    "点击选择一个坐标系（Ctrl+Shift+K）。":
        "Click to choose a CRS (Ctrl+Shift+K).",
    "点击修改；右键查看更多操作（Ctrl+Shift+K）。":
        "Click to change; right-click for more actions (Ctrl+Shift+K).",
    "<b>地图坐标系</b>：尚未设置": "<b>Map CRS</b>: not set",
    "已启用「即时投影变换」：不同坐标系的图层会自动重投影到本坐标系后叠加。":
        "On-the-fly reprojection is on: layers in other CRSs are "
        "reprojected to this CRS before being drawn.",

    "添加矢量图层": "Add Vector Layer",
    "添加栅格图层": "Add Raster Layer",
    "矢量数据 ({0});;所有文件 (*)": "Vector data ({0});;All files (*)",
    "栅格数据 ({0});;所有文件 (*)": "Raster data ({0});;All files (*)",
    "空间数据 ({0});;所有文件 (*)": "Spatial data ({0});;All files (*)",
    "所有文件 (*)": "All files (*)",
    "已加载 {0} 个图层": "{0} layer(s) loaded",
    "{0} 个文件加载失败": "{0} file(s) failed to load",
    "已加载 {0} 个图层，{1} 个失败":
        "{0} layer(s) loaded, {1} failed",
    "已加载：{0}（{1}）": "Loaded: {0} ({1})",
    "{0}，{1}": "{0}, {1}",
    "加载失败：{0}": "Load failed: {0}",
    "未知错误": "unknown error",
    "导入失败：{0}": "Import failed: {0}",
    "已导入 {0} 个点": "Imported {0} point(s)",
    "从路径添加": "Add from Path",
    "每行一个文件路径（也可直接粘贴资源管理器里复制的路径）：":
        "One file path per line (you can also paste paths copied from "
        "File Explorer):",
    "添加文本数据 (CSV)": "Add Delimited Text Layer (CSV)",
    "数据库 / Web 服务": "Database / Web Service",
    "连接串或服务地址（PostgreSQL / GPKG / WFS / GeoJSON 服务均可）：":
        "Connection string or service URL (PostgreSQL / GPKG / WFS / "
        "GeoJSON all work):",
    "把含经纬度字段的 CSV / 文本表转为点图层":
        "Turn a CSV / text table with longitude and latitude columns "
        "into a point layer",
    "添加分隔文本数据（CSV / TSV / TXT），按经纬度列转成点图层":
        "Add delimited text data (CSV / TSV / TXT) as a point layer "
        "built from its longitude / latitude columns",
    "打开数据源浏览器：本地文件、数据库、OGC 服务":
        "Open the data source browser: local files, databases, "
        "OGC services",
    "从路径输入数据源添加": "Add a data source by typing its path",
    "新建矢量 / 数据库文件": "Create a new vector / database file",
    "新建形状文件（.shp）": "New Shapefile (.shp)",
    "新建地理包（.gpkg）图层": "New GeoPackage (.gpkg) layer",
    "新建 Esri 文件地理数据库（.gdb）":
        "New Esri File Geodatabase (.gdb)",
    "新建矢量图层": "New Vector Layer",
    "新建矢量文件": "New Vector File",
    "新建图层": "New layer",
    "新建形状文件并绘制点 / 线 / 面要素":
        "Create a vector layer and draw point / line / polygon features",
    "新建矢量图层并绘制点 / 线 / 面要素":
        "Create a vector layer and draw point / line / polygon features",
    "新建点图层并绘制要素": "Create a point layer and draw features",
    "新建线图层并绘制要素": "Create a line layer and draw features",
    "新建面图层并绘制要素":
        "Create a polygon layer and draw features",
    "新建可绘制点 / 线 / 面的图形图层":
        "Create a drawable point / line / polygon graphic layer",
    "添加图形图层": "Add Graphic Layer",
    "图形图层先建在内存里，绘制完成后保存时再选路径。":
        "Graphic layers are created in memory first; you pick a path "
        "when you save them.",
    "新建点图层": "New point layer",
    "新建线图层": "New line layer",
    "新建面图层": "New polygon layer",
    "新建{0}图层": "New {0} layer",
    "已新建图层：{0}": "New layer created: {0}",
    "已新建：{0}（{1}）": "Created: {0} ({1})",
    "已新建 {0} 图层，在地图上单击开始绘制（保存时再选路径）":
        "New {0} layer created. Click on the map to start drawing "
        "(you will choose a path when saving).",
    "无法创建数据源：{0}": "Cannot create data source: {0}",
    "保存图层 — {0}": "Save Layer — {0}",
    "{0}：图层里还没有要素，未保存":
        "{0}: the layer has no features yet, nothing saved",
    "浏览：拖动平移，滚轮缩放": "Pan: drag to pan, scroll wheel to zoom",
    "地图工具「{}」已激活": "Map tool \"{}\" activated",
    "地图工具「{}」已激活（占位）":
        "Map tool \"{}\" activated (placeholder)",
    "当前选择：": "Current selection: ",
    "没有选中要素": "No features selected",

    "导入分隔文本数据": "Import Delimited Text",
    "选择 CSV / TSV / TXT 文件": "Select a CSV / TSV / TXT file",
    "选择分隔文本数据": "Select delimited text data",
    "分隔文本 (*.csv *.tsv *.txt);;所有文件 (*)":
        "Delimited text (*.csv *.tsv *.txt);;All files (*)",
    "分隔符": "Delimiter",
    "X / 经度列": "X / longitude column",
    "Y / 纬度列": "Y / latitude column",
    "图层名": "Layer name",
    "留空则用文件名": "Leave empty to use the file name",
    "数据预览": "Data preview",
    "导入": "Import",
    "已探测：{}": "Detected: {}",
    "读取失败：{}": "Read failed: {}",
    "按所选编码 / 分隔符解析失败：{}":
        "Parsing with the selected encoding / delimiter failed: {}",
    "⚠ {}": "⚠ {}",
    "⚠ {} 条记录可用，{}": "⚠ {} record(s) usable, {}",
    "✓ {} 条记录可导入": "✓ {} record(s) ready to import",
    "⚠ X 列与 Y 列不能是同一列":
        "⚠ The X and Y columns must be different",

    "请先选择一个图层": "Select a layer first",
    "缩放失败：{0}": "Zoom failed: {0}",
    "移除图层": "Remove Layer",
    "「{0}」有未保存的编辑，移除后这些改动会丢失。\n确定移除吗？":
        "\"{0}\" has unsaved edits that will be lost if you remove it.\n"
        "Remove it anyway?",
    "「{0}」还没有保存到文件，没有路径可复制":
        "\"{0}\" has not been saved to a file yet, so there is no path "
        "to copy",
    "已复制路径：{0}": "Path copied: {0}",
    "定位到": "Go to Coordinates",
    "输入坐标，用逗号或空格分隔（例：116.4, 39.9）；\n按地图坐标系解释。":
        "Enter coordinates separated by a comma or space "
        "(e.g. 116.4, 39.9);\nthey are interpreted in the project CRS.",
    "坐标格式无法识别：{0}": "Unrecognized coordinate format: {0}",
    "定位失败：{0}": "Go-to failed: {0}",
    "已定位到 {0}, {1}": "Centered on {0}, {1}",
    "组 {0}": "Group {0}",
    "新建分组失败：{0}": "Could not create group: {0}",

    "未保存的更改": "Unsaved Changes",
    "工程有未保存的更改，要先保存吗？":
        "The project has unsaved changes. Save them first?",
    "已新建工程": "New project created",
    "工程另存为": "Save Project As",
    "未命名工程": "Untitled Project",
    "内存工程": "In-memory Project",
    "（内存工程，尚未保存到文件）": "(In-memory project, not saved to a file yet)",
    "尚未保存到文件": "not saved to a file yet",
    "未设置": "not set",
    "打开工程": "Open Project",
    "GmaGIS 工程 (*.ggs);;所有文件 (*)":
        "GmaGIS project (*.ggs);;All files (*)",
    "保存工程失败：{0}": "Saving the project failed: {0}",
    "已保存工程：{0}（{1} 个图层）":
        "Project saved: {0} ({1} layer(s))",
    "已保存工程：{0}（{1} 个图层）；另有 {2} 个未落盘的图层未记入，请先保存这些图层":
        "Project saved: {0} ({1} layer(s)); {2} layer(s) not yet on "
        "disk were skipped — save those layers first",
    "工程已保存 → {0}": "Project saved -> {0}",
    "打开工程失败：{0}": "Opening the project failed: {0}",
    "已打开工程：{0} 个图层；{1} 个未能恢复":
        "Project opened: {0} layer(s); {1} could not be restored",
    "已打开工程：{0} 个图层": "Project opened: {0} layer(s)",
    "工程加载：{0}": "Project load: {0}",
    "工程：{0}": "Project: {0}",
    "{0} 个图层 · {1}": "{0} layer(s) · {1}",
    "文件：{0}": "File: {0}",

    "2-2 + 激活态容器底色": "2-2 + active container background",
    "ArcGIS Pro 风格功能区界面，提供图层管理、要素编辑、量算、坐标转换与空间分析能力；"
    "数据格式支持 Shapefile / GeoPackage / GeoJSON / GeoTIFF 与在线瓦片底图。":
        "An ArcGIS Pro style ribbon interface with layer management, feature "
        "editing, measurement, coordinate transformation and spatial analysis; "
        "supports Shapefile / GeoPackage / GeoJSON / GeoTIFF and online tile "
        "basemaps.",
    "CRS 不一致：{0} 是 {1}，工程是 {2}，将实时投影显示":
        "CRS mismatch: {0} is {1} but the project is {2}; "
        "reprojected on the fly",
    "视图坐标系已设为 {0}（取自首个图层：{1}）":
        "View CRS set to {0} (taken from the first layer: {1})",
    "Esri 地形图": "Esri Terrain",
    "Esri 影像": "Esri Imagery",
    "Esri 暗黑地图": "Esri Dark Gray Canvas",
    "Esri 浅色地图": "Esri Light Gray Canvas",
    "OSM 街道地图": "OSM Street Map",
    "OTM 等高线地形图": "OTM Topographic Contours",
    "[错误] 样式加载失败：{}": "[Error] Loading the style failed: {}",
    "[错误] 欢迎层初始化失败：{}":
        "[Error] Initialising the welcome layer failed: {}",
    "{0} {1} 个要素，当前共选中 {2} 个":
        "{0} {1} feature(s); {2} selected in total",
    "{0} 个点": "{0} point(s)",
    "{0}：未声明 CRS，按图层自身坐标画":
        "{0}: no CRS declared, drawing in the layer's own coordinates",
    "{}：功能占位，将在 GIS 里程碑接入":
        "{}: placeholder — to be implemented in a later milestone",
    "…（共 {0} 项）": "… ({0} item(s) in total)",
    "「{0}」是栅格图层，栅格属性表见 M2 之后的里程碑":
        "\u201c{0}\u201d is a raster layer; the raster attribute table arrives "
        "in a later milestone",
    "「{0}」有未保存的编辑，请先点「保存」或「放弃更改」":
        "\u201c{0}\u201d has unsaved edits; click \u201cSave\u201d or "
        "\u201cDiscard changes\u201d first",
    "「{0}」还没有保存到文件，无法粘贴":
        "\u201c{0}\u201d has not been saved to a file yet and cannot be pasted",
    "三行骨架整体化，点任意处弹菜单":
        "Render the three-row skeleton as a whole; click anywhere for the menu",
    "上限": "Max",
    "下限": "Min",
    "不支持的文件类型：{0}": "Unsupported file type: {0}",
    "不限": "Any",
    "与锚点间距 (px)": "Distance from anchor (px)",
    "与锚点间距": "Distance from anchor",
    "专业桌面 GIS · 空间数据管理、制图与分析":
        "Professional desktop GIS · spatial data management, mapping and analysis",
    "没有打开的视图": "No view open",
    "新建一个视图开始工作：地图用于浏览与编辑空间数据，"
    "布局用于排版出图，模型构建器用于搭建数据处理流程。":
        "Create a view to get started: Map for browsing and editing spatial "
        "data, Layout for cartography, Model Builder for data processing.",
    "主目录": "Home",
    "交集": "Intersect",
    "仅中点/内部点": "Midpoint / interior point only",
    "仅显示选中要素": "Show selected features only",
    "例如：value > 100 AND name LIKE 'P%'":
        "For example: value > 100 AND name LIKE 'P%'",
    "保存失败：{0}": "Save failed: {0}",
    "修改几何": "Change geometry",
    "修改属性 {0}": "Change attribute {0}",
    "候选位置": "Candidate positions",
    "光标在地图坐标系下的 XY 坐标": "Cursor XY in map coordinates",
    "全选": "Select all",
    "全部展开": "Expand all",
    "全部折叠": "Collapse all",
    "共 {0} 个要素": "{0} feature(s) in total",
    "共选中 {0} 个要素，分布在 {1} 个图层":
        "{0} feature(s) selected across {1} layer(s)",
    "关于对话框加载失败：{}": "Loading the About dialog failed: {}",
    "关闭提示": "Dismiss the message",
    "关闭欢迎页": "Close the welcome page",
    "减选": "Remove from selection",
    "几何编辑：{0}，影响 {1} 个要素":
        "Geometry edit: {0}, {1} feature(s) affected",
    "几何操作": "Geometry operations",
    "几何量": "Geometry",
    "出图(&X)": "Print(&X)",
    "分析": "Analysis",
    "分类": "Classification",
    "分类（唯一值）": "Categorised (unique values)",
    "分级方法": "Classification method",
    "删除 %d 个要素": "Delete %d feature(s)",
    "删除折点": "Delete vertex",
    "删除要素：单击要素即删除；有选择集时删除整个选择集":
        "Delete feature: click a feature to delete it; with an active "
        "selection the whole selection is deleted",
    "剪贴板": "Clipboard",
    "剪贴板里没有图层": "There is no layer on the clipboard",
    "加载失败：{0} ({1})": "Loading failed: {0} ({1})",
    "加选": "Add to selection",
    "匹配 {0} / {1} 个要素": "Matched {0} / {1} feature(s)",
    "十字": "Cross",
    "十进制度": "Decimal degrees",
    "升序": "Ascending",
    "参考线没有穿过任何选中要素，未做改动":
        "The reference line did not cross any selected feature; nothing changed",
    "叉号": "X",
    "反选": "Invert selection",
    "反选（选中不匹配的要素）": "Invert (select the features that do not match)",
    "清除选择": "Clear selection",
    "合并失败：{0}": "Merge failed: {0}",
    "合计": "Total",
    "向下还原": "Restore down",
    "向当前工程添加图层 / 数据": "Add a layer / data to the current project",
    "命中 {0} 个要素": "{0} feature(s) hit",
    "图例预览": "Legend preview",
    "图层(&L)": "Layer(&L)",
    "图层几何类型：{0}　要素数：{1}":
        "Layer geometry: {0}　Feature count: {1}",
    "圆圈": "Circle",
    "在地图上单击取一个参考点；Esc 取消":
        "Click on the map to pick a reference point; Esc to cancel",
    "在地图上画一条参考线：左键落点；双击 / 右键 / 回车结束；Esc 取消":
        "Draw a reference line on the map: left-click to add points; "
        "double-click / right-click / Enter to finish; Esc to cancel",
    "地图": "Map",
    "地图(&M)": "Map(&M)",
    "新建地图": "New Map",
    "地图 {0}": "Map {0}",
    "地图名称": "Map name",
    "新建地图失败：{0}": "Failed to create map: {0}",
    "确定要关闭当前视图吗？": "Close the current view?",
    "地图坐标": "Map coordinates",
    "地图显示选项": "Map display options",
    "地理处理": "Geoprocessing",
    "坐标小数位": "Coordinate decimals",
    "坐标显示格式": "Coordinate display format",
    "坐标格式：{}": "Coordinate format: {}",
    "坐标系切换将在 GIS 里程碑接入（{}）":
        "CRS switching arrives in a later milestone ({})",
    "坐标系页签在 GIS 里程碑接入后生效。":
        "The CRS tab takes effect once the GIS milestone lands.",
    "处理(&P)": "Processing(&P)",
    "处理工具箱": "Processing toolbox",
    "复制": "Copy",
    "复制失败：{0}": "Copy failed: {0}",
    "大地线": "Geodesic",
    "字体与配色": "Font and colours",
    "容差（地图单位）": "Tolerance (map units)",
    "导出(&E)": "Export(&E)",
    "导航": "Navigation",
    "小图标": "Small icons",
    "展开功能区": "Expand the ribbon",
    "属性表 — {0}": "Attribute table — {0}",
    "工具": "Tools",
    "工具箱": "Toolbox",
    "工程(&F)": "Project(&F)",
    "地图坐标系（GIS 里程碑接入后可修改）":
        "Map CRS (editable once the GIS milestone lands)",
    "工程属性对话框加载失败：{}":
        "Loading the project properties dialog failed: {}",
    "工程属性已保存": "Project properties saved",
    "工程标题": "Project title",
    "工程里还没有矢量图层。先「添加数据」再回来配样式。":
        "The project has no vector layers yet. Add data first, then come back "
        "to style it.",
    "已保存 {0} 个图层的编辑": "Saved edits for {0} layer(s)",
    "已保存编辑：{0} → {1}": "Edits saved: {0} -> {1}",
    "正在保存编辑：{0}": "Saving edits: {0}",
    "正在写盘…": "Writing to disk...",
    "写入失败": "write failed",
    "已全选「{0}」的 {1} 个要素":
        "Selected all {1} feature(s) of \u201c{0}\u201d",
    "已关闭「{0}」的标注": "Labels turned off for \u201c{0}\u201d",
    "已剪切图层：{0}（按 Ctrl+V 可恢复）":
        "Layer cut: {0} (press Ctrl+V to restore)",
    "已反选「{0}」": "Inverted the selection of \u201c{0}\u201d",
    "已合并为多部件要素": "Merged into a multi-part feature",
    "已开启「{0}」的标注（字段：{1}）":
        "Labels turned on for \u201c{0}\u201d (field: {1})",
    "已拆出 {0} 个部件": "Extracted {0} part(s)",
    "已放弃 {0} 个图层的未保存编辑":
        "Discarded unsaved edits for {0} layer(s)",
    "已更新「{0}」的标注设置": "Label settings updated for \u201c{0}\u201d",
    "已概化 {0} 个要素": "Simplified {0} feature(s)",
    "已清除全部选择": "Cleared the whole selection",
    "已清除选择": "Selection cleared",
    "已清除量测": "Measurements cleared",
    "已移除：{0}": "Removed: {0}",
    "已粘贴图层：{0}": "Layer pasted: {0}",
    "已融合 {0} 个要素": "Dissolved {0} feature(s)",
    "带菜单": "With menu",
    "帮助(&H)": "Help(&H)",
    "平均": "Mean",
    "平面": "Planar",
    "应用程序": "Application",
    "应用程序选项": "Application options",
    "度分": "Degrees minutes",
    "度分秒": "Degrees minutes seconds",
    "当前工程（下拉查看工程信息）":
        "Current project (click to view project info)",
    "当前显示 {0} 行": "Showing {0} row(s)",
    "当前设置": "Current settings",
    "快捷键速查表加载失败：{}":
        "Loading the shortcut cheat sheet failed: {}",
    "总长度": "Total length",
    "总面积": "Total area",
    "恢复默认样式": "Restore the default style",
    "所有字段": "All fields",
    "所选要素不是多部件": "The selected feature is not multi-part",
    "打断只对线图层有效": "Break only works on line layers",
    "把窗口大小与所有面板的位置 / 尺寸恢复为默认排布":
        "Restore the window size and every panel's position / size to the "
        "default layout",
    "折叠功能区": "Collapse the ribbon",
    "折点编辑": "Vertex editing",
    "折点工具不可用": "The vertex tool is not available",
    "折点样式对编辑页的折点选择 / 拖动生效。":
        "The vertex style applies to vertex selection / dragging on the edit tab.",
    "折点编辑：拖动折点；双击线段加点；Delete 删除折点":
        "Vertex editing: drag a vertex; double-click a segment to add one; "
        "Delete to remove one",
    "折点：单击折点即删除": "Vertex: click a vertex to delete it",
    "折点：单击选中折点（Ctrl 加选 / 减选）":
        "Vertex: click to select a vertex (Ctrl to add / remove)",
    "折点：在线段上单击插入新折点":
        "Vertex: click on a segment to insert a new vertex",
    "折点：按住折点拖动，整组一起移动":
        "Vertex: drag a vertex to move the whole group together",
    "拖入 .shp / .geojson / .tif 开始，或用「添加数据」":
        "Drop a .shp / .geojson / .tif here to start, or use \u201cAdd data\u201d",
    "按 {0} {1}排序": "Sort by {0} {1}",
    "按住中键 / 空格拖动": "Hold the middle button / Space and drag",
    "按图层": "By layer",
    "按表达式筛选，例如 value > 100 AND name LIKE 'P%'":
        "Filter by expression, e.g. value > 100 AND name LIKE 'P%'",
    "按表达式选中 {0} 个要素": "Selected {0} feature(s) by expression",
    "按表达式选择 — {0}": "Select by expression — {0}",
    "按表达式选择": "Select by expression",
    "没有可用的矢量图层": "No vector layer available",
    "捕捉": "Snapping",
    "捕捉设置：选择要吸附到的几何部位":
        "Snapping: pick the part of the geometry to snap to",
    "捕捉：打开后鼠标落点吸附到几何的指定部位":
        "Snapping: snap the cursor to the chosen part of the geometry",
    "描边宽度 (px)": "Stroke width (px)",
    "描边颜色": "Stroke colour",
    "操作失败：{0}": "Operation failed: {0}",
    "放弃当前图层所有未保存的编辑":
        "Discard all unsaved edits on the current layer",
    "放弃更改": "Discard changes",
    "数值字段统计（当前图层）": "Numeric field statistics (current layer)",
    "整体按钮 + 激活态容器底色": "Whole button + active container background",
    "整体按钮，无激活底色": "Whole button, no active background",
    "文字颜色": "Text colour",
    "方块": "Square",
    "无": "None",
    "无法加载：{0}": "Cannot load: {0}",
    "无法对齐：参考线或要素无效":
        "Cannot align: the reference line or the features are invalid",
    "无菜单": "No menu",
    "显示范围": "Visibility range",
    "更多分组": "More groups",
    "更改当前工程的设置": "Change the settings of the current project",
    "替换 {0} 个要素": "Replace {0} feature(s)",
    "最大化": "Maximise",
    "最大比例尺 1:": "Max scale 1:",
    "最小化": "Minimise",
    "最小比例尺 1:": "Min scale 1:",
    "最小要素尺寸 (px)": "Minimum feature size (px)",
    "未命名图层": "Untitled layer",
    "未选中要素（已清空选择）": "No feature selected (selection cleared)",
    "本地磁盘 ({})": "Local disk ({})",
    "本页只记录工程的目标坐标系。真实投影变换需要 pyproj / GDAL 参与，"
    "属于 GIS 里程碑内容，当前阶段不会改写数据。":
        "This page only records the project's target CRS. Real reprojection "
        "needs pyproj / GDAL and belongs to a later GIS milestone; nothing "
        "rewrites the data at this stage.",
    "查询": "Query",
    "栅格图层样式见后续里程碑": "Raster layer styling arrives in a later milestone",
    "标注设置 — {0}": "Label settings — {0}",
    "标注设置失败：{0}": "Applying label settings failed: {0}",
    "标签": "Label",
    "样例按钮": "Sample button",
    "样例": "Sample",
    "只有图标：功能区里最窄的一档，文字只出现在悬停提示里":
        "Icon only: the narrowest slot in the ribbon; the text lives in the "
        "tooltip",
    "图标 + 文本：点一下直接执行，没有菜单":
        "Icon + text: a single click runs it, there is no menu",
    "图标 + 文本 + 下拉箭头：点主体执行，点右侧箭头弹菜单":
        "Icon + text + drop arrow: click the body to run, click the arrow to "
        "open the menu",
    "只有图标 + 下拉箭头：最窄的带菜单样式":
        "Icon only + drop arrow: the narrowest style that has a menu",
    "样式面板初始化失败：{}": "Initialising the symbology panel failed: {}",
    "框选地图要素": "Select features by rectangle",
    "框选缩放": "Zoom by rectangle",
    "正在加载界面…": "Loading the interface…",
    "正在加载：{0}": "Loading: {0}",
    "正在后台加载：{0}": "Loading in the background: {0}",
    "此处没有要素": "No feature here",
    "此处没有要素。换个位置或放大后再点一次。":
        "No feature here. Try another spot, or zoom in and click again.",
    "每层上限": "Max per layer",
    "1:——": "1:--",
    "比例": "Scale",
    "求值失败：{}": "Evaluation failed: {}",
    "没有可撤销的编辑": "Nothing to undo",
    "没有可重做的编辑": "Nothing to redo",
    "没有选中要素。选择工具：框选 / 点选 / 属性表勾选 / 按表达式选择。":
        "No feature selected. Selection tools: rectangle / click / attribute "
        "table checkbox / select by expression.",
    "没有需要保存的编辑": "No edits to save",
    "没有需要放弃的编辑": "No edits to discard",
    "沿线重复距离 (px)": "Repeat distance along the line (px)",
    "沿线重复距离": "Repeat distance along the line",
    "测量地图上的距离": "Measure distances on the map",
    "浏览器初始化失败：{}": "Initialising the browser failed: {}",
    "浮动 / 取消浮动": "Float / dock",
    "添加在线底图": "Add an online basemap",
    "添加折点": "Add vertex",
    "添加数据": "Add data",
    "添加数据…": "Add data…",
    "添加要素": "Add feature",
    "添加要素：左键落点；双击 / 右键 / 回车结束；Esc 取消":
        "Add feature: left-click to place points; double-click / right-click / "
        "Enter to finish; Esc to cancel",
    "点击选择颜色": "Click to pick a colour",
    "点图标执行当前已选项": "Clicking the icon runs the current selection",
    "点图标执行菜单首项": "Clicking the icon runs the first menu item",
    "点数": "Point count",
    "点要素不能分割或修整": "Point features cannot be split or reshaped",
    "用「识别要素」工具点击地图查看属性":
        "Use the \u201cIdentify features\u201d tool and click the map to "
        "inspect attributes",
    "画布底色": "Canvas background",
    "确定要退出 GmaGIS 吗？": "Are you sure you want to quit GmaGIS?",
    "移动 %d 个要素": "Move %d feature(s)",
    "移动折点": "Move vertex",
    "移动要素": "Move feature",
    "移动要素：拖动选中的要素（未选中时按下命中的要素）":
        "Move features: drag the selected features (or the feature you press "
        "on when nothing is selected)",
    "移除…": "Remove…",
    "移除": "Remove",
    "窗口布局已重置为默认。": "The window layout has been reset to the default.",
    "符号化": "Symbology",
    "符号化…": "Symbology…",
    "符号系统": "Symbology",
    "符号大小": "Symbol size",
    "筛选": "Filter",
    "类数": "Classes",
    "粘贴失败：{0}": "Paste failed: {0}",
    "粘贴失败：数据源不可用（{0}）":
        "Paste failed: the data source is unavailable ({0})",
    "线宽": "Line width",
    "统计面板初始化失败：{}": "Initialising the statistics panel failed: {}",
    "编辑(&E)": "Edit(&E)",
    "编辑会话": "Edit session",
    "缩放到选择": "Zoom to selection",
    "缩放至要素": "Zoom to feature",
    "色带": "Colour ramp",
    "灰度": "Grayscale (no ramp)",
    "地形": "Terrain",
    "紫-绿-黄": "Viridis",
    "黑-紫-黄": "Magma",
    "蓝-灰-黄": "Cividis",
    "黄-绿": "Yellow-green",
    "橙-红": "Orange-red",
    "蓝-绿": "Blue-green",
    "绿-蓝": "Green-blue",
    "蓝-紫": "Blue-purple",
    "紫-蓝": "Purple-blue",
    "黑-紫-橙": "Inferno",
    "蓝-绿-黄": "Plasma",
    "红-黄-蓝": "Red-yellow-blue",
    "红-黄-绿": "Red-yellow-green",
    "红-白-灰": "Red-white-grey",
    "紫-白-绿": "Purple-white-green",
    "粉-白-绿": "Pink-white-green",
    "高程": "Elevation (green \u2192 brown \u2192 white)",
    "植被": "Vegetation (brown \u2192 yellow \u2192 green)",
    "蓝-白-红": "Blue-White-Red (diverging)",
    "蓝": "Blue",
    "绿": "Green",
    "红": "Red",
    "反转色带": "Invert colour ramp",
    "颜色反转": "Invert colours",
    "翻转颜色": "Invert colours",
    "自定义…": "Customise\u2026",
    "设置配色方案格式…": "Set colour ramp format\u2026",
    "显示名称": "Show names",
    "配色方案编辑器": "Colour ramp editor",
    "连续配色方案": "Continuous colour ramp",
    "离散配色方案": "Discrete colour ramp",
    "橙": "Orange (light → dark)",
    "紫": "Purple (light → dark)",
    "黄-绿-蓝": "Yellow-green-blue",
    "黄-橙-红": "Yellow-orange-red",
    "红-白-蓝": "Red-white-blue (diverging)",
    "褐-白-青": "Brown-white-teal (diverging)",
    "紫-白-橙": "Purple-white-orange (diverging)",
    "连续：色标之间平滑过渡；离散：每个色标管一段（段内纯色块）":
        "Continuous: smooth between stops; Discrete: each stop owns "
        "a band (flat colour)",
    "配色方案类型": "Colour ramp type",
    "目前只支持连续配色方案": "Only continuous ramps are supported for now",
    "保存到样式…": "Save to style…",
    "已保存到色带列表": "Saved to the ramp list",
    "先存起来（存进色带列表，不关这个窗口）": "Save it now (into the ramp list, without closing this window)",
    "平均分配颜色停靠点": "Distribute stops evenly",
    "把各色标的位置均匀铺开（0%、…、100%）": "Spread the stops evenly (0%, …, 100%)",
    "我的配色方案": "My colour scheme",
    "未命名配色方案": "Untitled colour scheme",
    "配色方案已存在": "Colour scheme already exists",
    "配色方案「{0}」已存在。\n\n「是」覆盖它；「否」自动改名保存；「取消」不保存。":
        "The colour scheme “{0}” already exists.\n\n"
        "Yes = overwrite it; No = save under a new name; Cancel = don't save.",
    "改的是**当前选中**的那个色标（点色带上的手柄切换）": "Edits the **currently selected** stop (click a handle to switch)",
    "自定义色带": "Customise colour ramp",
    "编辑一条自己的色带（基于当前色带）":
        "Edit your own ramp (starting from the current one)",
    "给这条色带起个名字": "Give this ramp a name",
    "添加色标": "Add stop",
    "删除色标": "Remove stop",
    "翻转": "Invert",
    "把色带高低端对调": "Swap the low and high ends of the ramp",
    "点空白加色标；拖动改位置；双击改颜色；右键删除":
        "Click a blank spot to add a stop; drag to move; "
        "double-click to recolour; right-click to remove",
    "三波段彩色合成下色带不生效":
        "Colour ramps have no effect in 3-band RGB composite",
    "设置颜色…": "Set Colour\u2026",
    "设置这一项的颜色": "Set the colour of this item",
    "复制标签": "Copy Label",
    "菱形": "Diamond",
    "融合失败：{0}": "Dissolve failed: {0}",
    "表达式": "Expression",
    "表达式（可选）": "Expression (optional)",
    "可选：含 [字段名] 占位符的表达式，如 [name] / [code]":
        "Optional: expression with [field] placeholders, e.g. [name] / [code]",
    "表达式为空，未做选择": "The expression is empty; nothing was selected",
    "表达式为空：点「选择」将清空选择":
        "The expression is empty: clicking \u201cSelect\u201d clears the selection",
    "要素": "Feature",
    "要素编辑": "Feature editing",
    "要素 ID": "Feature ID",
    "要素 ID：{0}　双击缩放": "Feature ID: {0}　double-click to zoom",
    "要素已经在参考线上，无需移动":
        "The features are already on the reference line; nothing to move",
    "视图(&V)": "View(&V)",
    "计数": "Count",
    "识别到 {0} 个要素（{1}）": "Identified {0} feature(s) ({1})",
    "识别面板初始化失败：{}": "Initialising the identify panel failed: {}",
    "该功能将在后续里程碑接入": "This feature arrives in a later milestone",
    "该图层没有可用的标注字段": "This layer has no usable label field",
    "说明": "Description",
    "请先在图层树里选一个图层": "Select a layer in the layer tree first",
    "请先选中至少两个要素": "Select at least two features first",
    "请先选中要处理的要素": "Select the features to process first",
    "请先选中要拆分的要素": "Select the features to explode first",
    "请先选中要概化的要素": "Select the features to simplify first",
    "请先选择一个矢量图层": "Select a vector layer first",
    "请选择一个图层": "Please select a layer",
    "距离单位": "Distance unit",
    "输入关键字即时筛选（支持中文）":
        "Type a keyword to filter as you go (Chinese supported)",
    "进程所在机器的 CPU 与内存占用":
        "CPU and memory usage of the machine running the process",
    "退出 GmaGIS": "Quit GmaGIS",
    "关闭 GmaGIS": "Close GmaGIS",
    "工程「{0}」有尚未保存的修改。\n\n关闭前要保存这些改动吗？":
        "The project \"{0}\" has unsaved changes.\n\n"
        "Do you want to save them before closing?",

    "放弃": "Discard",
    "放弃全部未保存的改动，恢复到保存后的状态":
        "Discard all unsaved changes and restore the saved state",
    "放弃失败：{0}": "Discard failed: {0}",
    "已放弃「{0}」的全部改动": "Discarded all changes in {0}",
    "选择当前图层中的要素": "Select features in the current layer",
    "框选当前图层的要素": "Select features of the current layer",
    "要素选择": "Feature Selection",
    "取消：丢弃未确认的改动，并结束这次折点编辑":
        "Cancel: discard the unconfirmed changes and end this vertex edit",
    "重置：丢弃未确认的改动，几何回到原样（不退出折点编辑）":
        "Reset: discard the unconfirmed changes, geometry back to original "
        "(stays in vertex editing)",
    "没有待重置的折点改动": "There is nothing to reset in the vertex edit",
    "已重置折点编辑：未确认的改动已丢弃":
        "Vertex edit reset: the unconfirmed changes were discarded",
    "已结束折点编辑": "Vertex editing ended",
    "选择性粘贴": "Paste Special",
    "剪切": "Cut",
    "粘贴": "Paste",
    "复制选中的要素（可粘贴到当前图层或指定图层）":
        "Copy the selected features (paste into the current or a chosen layer)",
    "剪切选中的要素：从原图层移除，可粘贴到其它图层":
        "Cut the selected features: remove them here, paste into another layer",
    "把剪贴板里的要素粘贴到当前图层":
        "Paste the clipboard features into the current layer",
    "把剪贴板里的要素粘贴到指定的图层（弹出图层列表）":
        "Paste the clipboard features into a chosen layer (pick from a list)",
    "请先选中要{0}的要素": "Select the features to {0} first",
    "选中的要素读不出几何": "The selected features have no readable geometry",
    "剪切要素需要先在图层上开始编辑":
        "Cutting features requires the layer to be in edit mode",
    "已{0} {1} 个要素到剪贴板": "{0} {1} feature(s) to the clipboard",
    "剪切失败：{0}": "Cut failed: {0}",
    "剪贴板里没有要素": "There are no features on the clipboard",
    "请先选中要粘贴到的矢量图层": "Select the target vector layer first",
    "已粘贴 {0} 个要素到「{1}」": "Pasted {0} feature(s) into layer {1}",
    "剪贴板：{0} 个「{1}」要素": "Clipboard: {0} {1} feature(s)",
    "剪贴板：{0} 个「{1}」要素（来自「{2}」）":
        "Clipboard: {0} {1} feature(s) (copied from {2})",
    "{0}（栅格）": "{0} (raster)",
    "栅格图层不支持要素粘贴": "Raster layers cannot receive pasted features",
    "不支持要素粘贴": "Pasting features is not supported",
    "不可粘贴（需要「{0}」）": "Cannot paste here (needs {0})",
    "该图层是「{0}」，与剪贴板里的「{1}」不是同一几何类型":
        "This layer holds {0}, which does not match the {1} on the clipboard",
    "几何集合": "Geometry collection",
    "工程里没有图层": "There are no layers in this project",
    "把剪贴板里的要素粘贴到「{0}」（该图层不在编辑态时会自动开始编辑）":
        "Paste the clipboard features into {0} (the layer will start editing "
        "automatically if it is not already)",
    "没有可粘贴的目标图层：剪贴板里要素的类型与列表中的图层都对不上":
        "No valid paste target: no layer in the list matches the geometry "
        "type of the clipboard features",
    "把剪贴板里的要素粘贴到指定的图层（弹出对话框；几何类型不同的图层会显示为禁用）":
        "Paste the clipboard features into a specific layer (opens a dialog; "
        "layers with a different geometry type are shown as disabled)",
    "选中": "Selected",
    "选中 {0} 个": "{0} selected",
    "选中数": "Selected count",
    "选择(&S)": "Selection(&S)",
    "选择颜色": "Pick a colour",
    "选项": "Options",
    "选项一": "Option 1",
    "选项二": "Option 2",
    "选项三": "Option 3",
    "选项对话框加载失败：{}": "Loading the options dialog failed: {}",
    "选项已应用": "Options applied",
    "重命名": "Rename",
    "重置布局": "Reset layout",
    "长度合计 {0}": "Total length {0}",
    "降序": "Descending",
    "面按 √面积、线按长度比较；过小的要素不标注":
        "Polygons are compared by √area and lines by length; features that are "
        "too small are not labelled",
    "面板(&P)": "Panels(&P)",
    "面积": "Area",
    "面积单位": "Area unit",
    "面积合计 {0}": "Total area {0}",
    "页面": "Page",
    "颜色": "Colour",
    "高德影像（有偏）": "Amap imagery (offset)",
    "高德街道（有偏）": "Amap streets (offset)",
    "（没有更多分组）": "(no more groups)",
    "（本组暂无可用命令）": "(no available commands in this group)",

    " 地图单位": " map units",
    "KML：属性表会压成一张描述字段；大图层不建议用这个格式。":
        "KML: the attribute table is flattened into a single Description "
        "field; not recommended for large layers.",
    "Shapefile：字段名会被截到 10 字符；只支持单一几何类型，"
    "混合几何的图层会丢失部分要素。":
        "Shapefile: field names are truncated to 10 characters; only one "
        "geometry type is supported, so mixed layers lose features.",
    "VRT 只记录引用，不复制像元数据。":
        "A VRT only stores references; it does not copy the pixel data.",
    "X (经度)": "X (longitude)",
    "Y (纬度)": "Y (latitude)",
    "↑↓ 互换": "↑↓ Swap",
    "「{0}」里没有要素，无法导出": "\u201c{0}\u201d has no features to export",
    "交换源 / 目标坐标系，并把结果填回输入":
        "Swap the source / target CRS and put the result back into the input",
    "仅当前地图视图范围": "Current map view only",
    "仅第 {0} 波段": "Band {0} only",
    "保留 {0} / {1} 个要素": "Keep {0} / {1} feature(s)",
    "像元值": "Pixel value",
    "全不选": "Select none",
    "全部波段（{0} 个）": "All bands ({0})",
    "关系": "Relation",
    "包含标注": "Include labels",
    "包含选择集高亮": "Include selection highlight",
    "单位：{0}；数值为 {1} 投影下的平面坐标":
        "Unit: {0}; planar coordinates in {1}",
    "压缩": "Compression",
    "隐藏": "Hide",
    "新建子组": "New Subgroup",
    "组属性": "Group Properties",
    "可见": "Visible",
    "缩放至范围": "Zoom to Extent",
    "将所选成组": "Group Selected",
    "图层数量": "Layer Count",
    "子组数量": "Subgroup Count",
    "参考几何": "Reference geometry",
    "参考几何为空": "The reference geometry is empty",
    "参考图层里没有可用几何": "The reference layer has no usable geometry",
    "参考图层里没有选中的要素":
        "No feature is selected in the reference layer",
    "只导出选中的要素": "Export selected features only",
    "只显示匹配的要素": "Show matching features only",
    "只用该图层中已选中的要素作为参考":
        "Use only the selected features of that layer as reference",
    "可填 EPSG:3857 / 4326 这类代号；重投影由 pyproj 完成。":
        "Enter a code such as EPSG:3857 / 4326; reprojection is done by pyproj.",
    "图层共 {0} 个要素": "The layer has {0} feature(s)",
    "图层无效或尚未加载完成": "The layer is invalid or not loaded yet",
    "图片写入失败：{0}": "Writing the image failed: {0}",
    "图片尺寸": "Image size",
    "地图还没有内容，先添加数据": "The map is empty; add data first",
    "坐标超出该坐标系的有效范围":
        "The coordinate is outside the valid range of that CRS",
    "坐标转换": "Coordinate transform",
    "字段「{0}」里没有数值（是文本字段？）":
        "Field \u201c{0}\u201d holds no numeric values (is it a text field?)",
    "字段值": "Field value",
    "宽度 (px)": "Width (px)",
    "导出哪些要素": "Which features to export",
    "导出地图图片": "Export map image",
    "导出地图图片：{0} × {1} → {2}":
        "Export map image: {0} × {1} -> {2}",

    "导出字段": "Fields to export",
    "导出时重投影到：": "Reproject on export to:",
    "导出栅格图层": "Export raster layer",
    "导出栅格图层 — {0}": "Export raster layer — {0}",
    "导出栅格失败：{0}": "Exporting the raster failed: {0}",
    "导出栅格：{0} → {1}": "Export raster: {0} -> {1}",
    "导出矢量图层": "Export vector layer",
    "导出矢量图层 — {0}": "Export vector layer — {0}",
    "导出矢量失败：{0}": "Exporting the vector layer failed: {0}",
    "导出矢量：{0} → {1}": "Export vector: {0} -> {1}",
    "导出表格": "Export table",
    "导出表格 — {0}": "Export table — {0}",
    "导出表格失败：{0}": "Failed to export table: {0}",
    "导出表格：{0} → {1}": "Export table: {0} -> {1}",
    "已导出表格 → {0}": "Table exported -> {0}",
    "请先选择一个表格图层": "Please select a table layer first",
    "「{0}」里没有数据，无法导出": "\u201c{0}\u201d has no data to export",
    "表转矢量": "Table to vector",
    "表转矢量 — {0}": "Table to vector — {0}",
    "XY表转点": "XY to points",
    "WKT转几何": "WKT to geometry",
    "无法转换": "Cannot convert",
    "未指定 X / Y 字段": "X / Y field not specified",
    "没有列「{0}」": "Column not found: {0}",
    "没有可识别的几何": "No recognizable geometry",
    "没有可转换为几何的数据行": "No data rows could be converted to geometry",
    "已生成矢量图层：{0}": "Vector layer created: {0}",
    "导出已取消": "Export cancelled",
    "尺寸：{0} × {1}": "Size: {0} × {1}",
    "已复制到剪贴板": "Copied to the clipboard",
    "已导出地图图片 → {0}": "Map image exported -> {0}",
    "已导出栅格图层 → {0}": "Raster layer exported -> {0}",
    "已导出矢量图层 → {0}": "Vector layer exported -> {0}",
    "已加入地图：{0}": "Added to map: {0}",
    "导出后加入地图失败：{0}": "Failed to add to map after export: {0}",
    "已导出，但无法读回加入地图：{0}":
        "Exported, but could not read back into the map: {0}",
    "已导出，但加入地图失败：{0}":
        "Exported, but failed to add to the map: {0}",
    "已清除「{0}」的过滤": "Filter cleared for \u201c{0}\u201d",
    "已跳过 {0} 个空值 / 非数值":
        "Skipped {0} empty / non-numeric value(s)",
    "已过滤「{0}」：保留 {1} / {2} 个要素":
        "Filtered \u201c{0}\u201d: {1} / {2} feature(s) kept",
    "已过滤，只导出可见的 {0} 个":
        "Filtered: only the {0} visible feature(s) are exported",
    "已选 {0} 个字段": "{0} field(s) selected",
    "当前地图视图没有有效范围": "The current map view has no valid extent",
    "当前地图视图范围": "Current map view",
    "按位置选中：当前共 {0} 个要素":
        "Select by location: {0} feature(s) selected in total",
    "按位置选择 — {0}": "Select by location — {0}",
    "按位置选择：{0} → 共 {1} 个": "Select by location: {0} -> {1} in total",
    "数据量较大，已按 1/{0} 抽样绘制":
        "Large dataset: drawn from a 1/{0} sample",
    "整个图层": "Whole layer",
    "暂无数据": "No data",
    "未知": "Unknown",
    "来自图层：": "From layer:",
    "栅格图层没有打开的数据集": "The raster layer has no open dataset",
    "没有可用的参考图层": "There is no usable reference layer",
    "没有可统计的数值": "No numeric values to summarise",
    "没有地图视图，无法取当前范围":
        "There is no map view to take the current extent from",
    "没有选中的要素可导出": "No selected feature to export",
    "沿用图层坐标系（{0}）": "Keep the layer CRS ({0})",
    "波段 {0}": "Band {0}",
    "波段 {0} 像元值分布": "Pixel value distribution of band {0}",
    "波段：{0}": "Bands: {0}",
    "渲染失败：{0}": "Rendering failed: {0}",
    "源坐标系": "Source CRS",
    "源坐标系无法识别：{0}": "Unrecognised source CRS: {0}",
    "留 0 = 自动（Freedman–Diaconis 规则）":
        "Leave 0 for automatic (Freedman–Diaconis rule)",
    "目标坐标系": "Target CRS",
    "目标坐标系无法识别：{0}": "Unrecognised target CRS: {0}",
    "直方图 — {0}": "Histogram — {0}",
    "空间关系": "Spatial relation",
    "箱数": "Bins",
    "类型：{0}": "Type: {0}",
    "纬度": "Latitude",
    "纵轴对数": "Logarithmic Y axis",
    "经度": "Longitude",
    "自动": "Automatic",
    "范围与波段": "Extent and bands",
    "表达式为空：应用后清除现有过滤":
        "The expression is empty: applying clears the current filter",
    "该波段没有有效像元（全部是 nodata？）":
        "This band has no valid pixels (all nodata?)",
    "该点位于纬度 {0}°、经度 {1}°":
        "The point is at latitude {0}°, longitude {1}°",
    "请先选择一个栅格图层": "Select a raster layer first",
    "请先选择输出图片": "Choose the output image first",
    "请先选择输出文件": "Choose the output file first",
    "请输入数值 X / Y": "Enter numeric X / Y",
    "距离": "Distance",
    "路径": "Path",
    "转换失败：{0}": "Transformation failed: {0}",
    "转换结果": "Result",
    "输入坐标": "Input coordinate",
    "过滤方式": "Filter mode",
    "过滤要素 — {0}": "Filter features — {0}",
    "按「{0}」设置过滤条件（要素 {1} 个）":
        "Set a filter for \u201c{0}\u201d ({1} feature(s))",
    "设置过滤条件": "Set a filter",
    "字段": "Field",
    "值": "Value",
    "搜索…": "Search…",
    "先在左边选一个字段": "Pick a field on the left first",
    "点「采样」取「{0}」的候选值":
        "Click Sample to load candidate values of \"{0}\"",
    "「{0}」没有取到候选值": "No candidate value found for \"{0}\"",
    "在此输入过滤条件，例如：  POP >= 500  AND  NAME LIKE '南%'\n（字段与值都能双击插入；留空后点「确定」= 清除本图层现有的过滤条件）":
        "Type a filter condition here, e.g.  POP >= 500  AND  NAME LIKE 'Nan%'\n"
        "(fields and values can be inserted by double-click; leaving it empty "
        "and pressing OK clears this layer's filter)",
    "采样": "Sample",
    "全部": "All",
    "只读前 {0} 个要素取唯一值（快）":
        "Read the first {0} features for unique values (fast)",
    "读完整个图层取唯一值（大图层会慢一点）":
        "Read the whole layer for unique values (slower on big layers)",
    "候选值 {0} 个{1}": "{0} candidate value(s){1}",
    "（已截断）": " (truncated)",
    "使用未过滤的图层": "Use unfiltered layer",
    "勾上：取样值来自全部要素；不勾：只取当前可见（已过滤）的要素":
        "Checked: values come from all features; unchecked: only from the "
        "currently visible (filtered) features",
    "运算符": "Operators",
    "插入 {0}": "Insert {0}",
    "双击插入字段名": "Double-click to insert the field name",
    "测试": "Test",
    "已试套到地图上：保留 {0} / {1} 个要素（取消可还原）":
        "Applied to the map for testing: {0} / {1} feature(s) kept "
        "(Cancel restores it)",
    "这个栅格没有属性表（连续值栅格，如 DEM / 影像）":
        "This raster has no attribute table (continuous values, e.g. DEM / imagery)",
    "这个图层没有字段可选": "This layer has no selectable field",
    "选择「{0}」中满足下列空间关系的要素":
        "Select the features of \u201c{0}\u201d that satisfy the spatial "
        "relation below",
    "选择输出图片…": "Choose the output image…",
    "锁定宽高比": "Lock aspect ratio",
    "长尾数据用对数看副峰；柱高为 0 的箱仍然空着":
        "Use a log axis to see secondary peaks in long-tailed data; "
        "empty bins stay empty",
    "隐藏 {0} 个，保留 {1} / {2} 个要素":
        "Hide {0}, keep {1} / {2} feature(s)",
    "隐藏匹配的要素": "Hide matching features",
    "高度 (px)": "Height (px)",
        "选择坐标系": "Select CRS",
        "地图坐标系": "Map coordinate system",
        "搜索": "Search",
        "输入名称或编号，如 4326 / CGCS2000 / UTM":
            "Type a name or code, e.g. 4326 / CGCS2000 / UTM",
                    "（未定义坐标系）": "(undefined CRS)",
        "（自定义坐标系）": "(custom CRS)",
        "未定义": "Undefined",
                "当前：{0} — {1}": "Current: {0} — {1}",
        "共 {0} 条": "{0} entries",
        "共 {0} 条，仅显示前 {1} 条——请继续输入以缩小范围":
            "{0} entries, showing the first {1} — keep typing to narrow down",
                "地图坐标系（决定地图按哪个坐标系显示，其余坐标系的数据会实时投影过来）":
            "Map CRS (sets the map display CRS; layers in other CRS are "
            "reprojected on the fly)",
        "地图坐标系已切换为 {0}": "Map coordinate system changed to {0}",
        "地图坐标系已设为未定义": "Map CRS set to undefined",

    "信息": "Information",
    "数据本身的坐标就是目标坐标系，只是元数据缺失或错误时选这个。"
    "适合：shapefile 少了 .prj、或者 .prj 写错了。":
        "Use this when the stored coordinates already are in the target CRS "
        "and only the metadata is missing or wrong — for example a shapefile "
        "with no .prj, or with an incorrect one.",
    "数据确实在另一个坐标系下，需要把每个顶点换算过去时选这个。"
    "要保存结果请用「导出矢量图层」。":
        "Use this when the data really is in another CRS and every vertex has "
        "to be converted. Use Export Vector Layer to save the result.",
    "选择…": "Choose…",
    "从全量 EPSG 坐标系中查找，或直接输入编号 / WKT":
        "Look up the full EPSG list, or type a code / WKT directly",
    "未定义坐标系时不做任何重投影":
        "With an undefined CRS nothing is reprojected",
    "地图坐标系决定地图按哪个坐标系显示。当某个图层的坐标系与它不同时，"
    "渲染时会把这个图层的坐标实时投影到地图坐标系（OTF，On-The-Fly），"
    "原始数据文件不会被改写。":
        "The project CRS decides how the map is displayed. When a layer uses a "
        "different CRS, its coordinates are projected on the fly (OTF) to the "
        "project CRS while rendering; the source data files are never rewritten.",
    "未定义坐标系：各图层按各自坐标系原样显示，不做任何投影换算。":
        "Undefined CRS: every layer is drawn as-is in its own CRS, with no "
        "projection applied.",
    "{}：{}（{}，单位 {}）": "{}: {} ({}, unit {})",
    "（未定义）": "(undefined)",
    "（未知）": "(unknown)",
    "（无）": "(none)",
    "（内存图层）": "(in-memory layer)",
    "图层属性对话框加载失败：{}":
        "Failed to open the layer properties dialog: {}",
    "已把「{0}」的坐标系改为 {1}（坐标数值未改动）":
        "CRS of \u201c{0}\u201d set to {1} (coordinate values unchanged)",
    "已把「{0}」的 {1} 个要素从 {2} 重投影到 {3}（只改了内存，要保存请用导出）":
        "Reprojected {1} features of \u201c{0}\u201d from {2} to {3} "
        "(in memory only; export to save)",
    "「{0}」是栅格图层，只能修改坐标系定义，不能重投影数据":
        "\u201c{0}\u201d is a raster layer: only its CRS definition can be "
        "changed, its data cannot be reprojected",
    "「{0}」的坐标系未定义，无法重投影——请先用「只修改坐标系定义」"
    "告诉软件数据在哪个坐标系下":
        "The CRS of \u201c{0}\u201d is undefined, so it cannot be reprojected — "
        "use \u201cchange the CRS definition only\u201d first to tell the "
        "software which CRS the data is in",
    "重投影失败：{}": "Reprojection failed: {}",

    "复制路径": "Copy Path",
    "剪贴": "Cut",
    "粘贴图层": "Paste Layer",
    "显示标注": "Show Labels",
    "移除分组": "Remove Group",
    "移除分组及图层…": "Remove Group and Layers…",
    "移除分组及图层": "Remove Group and Layers",
    "移除这 {0} 个图层…": "Remove These {0} Layers…",
    "移除这 {0} 个图层": "Remove These {0} Layers",
    "缩放至这 {0} 个图层": "Zoom to These {0} Layers",
    "显示这 {0} 个图层": "Show These {0} Layers",
    "隐藏这 {0} 个图层": "Hide These {0} Layers",
    "已显示 {0} 个图层": "Showed {0} layers",
    "已隐藏 {0} 个图层": "Hid {0} layers",
    "确定要移除这 {0} 个图层吗？\n{1}":
        "Remove these {0} layers?\n{1}",
    "已移除 {0} 个图层": "Removed {0} layers",
    "缩放至分组范围": "Zoom to Group",
    "重命名组": "Rename Group",
    "展开分组": "Expand Group",
    "折叠分组": "Collapse Group",
    "分组内全部显示": "Show All in Group",
    "分组内全部隐藏": "Hide All in Group",
    "分组「{0}」里有 {1} 个图层，确定要一起移除吗？":
        "Group \u201c{0}\u201d contains {1} layers. Remove them all?",
    "已移除分组及其 {0} 个图层": "Removed the group and its {0} layers",
    "分组里没有可缩放的图层": "The group has no layer to zoom to",
    "{0} 副本": "{0} copy",
    "复制图层失败：{}": "Failed to duplicate the layer: {}",
    "已复制图层：{0}": "Layer duplicated: {0}",
    "已复制图层到剪贴板：{0}": "Layer copied to clipboard: {0}",
    "「{0}」是栅格图层，请用「显示设置」调整显示":
        "\u201c{0}\u201d is a raster layer — use Raster Display Settings to "
        "change how it is displayed",
    "「{0}」是栅格图层，不能按属性过滤":
        "\u201c{0}\u201d is a raster layer and cannot be filtered by "
        "attributes",
    "栅格显示 — {0}": "Raster Display \u2014 {0}",
    "伽马": "Gamma",
    "大于 1 提亮暗部，小于 1 压暗；1.00 = 不调整":
        "Above 1 brightens the shadows, below 1 darkens them; "
        "1.00 leaves the pixels untouched",
    "整层透明度；不影响像素本身，拖动时不必重算图像":
        "Whole-layer opacity. It does not touch the pixels, so dragging is "
        "cheap",
    "对比度拉伸": "Contrast stretch",
    "方式": "Mode",
    "百分位截断": "Percentile clip",
    "最小-最大": "Min\u2013max",
    "不拉伸（原始值）": "No stretch (raw values)",
    "百分位": "Percentile",
    "下限百分位；调小可以把暗部细节拉出来":
        "Lower percentile. Lowering it pulls shadow detail out",
    "上限百分位；调大可以把高光细节拉回来":
        "Upper percentile. Raising it brings highlight detail back",
    "手动指定区间": "Specify the range manually",
    "勾选后用下面填的最小 / 最大取代百分位，适合已知量纲的数据":
        "When checked, the min / max below replace the percentiles. Useful "
        "when the value range is known in advance",
    "无数据处的像素画成这个颜色；透明度拖到 100%（默认）= 不画":
        "No-data pixels are painted in this colour; drag transparency to "
        "100% (the default) to leave them unpainted",
    "留空 = 用数据源自带的节点值":
        "Leave empty to use the nodata value stored in the data source",
    "（留空用数据源自带值）": "(empty = value from the data source)",
    "分布（全幅抽样）": "Distribution (sampled over the whole raster)",
    "自动（三波段彩色）": "Automatic (3-band colour)",
    "像元值分布": "Pixel value distribution",
    "读不出像素（数据源可能已失效）":
        "Cannot read any pixel (the data source may be gone)",
    "像元值（拉伸到 {0} ~ {1}）": "Pixel value (stretched to {0} \u2013 {1})",
    "像元值（不拉伸）": "Pixel value (no stretch)",
    "有效像元 {0} ｜ 最小 {1} ｜ 最大 {2} ｜ 均值 {3} ｜ 中位 {4} ｜ "
    "标准差 {5} ｜ 2%~98% 为 {6} ~ {7}":
        "Valid pixels {0} | Min {1} | Max {2} | Mean {3} | Median {4} | "
        "Std {5} | 2%\u201398% spans {6} \u2013 {7}",
    "重置": "Reset",
    "请先在图层树里选一个栅格图层":
        "Select a raster layer in the layer tree first",
    "「{0}」不是栅格图层": "\u201c{0}\u201d is not a raster layer",
    "没有图层": "No layer",
    "显示设置…": "Display Settings\u2026",
    "直方图": "Histogram",
    "拉伸": "Stretch",
    "应用到图层": "Apply to layer",
    "栅格属性表…": "Raster Attribute Table\u2026",
    "栅格属性表": "Raster Attribute Table",
    "栅格属性表 — {0}": "Raster Attribute Table \u2014 {0}",
    "查看分类栅格的值 / 类别 / 颜色 / 像素数":
        "Show the values / classes / colours / pixel counts of a classified "
        "raster",
    "这个栅格没有属性表": "This raster has no attribute table",
    "像素数": "Pixels",
    "「{0}」第 {1} 波段：{2} 个类别值（数据源自带调色板）":
        "\u201c{0}\u201d band {1}: {2} class values (colour table from the "
        "data source)",
    "「{0}」第 {1} 波段：{2} 个离散取值":
        "\u201c{0}\u201d band {1}: {2} distinct values",
    "「{0}」第 {1} 波段：没有属性表":
        "\u201c{0}\u201d band {1}: no attribute table",
    "样式管理器": "Style Manager",
    "样式库管理：符号 / 色带 / 标注 / 文本格式":
        "Manage the style library: symbols / ramps / labels / text formats",
    "（不选，仅浏览）": "(none — browse only)",
    "预设": "Presets",
    "预览": "Preview",
    "复制为自定义": "Duplicate as custom",
    "导入…": "Import…",
    "导出…": "Export…",
    "{0} × {0} px": "{0} × {0} px",
    "输出 {0} × {1} px；按 {2} DPI 打印约 {3:.1f} × {4:.1f} cm":
        "Output {0} × {1} px; at {2} DPI about {3:.1f} × {4:.1f} cm",
    " px": " px",
    "内置": "Built-in",
    "内置预设（只读）": "Built-in preset (read-only)",
    "自定义预设": "Custom preset",
    "内置预设只读；改动请先「复制为自定义」":
        "Built-in presets are read-only; duplicate one as custom before editing",
    "色带是内置集合（自定义色带需要色标编辑器，暂未支持）":
        "Ramps are built-in only (custom ramps need a colour-stop editor, not supported yet)",
    "提示：可按「{0}」筛选几何类型": "Tip: filter by geometry type with “{0}”",
    "未选目标图层：只能浏览": "No target layer: browse only",
    "目标图层：{0}": "Target layer: {0}",
    "色标": "Colour stops",
    "删除样式": "Delete style",
    "确定删除自定义样式「{0}」？": "Delete the custom style “{0}”?",
    "已保存：{0}": "Saved: {0}",
    "我的{0} {1}": "My {0} {1}",
    "导入样式库": "Import style library",
    "导出样式库": "Export style library",
    "JSON 文件 (*.json)": "JSON files (*.json)",
    "导入失败": "Import failed",
    "导出失败": "Export failed",
    "已导入 {0} 条样式": "Imported {0} styles",
    "已导出样式库：{0}": "Style library exported: {0}",
    "应用失败": "Apply failed",
    "已把「{0}」应用到 {1}{2}": "Applied “{0}” to {1}{2}",
    "按字段「{0}」分 5 级": "5 classes on field “{0}”",
    "该图层没有数值字段，无法做分级渲染":
        "This layer has no numeric field; graduated rendering is not possible",
    "标注样式已更新": "Label style updated",
    "示例文字": "Sample text",
    "符号": "Symbol",
    "文本格式": "Text format",
    "光谱": "Spectral",
    "黄蓝渐变": "Yellow–blue",
    "蓝绿渐变": "Blue–green",
    "橙红渐变": "Orange–red",
    "灰阶": "Greyscale",
    "红蓝分歧": "Red–blue diverging",
    "紫绿分歧": "Purple–green diverging",
    "标准点": "Standard point",
    "小点": "Small point",
    "强调点": "Emphasis point",
    "淡灰点": "Muted grey point",
    "标准线": "Standard line",
    "主线": "Main line",
    "细辅助线": "Thin helper line",
    "强调线": "Emphasis line",
    "标准面": "Standard polygon",
    "淡填充面": "Light fill polygon",
    "实色面": "Solid fill polygon",
    "高亮面": "Highlight polygon",
    "自动放置": "Automatic placement",
    "点右侧": "Right of point",
    "点上方": "Above point",
    "沿线重复": "Repeat along line",
    "大面标注（≥40px）": "Large polygon label (≥ 40 px)",
    "每层最多 200 个": "At most 200 per layer",
    "白字黑晕": "White text, black halo",
    "深色字（浅底）": "Dark text on a light background",
    "粗体白字": "Bold white text",
    "强调橙字": "Emphasis orange text",
    "斜体标注": "Italic label text",
    "衬线字体": "Serif font",
    "填充色": "Fill colour",
    "描边色": "Stroke colour",
    "填充透明度": "Fill opacity",
    "放置方式": "Placement",
    "水平偏移": "Horizontal offset",
    "垂直偏移": "Vertical offset",
    "最小要素尺寸": "Minimum feature size",
    "沿线间隔": "Repeat interval along line",
    "晕圈颜色": "Halo colour",
    "晕圈宽度": "Halo width",
    "文字间距": "Text buffer",
    "表达式构建器": "Expression Builder",
    "表达式编辑器：函数参考 + 实时求值预览":
        "Expression editor: syntax reference with live evaluation preview",
    "（不选，仅校验语法）": "(none — syntax check only)",
    "字段（双击插入）": "Fields (double-click to insert)",
    "语法参考（双击插入）": "Syntax reference (double-click to insert)",
    "求值预览（前 {0} 行）": "Evaluation preview (first {0} rows)",
    "表达式结果": "Expression result",
    "应用到选择": "Apply to selection",
    "空表达式：写一条条件试试": "Empty expression: write a condition to get started",
    "语法正确": "Syntax OK",
    "语法错误：{0}": "Syntax error: {0}",
    "未选图层：只校验语法，不做求值": "No layer selected: syntax check only, no evaluation",
    "统计失败：{0}": "Counting failed: {0}",
    "表达式求值失败：{0}": "Expression evaluation failed: {0}",
    "比较": "Comparison",
    "不等": "Not equal",
    "大小比较": "Ordering comparison",
    "相等（数字或文本；文本要加引号）": "Equal (numbers or text; quote text values)",
    "文本匹配": "Text matching",
    "% 任意长度、_ 单字符；* 等同 %":
        "% matches any length, _ matches one character, * means the same as %",
    "不匹配该模式": "Does not match the pattern",
    "集合与区间": "Lists and ranges",
    "在集合内": "In the list",
    "不在集合内": "Not in the list",
    "闭区间（含两端）": "Closed interval (both ends included)",
    "空值": "Null values",
    "为空": "Is null",
    "不为空": "Is not null",
    "逻辑": "Logic",
    "两边都成立": "Both sides must hold",
    "任一边成立": "Either side may hold",
    "取反": "Negate",
    "用括号分组，别靠优先级记忆":
        "Group with parentheses instead of relying on precedence",
    "字面量": "Literals",
    "数字": "Number",
    "文本": "Text",
    "支持科学计数法 1e3": "Scientific notation such as 1e3 is supported",
    "单引号，内部 '' 转义": "Single quotes; '' escapes an inner quote",
    "布尔与空值常量": "Boolean and null constants",
    "数值大于": "Numeric greater than",
    "区间": "Range",
    "文本包含": "Text contains",
    "非空": "Not null",
    "{字段} LIKE '%关键字%'": "{字段} LIKE '%keyword%'",
    "{字段} IN ('甲', '乙')": "{字段} IN ('alpha', 'beta')",
    "{字段} NOT IN ('甲', '乙')": "{字段} NOT IN ('alpha', 'beta')",

    "使用范围": "Area of use",
    "搜索结果": "Search results",
    "编号": "Code",
    "（未选择坐标系）": "(no coordinate system selected)",
    "其他投影方法": "Other projection methods",
    "共 {0} 条——按类型与投影方法分组，展开查看；也可在上方直接搜索编号或名称": "Total {0} — grouped by type and projection method; expand a group, or search by code / name above",
    "共 {0} 条，仅显示前 {1} 条——请在上方输入以缩小范围": "{0} in total, showing the first {1} — type above to narrow it down",
    "没有匹配项。也可以直接在上面输入 EPSG 编号或 WKT 后确定。": "No match. You can also type an EPSG code or WKT above and confirm.",
    "新建坐标系…": "New CRS…",
    "新建坐标系": "New Coordinate System",
    "无法打开新建坐标系": "Could not open the new-CRS dialog",
    "坐标系信息": "Coordinate system info",
    "坐标系无效": "Invalid coordinate system",
    "按当前参数建不出有效的坐标系，请检查投影方法与各参数。":
        "The current parameters do not produce a valid coordinate system; "
        "please check the projection method and parameters.",
    "基准（椭球）": "Datum (ellipsoid)",
    "角度单位": "Angular unit",
    "长度单位": "Linear unit",
    "例如：某某市独立坐标系": "e.g. Some City Local Grid",
    "新建地理坐标系": "New geographic coordinate system",
    "新建地理坐标系或投影坐标系（可指定基准、投影方法与参数）":
        "Create a geographic or projected coordinate system "
        "(choose datum, projection method and parameters)",
    "自定义坐标系": "Custom coordinate system",
    "自定义": "Custom",
    "当前视图": "Current view",
    "选择图层范围": "Select layer extent",
    "在地图上框选": "Pick on map",
    "范围无效": "Extent invalid",
    "X 最小值": "X min",
    "Y 最小值": "Y min",
    "X 最大值": "X max",
    "Y 最大值": "Y max",
    "（暂无视图范围）": "(no view extent yet)",
    "分析结果": "Analysis result",
    "{0} 个要素": "{0} feature(s)",
    "用时 {0} ms": "Elapsed {0} ms",
    "有 {0} 条警告": "{0} warning(s)",
    "没有匹配项。也可以直接在上面输入 EPSG 编号或 WKT 后确定，或点右侧「新建坐标系…」。":
        "No match. You can also type an EPSG code or WKT above and confirm, "
        "or click \"New CRS…\" on the right.",
    "WGS 84": "WGS 84",
    "CGCS2000（GRS80 椭球）": "CGCS2000 (GRS80 ellipsoid)",

    "西安 1980（IAG-75 椭球）": "Xian 1980 (IAG-75 ellipsoid)",
    "北京 1954（克拉索夫斯基椭球）": "Beijing 1954 (Krassovsky ellipsoid)",
    "弧度": "Radians",
    "美制英尺": "US survey feet",
    "阿尔伯斯等积圆锥": "Albers Equal Area Conic",
    "墨卡托（1SP）": "Mercator (1SP)",
    "Web 墨卡托（Pseudo-Mercator）": "Web Mercator (Pseudo-Mercator)",
    "原点纬度": "Latitude of origin",
    "中央经线": "Central meridian",
    "第一标准纬线": "Standard parallel 1",
    "第二标准纬线": "Standard parallel 2",
    "比例因子": "Scale factor",
    "东偏移（假东）": "False easting",
    "北偏移（假北）": "False northing",
    "假原点纬度": "Latitude of false origin",
    "假原点经度": "Longitude of false origin",
    "假原点东偏": "Easting at false origin",
    "假原点北偏": "Northing at false origin",
    "中心经度": "Longitude of centre",
    "中心纬度": "Latitude of centre",
    "（无 EPSG 编码）": "(no EPSG code)",
    "剖面曲线": "Profile",
    "无法打开剖面曲线：{0}": "Could not open the profile dialog: {0}",
    "剖面曲线 — {0}": "Profile — {0}",
    "X（图层坐标）": "X (layer coordinates)",
    "Y（图层坐标）": "Y (layer coordinates)",
    "用视图中心": "Use view centre",
    "把取样位置退回当前画布视野的中心":
        "Move the probe back to the centre of the current canvas view",
    "行 / 列曲线用波段": "Band for the row / column curves",
    "行曲线（过该点沿 X 方向）": "Row profile (along X through the point)",
    "列曲线（过该点沿 Y 方向）": "Column profile (along Y through the point)",
    "横轴：图层坐标 {0}": "X axis: layer coordinates {0}",
    "横轴：{0} = {1}（图层坐标 {2} ~ {3}）": "X-axis: {0} = {1} (layer coords {2} ~ {3})",
    "像素（列, 行）": "Pixel (column, row)",
    "像素（列, 行）=（{0}, {1}）": "Pixel (column, row) = ({0}, {1})",
    "　无数据值 = {0}": "  No-data value = {0}",
    "（无数据）": "(no data)",
    "（没有数据）": "(no data)",
    "（读不到像素值）": "(no pixel value could be read)",
    "该位置不在栅格范围内（或者读不到像素）。把 X / Y 改到范围内，或点「用视图中心」。":
        "The position is outside the raster (or no pixel could be read). "
        "Adjust X / Y to be inside, or click \"Use view centre\".",
    "栅格像素：双击打开该位置的剖面曲线":
        "Raster pixel: double-click to open the profile curves here",
    "横轴墨卡托 / 高斯-克吕格": "Transverse Mercator / Gauss-Kruger",
    "斜轴墨卡托": "Oblique Mercator",
    "伪墨卡托（Web 墨卡托）": "Pseudo-Mercator (Web Mercator)",
    "墨卡托": "Mercator",
    "兰勃特等角圆锥": "Lambert Conic Conformal",
    "兰勃特等积方位": "Lambert Azimuthal Equal Area",
    "阿尔伯斯等积": "Albers Equal Area",
    "极地立体投影": "Polar Stereographic",
    "斜轴立体投影": "Oblique Stereographic",
    "方位等距": "Azimuthal Equidistant",
    "卡西尼-索尔德纳": "Cassini-Soldner",
    "多圆锥": "Polyconic",
    "克罗瓦克": "Krovak",
    "摩尔魏特等积": "Mollweide Equal Area",
    "圆柱等积": "Cylindrical Equal Area",
    "哥伦比亚城市网格": "Colombia Urban",
    "等距圆柱": "Equidistant Cylindrical",

    "界面缩放": "Interface scale",
    "复制全部日志到剪贴板": "Copy all log entries to clipboard",
    "把日志保存为文本文件…": "Save the log to a text file…",
    "只显示指定级别以上的日志": "Show only entries at or above this level",
    "全部消息": "All messages",
    "仅警告及以上": "Warnings and errors",
    "仅错误": "Errors only",
    "自动滚动": "Auto-scroll",
    "新日志到来时自动滚到最后一行":
        "Scroll to the newest entry automatically",
    "{0} 条": "{0} entries",
    "保存日志": "Save log",
    "文本文件 (*.txt *.log);;所有文件 (*)":
        "Text files (*.txt *.log);;All files (*)",
    "正在后台建立显示金字塔（{0}），期间缩放会稍慢":
        "Building a display pyramid in the background ({0}); zooming is "
        "slower until it finishes",
    "后台建立显示金字塔：{0}": "Building display pyramid in background: {0}",
    "建立显示金字塔": "Building display pyramid",
    "显示金字塔已就绪，缩放平移将明显更快":
        "Display pyramid ready; zooming and panning will be much faster",
    "显示金字塔已就绪：{0}": "Display pyramid ready: {0}",
    "缩略图已就绪，正在精细化显示金字塔":
        "Quicklook ready; finer pyramid levels still being prepared",
    "运行环境": "Runtime environment",
    "组件版本": "Component versions",
    "查看全文…": "View full text…",
    "{0}%（跟随系统）": "{0}% (follow system)",
    "英文": "English",
    "架构": "Architecture",
    "界面语言": "Interface language",
    "内存大小": "Memory",
    "CPU 型号": "CPU model",
    "多视图桌面 GIS · 地图、布局与模型构建器一体化":
        "Multi-view desktop GIS · map, layout and model builder in one",
    "内置内核 · 子进程渲染": "Built-in renderer · rendering in a subprocess",
    "使用手册": "User Manual",
    "GmaGIS 使用手册": "GmaGIS User Manual",
    "打开使用手册：界面、数据、编辑、分析、出图逐个讲一遍 (F1)":
        "Open the user manual: interface, data, editing, analysis, "
        "and map production (F1)",
    "按功能组织；左侧目录可直接跳转":
        "Organized by feature; use the outline on the left to jump",
    "使用手册加载失败：{}": "Failed to open the user manual: {}",
    "批处理": "Batch",
    "[错误] 功能区重建失败：{}":
        "[error] Failed to rebuild the ribbon: {}",
    "选择矢量文件": "Choose vector file",
    "更换文件…": "Change file…",
    "当前：{0}": "Current: {0}",
    "选择磁盘上的矢量文件": "Choose a vector file on disk",
    "运行中…": "Running…",
    "执行失败：{0}": "Execution failed: {0}",


    "端点": "Endpoint",
    "节点": "Vertex",
    "交点": "Intersection",
    "中点": "Midpoint",
    "边": "Edge",
    "捕捉到线 / 面的首末顶点": "Snap to the first/last vertex of a line or polygon",
    "捕捉到任意折点": "Snap to any vertex",
    "捕捉到两条线段的交叉点": "Snap to the crossing point of two segments",
    "捕捉到线段的中间点": "Snap to the midpoint of a segment",
    "捕捉到线段上距离鼠标最近的点（不限于端点与折点）": "Snap to the nearest point on a segment (not just endpoints or vertices)",
    "捕捉总开关：关闭后鼠标落点不再吸附到任何几何": "Master snapping switch: when off, the cursor no longer sticks to any geometry",

    "算法分类": "Algorithm category",

    "地图坐标系未定义：不做任何重投影，按数据自身坐标直接显示":
        "Map CRS is undefined: no reprojection is applied; data is "
        "drawn in its own coordinates",

    "当前比例尺（1:N）。可挑选常见比例，也可直接输入（如 1:25000）":
        "Current scale (1:N). Pick a common scale or type one (e.g. 1:25000)",
    "画布缩放（100% 为实际尺寸）。可挑选，也可直接输入（如 150%）":
        "Canvas zoom (100% = actual size). Pick a step or type one "
        "(e.g. 150%)",
    "锁定比例：开启后滚轮与缩放工具都不再改变比例（平移不受影响）":
        "Lock scale: wheel and zoom tools no longer change the scale "
        "(panning still works)",
    "已锁定比例": "Scale locked",
    "已解除比例锁定": "Scale unlocked",
    "设置比例尺": "Set scale",
    "比例尺分母（1:N 中的 N）": "Scale denominator (the N in 1:N)",
    "已缩放到比例 1:{0}": "Zoomed to scale 1:{0}",

    "渲染": "Rendering",
    "矢量渲染后端": "Vector renderer",
    "栅格渲染后端": "Raster renderer",
    "流式瓦片（方案2）": "Streaming tiles (Scheme 2)",
    "经典（方案1）": "Classic (Scheme 1)",
    "流式瓦片块边长": "Streaming tile edge",
    "流式瓦片内存缓存": "Streaming tile cache",
    "「流式瓦片（方案2）」已暂时隐藏，渲染固定用方案1。":
        "Streaming tiles (Scheme 2) is hidden for now; rendering is fixed to "
        "Scheme 1.",
    "清空渲染缓存": "Clear render cache",
    "缓存位置": "Cache location",
    "选择缓存目录": "Choose cache folder",
    "选择日志文件": "Choose log file",
    "日志文件 (*.log);;所有文件 (*)": "Log files (*.log);;All files (*)",
    "留空 = 自动探测常见安装位置":
        "Empty = auto-detect a common installation",
    "在线瓦片与显示金字塔的存放位置（可再生，可随手删）。"
    "可填绝对路径，如 D:/GmaGIS-cache":
        "Where online tiles and display pyramids are stored "
        "(regenerable, safe to delete). An absolute path is fine, "
        "e.g. D:/GmaGIS-cache",
    "已请求清空（确定后执行）": "Clear requested (on OK)",
    "丢掉已缓存的瓦片与块路径，下次重绘重新读数据":
        "Drop cached tiles and block paths; the next repaint re-reads data",
    "方案1 为当前默认后端；方案2 按瓦片边读边画，首屏更快、单帧更轻，"
    "但整层可见且顶点极多时完全清晰会更慢。切换后立即生效，缓存会自动清空。":
        "Scheme 1 is the current default. Scheme 2 reads and draws tile by "
        "tile: the first frame is faster and each frame is lighter, but with "
        "a whole layer visible and millions of vertices the fully sharp "
        "result takes longer. Switching takes effect immediately and the "
        "cache is cleared.",
    "块边长越小切得越碎（首屏更快、块数更多）；内存缓存超限时按"
    "最久未用淘汰。方案2 不写任何临时文件。":
        "A smaller tile edge means more, finer tiles (faster first frame). "
        "The in-memory cache evicts least-recently-used tiles when over "
        "budget. Scheme 2 writes no temporary files.",
    "正在保存工程…": "Saving project…",
    "正在打开工程…": "Opening project…",
    "正在导出矢量…": "Exporting vector layer…",
    "保存期间工程又有改动，这些改动尚未写入，请再保存一次": (
        "The project was modified while saving; those changes have not "
        "been written yet. Please save again."),

    "符号系统 — {0}": "Symbology — {0}",
    "标注 — {0}": "Labels — {0}",
    "请先在图层树里选中一个图层。": "Select a layer in the layer tree first.",
    "该图层类型没有可配置的符号系统。": "This layer type has no configurable symbology.",
    "勾选后用最小 / 最大取代百分位，适合已知量纲的数据": "Use the min / max below instead of percentiles; handy for data with known units",
    "填充": "Fill",
    "描边": "Stroke",
    "线条": "Line",
    "间距": "Spacing",
    "图案线宽": "Pattern width",
    "实线": "Solid",
    "虚线": "Dash",
    "点线": "Dot",
    "点划线": "Dash dot",
    "双点划线": "Dash dot dot",
    "短划线": "Short dash",
    "短点划线": "Short dash dot",
    "短双点划线": "Short dash dot dot",
    "长划线": "Long dash",
    "长点划线": "Long dash dot",
    "长双点划线": "Long dash dot dot",
    "实心": "Solid",
    "横线": "Horizontal",
    "竖线": "Vertical",
    "斜线": "Diagonal",
    "反斜线": "Backward diagonal",
    "十字交叉": "Cross",
    "斜线交叉": "Diagonal cross",
    "端头": "Cap",
    "连接": "Join",
    "滚轮缩放预览（最大 200%），双击复位": "Scroll to zoom the preview (up to 200%), double-click to reset",
    "渲染选项": "Rendering Options",
    "选中要素高亮": "Selected feature highlight",
    "填充颜色": "Fill colour",
    "描边宽度": "Stroke width",
    "容差": "Tolerance",
    "高亮 · 面": "Highlight · Polygon",
    "高亮 · 线": "Highlight · Line",
    "选中线要素的线宽，单位为屏幕像素。填0 表示跟随图层符号自身的线宽。": "Width of the selected line feature, in screen pixels. Enter 0 to follow the layer symbol's own line width.",
    "点选容差": "Pick tolerance",
    "捕捉容差": "Snapping tolerance",
    "填充透明度只对面要素生效（线与点的高亮需实心才能看清）；描边宽度选「自动」时，高亮比图层自身的线略粗一点。": "Fill transparency applies to polygon fills only (line and point highlights have to stay opaque to be visible); with an automatic stroke width the highlight is drawn slightly thicker than the layer's own line.",
    "画布": "Canvas",
    "背景色": "Background colour",
    "默认坐标系": "Default CRS",
    "新建地图视图时采用的默认坐标系。留空则按首个数据图层的坐标系自动推导。仅作为初值，每视图的坐标系可在视图内单独设定，不影响已打开的视图。": "Default coordinate reference system used when a new map view is created. Leave empty to auto-derive from the first data layer's CRS. This is only an initial value; each view's CRS can be set individually and does not affect already-open views.",
    "背景": "Background",
    "线条颜色": "Line colour",
    "注记颜色": "Label colour",
    "分段色 1": "Segment colour 1",
    "分段色 2": "Segment colour 2",
    "在地图上实时显示测量结果": "Show measurement results on the map",
    "打开后测量过程中会在地图上画出分段长度 / 总面积。": "When on, segment lengths and the total area are drawn on the map while measuring.",
    "几何简化按屏幕 1.2 像素的容差抽稀顶点：大数据量下明显更快，但小于该尺寸的碎多边形会被整个吃掉、相邻面之间可能留缝。默认关闭（几何原样绘制）。": "Simplification drops vertices with a 1.2-pixel screen tolerance: it is clearly faster on large datasets, but polygons smaller than that are swallowed whole and gaps may appear between neighbouring polygons. Off by default (geometry is drawn as-is).",
    "缓存位置对已经打开的数据要重新加载才彻底生效；缓存都是可再生的（瓦片、显示金字塔），删掉只会让下次变慢。": "A new cache location only takes full effect after the already-opened data is reloaded; everything in it is regenerable (tiles, display pyramids), so deleting it only makes the next load slower.",
    "（尚未保存到文件）": "(Not saved to a file yet)",
    "选择选项": "Selection Options",
    "编辑选项": "Editing Options",
    "识别 / 选择工具判定「点到要素」的距离（屏幕像素）：调大更容易点中细线，也更容易误选。": "How close a click has to be to count as hitting a feature (screen pixels): larger is easier to hit thin lines with, but also easier to mis-select.",
    "光标离吸附点这个距离（屏幕像素）以内就吸上去：调大更容易吸到，也更容易吸错。": "The cursor snaps once it is within this distance (screen pixels) of a snap point: larger is easier to snap with, but also easier to snap to the wrong thing.",
    "开不开捕捉、吸到哪些部位（端点 / 节点 / 交点 / 中点 / 边），在功能区的「捕捉」下拉里勾选。": "Whether snapping is on and which parts it snaps to (endpoint / vertex / intersection / midpoint / edge) are chosen in the Snapping drop-down on the ribbon.",
    "语言更改需要重启程序才完全生效。": "The language change only takes full effect after GmaGIS restarts.",
    "更改需要重启程序才完全生效。": "The change only takes full effect after GmaGIS restarts.",
    "界面缩放更改需要重启程序才完全生效。": "The interface scale change only takes full effect after GmaGIS restarts.",
    "要素总数": "Total features",
    "文件大小": "File size",
    "最后修改": "Last modified",
    "矢量 {0} / 栅格 {1}": "Vector {0} / Raster {1}",
    "只读：坐标系在「工程 → 工程属性」里设置": "Read-only: the coordinate system is set in Project > Project Properties",
    "{0} 已保存，重启程序后生效。": "{0} has been saved and takes effect after GmaGIS restarts.",
    "需要重启": "Restart required",
    "只影响新建的符号与预设；已有图层各自记着自己的单位，不会被改写。": "Only affects newly created symbols and presets; existing layers keep their own unit and are never rewritten.",
    "最近文档": "Recent projects",
    "最近工程": "Recent projects",
    "上一页": "Previous page",
    "下一页": "Next page",
    "{0} / {1}": "{0} / {1}",
    "新建空白工程": "Create a new empty project",
    "新建工程…": "New Project…",
    "新建工程开始工作，或打开一个已有工程。": "Create a new project to get started, or open an existing one.",
    "新建工程并选择视图类型": "Create a project and choose its view type",
    "新建工程失败：{0}": "Failed to create project: {0}",
    "选择新工程的视图类型：": "Choose the view type for the new project:",
    "视图类型": "View type",
    "保存位置": "Save to",
    "打开其他工程…": "Open another project…",
    "联系作者": "Contact author",
    "扫码赞助": "Donate",
    "（尚无最近工程）": "(No recent projects)",
    "新建工程并打开一张空白地图视图": "Create a project and open a blank map view",
    "新建一张空白地图视图": "Create a blank map view",
    "布局视图（{0}）": "Layout view ({0})",
    "模型构建器（{0}）": "Model builder ({0})",
    "正在优化": "Under optimization",
    "打开 .ggis 工程文件": "Open a .ggis project file",
    "{0}（文件已不存在）": "{0} (file missing)",
    "[错误] 打开最近工程失败：{0}": "[Error] Failed to open recent project: {0}",
    "[错误] 欢迎页操作失败：{0}": "[Error] Welcome page action failed: {0}",
    "（尚无最近文档）": "(No recent projects)",
    "{0}（文件不存在）": "{0} (file missing)",
    "清除最近文档列表": "Clear the recent projects list",
    "{0} 个图层": "{0} layer(s)",
    "工程文件": "Project file",
    "只读：位置由「另存为」决定": "Read-only; set by Save As",
    "工程文件与工程标题": "Project file and title",
    "距离 / 面积单位与坐标小数位": "Distance / area units and coordinate decimals",
    "测量结果与坐标显示的小数位数": "Decimals shown for measurements and coordinates",
    "数据源 / 几何类型 / 要素数 / 范围（只读）": "Source / geometry / feature count / extent (read-only)",
    "（有未保存的更改）": " (unsaved changes)",
    "更多颜色…": "More colors…",
    "标准色": "Standard",
    "色相环": "Hue wheel",
    "ColorBrewer": "ColorBrewer",
    "十六进制颜色，如 #1E88E5": "Hex color, e.g. #1E88E5",
    "透明度（0 = 全透明，255 = 不透明）": "Alpha (0 = transparent, 255 = opaque)",
    "红色": "Red",
    "绿色": "Green",
    "蓝色": "Blue",
    "点击打开颜色对话框": "Click to open the colour dialog",
    "快速选择颜色": "Quick colour picker",
    "色相": "Hue",
    "饱和度": "Saturation",
    "明度": "Value",
    "色相（0–359°）": "Hue (0–359°)",
    "饱和度（0–100%）": "Saturation (0–100%)",
    "明度（0–100%）": "Value (0–100%)",
    "透明度是颜色自身的通道；图层的整体透明见「符号系统」里的透明度。": "Alpha is a channel of the colour itself; for overall layer transparency use the Symbology opacity.",
    "从样式库选择": "Choose from the style library",
    "从符号系统选择": "Choose from Symbology",
    "从样式库选择...": "Choose from the style library...",
    "当前样式：{0}": "Current style: {0}",
    "取色": "Pick Colour",
    "点它之后对话框会收起，在窗口上点一下即取该处颜色（Esc 取消）": "The dialog hides; click once anywhere in the app window to sample the colour there (Esc to cancel)",

    "模型构建器": "Model Builder",
    "模型构建器初始化失败：{}": "Model Builder failed to initialize: {}",
    "按连线顺序执行整条处理链": "Run the whole chain in connection order",
    "把所有节点缩进视野": "Zoom out to show every node",
    "删除选中的节点或连线": "Delete the selected nodes or links",
    "清空整张模型（不影响已产出的图层）":
        "Clear the whole model (layers already produced are kept)",
    "删除节点": "Delete node",
    "删除选中": "Delete selected",
    "设为活动数据": "Set as active data",
    "适应窗口": "Fit to window",
    "数据": "Data",
    "节点参数": "Node parameters",
    "节点标题": "Node title",
    "分组字段": "Group by field",
    "（不分组）": "(no grouping)",
    "圆弧分段": "Arc segments",
    "容差 / 间距": "Tolerance / spacing",
    "添加到地图": "Add to map",
    "选择输出文件": "Choose output file",
    "留空 = 只放工程里，不写文件":
        "Leave empty to keep it in the project only",
    "从左侧拖入算法与数据图层，把输出口连到输入口即可":
        "Drag algorithms and data layers from the left, then connect an output port to an input port",
    "把算法拖到画布上；双击也可以添加":
        "Drag an algorithm onto the canvas (double-click also adds it)",
    "把图层拖到画布上作为输入；双击也可以添加":
        "Drag a layer onto the canvas as input (double-click also adds it)",
    "处理链的终点：决定结果叫什么、放不放进工程":
        "End of the chain: decides the result name and whether it joins the project",
    "（请选择图层）": "(choose a layer)",
    "（未命名图层）": "(unnamed layer)",
    "这个图层已不在工程中，请重新选择":
        "This layer is no longer in the project \u2014 choose another",
    "正在运行「{0}」…": "Running \u201c{0}\u201d\u2026",
    "有需要确认的地方": "Please confirm",
    "确认后开始运行": "Start the run when confirmed",
    "模型还不能运行": "The model cannot run yet",
    "无法连接": "Cannot connect",
    "这条连线不成立": "This link is not allowed",
    "已取消": "Cancelled",
    "「{0}」失败：{1}": "\u201c{0}\u201d failed: {1}",
    "「{0}」拿不到输入图层":
        "No input layer is available for \u201c{0}\u201d",
    "「{0}」没有产出结果": "\u201c{0}\u201d produced no result",
    "模型是空的——请从左侧拖入算法与数据图层":
        "The model is empty \u2014 drag an algorithm and a data layer in from the left",
    "模型里存在循环连线，无法确定执行顺序":
        "The model contains a cycle, so the run order cannot be determined",
    "「{0}」还没有选择图层": "\u201c{0}\u201d has no layer selected",
    "「{0}」的数据源图层已不在工程中":
        "The source layer of \u201c{0}\u201d is no longer in the project",
    "「{0}」还需要一路叠加输入":
        "\u201c{0}\u201d still needs an overlay input",
    "「{0}」缺少输入数据": "\u201c{0}\u201d has no input data",
    "模型里没有「结果」节点，跑完不知道结果放哪":
        "The model has no Result node, so there is nowhere to put the output",
    "「{0}」没有接到任何上游节点":
        "\u201c{0}\u201d is not connected to any upstream node",
    "「{0}」还没有起名字": "\u201c{0}\u201d still needs a name",
    "「{0}」的结果没有被任何结果节点接收，跑完不会保留":
        "The output of \u201c{0}\u201d is not consumed by any Result node and will be discarded",

    "着色": "Colouring",
    "重采样": "Resampling",
    "放大时": "When zooming in",
    "缩小时": "When zooming out",

    "栅格渲染": "Raster rendering",
    "矢量增强": "Vector enhancement",
    "缓存": "Cache",
    "对所有栅格图层生效。原来在符号系统的栅格页里逐图层设置，已收口到这里；"
    "放大 / 缩小时各用一种：放大用插值核（双线性 / 双三次…），"
    "缩小用聚合（平均值 / 众数）。":
        "Applies to every raster layer. This used to be set per layer on the "
        "Raster page of the Symbology panel and is now consolidated here. "
        "One mode for zooming in (interpolation kernels such as bilinear / "
        "cubic) and one for zooming out (aggregation such as average / mode).",

    "保存当前工程": "Save the current project",
    "不支持的文件类型": "Unsupported file type",
    "工程文件、工程标题与工程概况": "Project file, project title and summary",
    "地图坐标系（其他坐标系的数据会实时投影）": "Map CRS (data in other CRSs is projected on the fly)",
    "只读：在「坐标系」页里设置": "Read-only: set it on the Coordinate System page",
    "{0} px": "{0} px",
    "{}（{}）": "{} ({})",
    "{}（{}，单位 {}）": "{} ({}, unit {})",
    "打开配色方案编辑器（基于当前色带）": "Open the colour scheme editor (based on the current colour ramp)",
    "图层 / 数据源 / 范围": "Layer / data source / extent",
    "图层坐标系的参数（只读，可复制）": "Layer CRS parameters (read-only, copyable)",
    "已复制到剪贴板（{0} 字符）": "Copied to clipboard ({0} characters)",
    "选择数据源": "Select data source",
    "改完点「确定」会**按新数据源重新读取**；读不出来会原样保留当前数据并给出提示。": "Clicking OK re-reads the data from the new source. If it cannot be read, the current data is kept unchanged and you get a message",
    "服务地址": "Service address",
    "像素类型": "Pixel type",
    "无法打开坐标系选择框": "Could not open the CRS picker",
    "原因：{0}": "Reason: {0}",
    "换数据源失败：{0}": "Could not change the data source: {0}",
    "接管数据集失败": "Could not take over the dataset",
    "数据源不存在：{0}（当前图层未做任何改动）": "Data source not found: {0} (the layer was left untouched)",
    "不支持的文件类型：{0}（当前图层未做任何改动）": "Unsupported file type: {0} (the layer was left untouched)",
    "读取失败，已保留原数据源：{0}": "Reading failed; the previous data source is kept: {0}",
    "新旧数据源类型不一致（矢量 / 栅格不能互换），已取消": "The new data source has a different type (vector and raster are not interchangeable); cancelled",
    "服务地址无效：模板必须含 {x} {y} {z} 占位符（TMS 服务的行号也可写成 {-y}）": "Invalid service address: the template needs the {x} {y} {z} placeholders (TMS services may spell the row as {-y})",
    "已重新读取数据源：{0}": "Data source re-read: {0}",
    "数据源已更换：{0} → {1}": "Data source changed: {0} \u2192 {1}",
    "DPI": "DPI",
    "EPSG:3857": "EPSG:3857",
    "SQL": "SQL",
    "X": "X",
    "Y": "Y",
    "未保存：名字重复": "Not saved: duplicate name",
    "滚轮缩放、按住拖动移动预览，双击复位": "Scroll to zoom, drag to pan the preview, double-click to reset",
    "透明度：0% = 完全显示，100% = 完全透明": "Opacity: 0% = fully opaque, 100% = fully transparent",
    "透明度是颜色自身的通道（0% = 完全显示，100% = 完全透明）；图层的整体透明见「符号系统」里的透明度。": "Opacity is the colour's own alpha (0% = fully opaque, 100% = fully transparent); for the whole layer see Opacity in Symbology",
    "这是内存图层（还没有落盘的来源）；先用「导出」写出文件，之后就能在这里指定数据源。": "This is an in-memory layer with no file-backed source yet. Export it to a file first, then you can set the data source here",
    "四至": "Extent",
    "北": "North", "南": "South",
    "东": "East", "西": "West",
    "0% = 完全显示，100% = 完全透明":
        "0% = fully visible, 100% = fully transparent",
    "该格式只支持 8 位整型（当前 {0}），导出可能失败。":
        "This format accepts 8-bit data only (current: {0}); the export may fail.",
    "GeoPackage (*.gpkg)":
        "GeoPackage (*.gpkg)",
    "Esri Shapefile (*.shp)":
        "Esri Shapefile (*.shp)",
    "GeoJSON (*.geojson)":
        "GeoJSON (*.geojson)",
    "GeoJSON 序列 (*.jsonl)":
        "GeoJSON sequence (*.jsonl)",
    "FlatGeobuf (*.fgb)":
        "FlatGeobuf (*.fgb)",
    "GML (*.gml)":
        "GML (*.gml)",
    "KML (*.kml)":
        "KML (*.kml)",
    "CSV（WKT 几何列）(*.csv)":
        "CSV (WKT geometry column) (*.csv)",
    "MapInfo TAB (*.tab)":
        "MapInfo TAB (*.tab)",
    "MapInfo MIF (*.mif)":
        "MapInfo MIF (*.mif)",
    "AutoCAD DXF (*.dxf)":
        "AutoCAD DXF (*.dxf)",
    "MicroStation DGN (*.dgn)":
        "MicroStation DGN (*.dgn)",
    "SQLite (*.sqlite)":
        "SQLite (*.sqlite)",
    "Excel 工作簿 (*.xlsx)":
        "Excel workbook (*.xlsx)",
    "OpenDocument 表格 (*.ods)":
        "OpenDocument spreadsheet (*.ods)",
    "GeoTIFF (*.tif)":
        "GeoTIFF (*.tif)",
    "Cloud Optimized GeoTIFF (*.tif)":
        "Cloud Optimized GeoTIFF (*.tif)",
    "Erdas Imagine (*.img)":
        "Erdas Imagine (*.img)",
    "GDAL VRT（只记引用）(*.vrt)":
        "GDAL VRT (reference only) (*.vrt)",
    "GeoPackage 栅格 (*.gpkg)":
        "GeoPackage raster (*.gpkg)",
    "Arc/Info ASCII Grid (*.asc)":
        "Arc/Info ASCII Grid (*.asc)",
    "XYZ 文本网格 (*.xyz)":
        "XYZ text grid (*.xyz)",
    "ESRI .hdr Labelled (*.bil)":
        "ESRI .hdr Labelled (*.bil)",
    "netCDF (*.nc)":
        "netCDF (*.nc)",
    "ER Mapper (*.ers)":
        "ER Mapper (*.ers)",
    "Idrisi RST (*.rst)":
        "Idrisi RST (*.rst)",
    "SAGA GIS (*.sdat)":
        "SAGA GIS (*.sdat)",
    "JPEG 2000 (*.jp2)":
        "JPEG 2000 (*.jp2)",
    "PNG 图片 (*.png)":
        "PNG image (*.png)",
    "JPEG 图片 (*.jpg)":
        "JPEG image (*.jpg)",
    "BMP 图片 (*.bmp)":
        "BMP image (*.bmp)",
    "WebP 图片 (*.webp)":
        "WebP image (*.webp)",
    "GeoPackage":
        "GeoPackage",
    "Shapefile":
        "Shapefile",
    "GeoJSON":
        "GeoJSON",
    "GeoJSON 序列":
        "GeoJSON sequence",
    "FlatGeobuf":
        "FlatGeobuf",
    "GML":
        "GML",
    "KML":
        "KML",
    "CSV（WKT 几何列）":
        "CSV (WKT geometry column)",
    "MapInfo TAB":
        "MapInfo TAB",
    "MapInfo MIF":
        "MapInfo MIF",
    "AutoCAD DXF":
        "AutoCAD DXF",
    "MicroStation DGN":
        "MicroStation DGN",
    "SQLite / SpatiaLite":
        "SQLite / SpatiaLite",
    "Excel 工作簿":
        "Excel workbook",
    "OpenDocument 表格":
        "OpenDocument spreadsheet",

    "不勾：按百分位截断（%）；勾上：直接填最小 / 最大实际值":
        "Unchecked: percentile cut (%); checked: enter real min / max values",
    "拉伸区间的下界（实际值）":
        "Lower bound of the stretch range (real value)",
    "拉伸区间的上界（实际值）":
        "Upper bound of the stretch range (real value)",
    "当前区间":
        "Current range",
    "不拉伸":
        "No stretch",
    "当前实际生效的拉伸区间（起止值）；多波段合成时各波段各算一条":
        "The stretch range actually in effect (start / end values); with a multiband composite each band is stretched separately",
    "映射表":
        "Colour table",
    "按数据自动配色":
        "Auto-colour from data",
    "按数据里实际出现的取值，用数据源调色板或分类色板配一份颜色表":
        "Build a colour table from the values that actually occur, using the dataset palette or a categorical palette",
    "按数据源自带的调色板上色（共 {0} 类）":
        "Painted with the dataset's own palette ({0} classes)",
    "该数据源没有调色板；请改用唯一值或伪彩色。":
        "This dataset has no palette; use unique values or a pseudocolour renderer instead.",
    "点击配置这个样式":
        "Click to configure this style",
    "分类符号：{0}":
        "Class symbol: {0}",
    "分级符号：{0} – {1}":
        "Graduated symbol: {0} - {1}",
    "分级符号":
        "Graduated symbol",
    "线样式":
        "Line style",
    "填充图案":
        "Fill pattern",
    "图案间距":
        "Pattern spacing",
    "色彩映射表（数据源）":
        "Colour map (data source)",
    "唯一值（分类）":
        "Unique values (categorised)",
    "红波段 (R)":
        "Red band (R)",
    "绿波段 (G)":
        "Green band (G)",
    "蓝波段 (B)":
        "Blue band (B)",

    "显示消息":
        "Show messages",
    "正常":
        "Normal",
    "成功":
        "Success",
    "警告":
        "Warning",
    "错误":
        "Error",
    "控件画廊":
        "Widget gallery",
    "Ggs 控件画廊":
        "Ggs widget gallery",
    "浏览项目内全部 Ggs 标准控件的外观":
        "Browse the look of all Ggs standard widgets in the project",
    "控件画廊加载失败：{}":
        "Failed to load the widget gallery: {}",
    "按钮":
        "Buttons",
    "Ggs 专属":
        "Ggs-specific",
    "树":
        "Tree",
    "表格":
        "Table",
    "询问":
        "Question",
    "只读值行":
        "Read-only value row",
    "只读文本，可选中复制":
        "Read-only text, selectable and copyable",
    "这是一条信息消息。":
        "This is an information message.",
    "这是一条警告消息。":
        "This is a warning message.",
    "这是一条错误消息。":
        "This is a critical message.",
    "这是一个询问，需要你确认。":
        "This is a question that needs your confirmation.",
    "打开对话框样例":
        "Open a sample dialog",
    "对话框样例":
        "Sample dialog",
    "这是 GgsDialog 对话框壳样例。":
        "This is a GgsDialog shell sample.",
    "单行文本":
        "Line edit",
    "下拉框":
        "Combo box",
    "复选框":
        "Check box",
    "单选":
        "Radio button",
    "滑块":
        "Slider",
    "对话框":
        "Dialog",
    "普通按钮":
        "Push button",
    "带图标按钮":
        "Button with icon",
    "可勾选按钮":
        "Checkable button",
    "禁用按钮":
        "Disabled button",
    "文件夹":
        "Folder",
    "扫帚":
        "Broom",
    "多行文本":
        "Plain text edit",
    "分组框":
        "Group box",
    "选项卡":
        "Tabs",
    "滚动条":
        "Scroll bar",
    "工具按钮":
        "Tool button",
    "视图选项卡":
        "View tabs",
    "消息条":
        "Message bar",
    "这是一条消息条消息。":
        "This is a message-bar message.",
    "弹一条消息":
        "Push a message",
    "坐标系选择":
        "CRS selector",
    "搜索框":
        "Search bar",
    "色带一":
        "Ramp 1",
    "色带二":
        "Ramp 2",
    "输入对话框样例":
        "Sample input dialog",
    "请输入内容":
        "Please enter text",
    "打开输入对话框样例":
        "Open a sample input dialog",
    "输入图层":
        "Input layer",
    "输出图层":
        "Output layer",
    "图层输入与输出":
        "Layer input / output",
    "请选择图层":
        "Select a layer",
    "示例矢量图层":
        "Sample vector layer",
    "示例栅格图层":
        "Sample raster layer",
    "打开文件":
        "Open file",
    "保存文件":
        "Save file",
    "所有支持的格式":
        "All supported formats",
    "输入文件":
        "Input file",
    "选择文件":
        "Choose file",
    "文件输入与输出":
        "File input / output",
    "其他":
        "Other",
    "剖面":
        "Profile",
    "剖面曲线只对栅格图层有效，请先选中一个栅格图层":
        "Profiles only work on raster layers; select a raster layer first",
    "已移除分组「{0}」":
        "Group \u201c{0}\u201d removed",


    "点击：设置地图坐标系":
        "Click: set the project CRS",
    "请先选择一个坐标系":
        "Please select a coordinate system first",
    "在左侧树里选一个坐标系，或在上方输入 EPSG 编号 / PROJ 串 / WKT 后点「确定」。":
        "Pick a coordinate system in the tree on the left, or type an EPSG code / PROJ string / WKT above and press OK.",
    "新建坐标系（地理 / 投影 / 从字符串）":
        "New coordinate system (geographic / projected / from a string)",
    "新建地理坐标系…":
        "New geographic coordinate system…",
    "新建投影坐标系…":
        "New projected coordinate system…",
    "从字符串创建（WKT / PROJ）…":
        "Create from a string (WKT / PROJ)…",
    "从字符串新建坐标系":
        "New coordinate system from a string",
    "粘贴 WKT、PROJ 串或 EPSG 编号（如 EPSG:4526）":
        "Paste a WKT, a PROJ string or an EPSG code (e.g. EPSG:4526)",
    "留空则用字符串自带的名字":
        "Leave blank to use the name in the string",
    "支持 WKT、PROJ 串与 EPSG 编号；解析成功后才能点「确定」。":
        "WKT, PROJ strings and EPSG codes are supported; OK becomes available once it parses.",
    "字符串无法解析":
        "Could not parse the string",
    "这一段认不出来：请检查 WKT / PROJ 串 / EPSG 编号是否完整正确。":
        "Not recognised: check that the WKT / PROJ string / EPSG code is complete and correct.",
    "经度范围":
        "Longitude range",
    "纬度范围":
        "Latitude range",
    "常用":
        "Common",
    "本初子午线":
        "Prime meridian",
    "子午线经度":
        "Meridian longitude",
    "自定义本初子午线：相对格林尼治的东经度数":
        "Custom prime meridian: degrees east of Greenwich",
    "自定义椭球…":
        "Custom ellipsoid…",
    "长半轴":
        "Semi-major axis (a)",
    "扁率倒数":
        "Inverse flattening (1/f)",
    "分级（{0} 个类）":
        "Graduated ({0} classes)",
    "m 参数":
        "m",
    "q 参数":
        "q",
    "路径号":
        "Path",
    "卫星高度":
        "Satellite height",
    "UTM 带号（1–60）":
        "UTM zone (1–60)",
    "真比例纬线":
        "Latitude of true scale",
    "第一点经度":
        "First point longitude",
    "第二点经度":
        "Second point longitude",
    "斜轴中心经线":
        "Oblique central meridian",
    "斜轴方位角":
        "Oblique azimuth",
    "斜轴偏转角":
        "Oblique gamma",
    "方位角":
        "Azimuth",
    "倾斜角":
        "Tilt",
    "n 参数":
        "n",
    "通用横轴墨卡托（UTM）":
        "Universal Transverse Mercator (UTM)",
    "扩展横轴墨卡托（EtMerc）":
        "Extended Transverse Mercator (EtMerc)",
    "兰勃特等角圆锥（2 标准纬线）":
        "Lambert Conformal Conic (2 standard parallels)",
    "等距圆锥":
        "Equidistant Conic",
    "等积圆柱（Lambert）":
        "Lambert Cylindrical Equal Area",
    "等距圆柱（Plate Carrée）":
        "Equirectangular (Plate Carrée)",
    "米勒圆柱":
        "Miller Cylindrical",
    "兰勃特方位等积":
        "Lambert Azimuthal Equal Area",
    "立体投影（极球面）":
        "Stereographic (Polar)",
    "斜轴立体（Oblique Stereographic）":
        "Oblique Stereographic",
    "瑞士斜轴墨卡托":
        "Swiss Oblique Mercator",
    "捷克 Krovak":
        "Krovak",
    "斜轴墨卡托（Hotine）":
        "Hotine Oblique Mercator",
    "横轴等积圆柱":
        "Transverse Cylindrical Equal Area",
    "摩尔威德":
        "Mollweide",
    "罗宾逊":
        "Robinson",
    "正弦曲线（Sinusoidal）":
        "Sinusoidal",
    "自然地球":
        "Natural Earth",
    "古德等积（Homolosine）":
        "Goode Homolosine",
    "正射投影（Orthographic）":
        "Orthographic",
    "球心投影（Gnomonic）":
        "Gnomonic",
    "地球同步卫星视图":
        "Geostationary Satellite View",
    "近侧透视（Vertical Perspective）":
        "Vertical Perspective",
    "Airy 最小误差方位":
        "Airy Minimum Error Azimuthal",
    "阿拉斯加圆锥（Modified Stereo）":
        "Alaska Conformal (Modified Stereo)",
    "Apian 球面":
        "Apian Globular",
    "August 极射":
        "August Epicycloidal",
    "Bacon 球面":
        "Bacon Globular",
    "双极圆锥（Bipolar Conic）":
        "Bipolar Conic",
    "Boggs 等积":
        "Boggs Equal Area",
    "Bonne 等积圆锥":
        "Bonne",
    "Cartesian（笛卡儿）":
        "Cartesian",
    "卡西尼（Cassini-Soldner）":
        "Cassini-Soldner",
    "中央圆柱（Central Cylindrical）":
        "Central Cylindrical",
    "Collignon 等积":
        "Collignon",
    "紧凑米勒（Compact Miller）":
        "Compact Miller",
    "Craster 抛物线":
        "Craster Parabolic",
    "Denoyer 半立方":
        "Denoyer Semi-Elliptical",
    "等积地球（Equal Earth）":
        "Equal Earth",
    "Gall 立体":
        "Gall Stereographic",
    "地心直角坐标（Geocentric）":
        "Geocentric",
    "通用正弦（General Sinusoidal）":
        "General Sinusoidal",
    "高斯-施赖伯横轴墨卡托":
        "Gauss-Schreiber Transverse Mercator",
    "Hammer 等积":
        "Hammer",
    "Hatano 非对称等积":
        "Hatano Asymmetrical Equal Area",
    "国际椭球专用（Interrupted Goode）":
        "Interrupted Goode Homolosine",
    "ISEA 离散全球网格":
        "ISEA Discrete Global Grid",
    "Laskowski 三角":
        "Laskowski Tri-Optimal",
    "经纬度（Lat/Lon）":
        "Geographic (Lat/Lon)",
    "经纬度（Long/Lat）":
        "Geographic (Long/Lat)",
    "经纬度（Lon/Lat）":
        "Geographic (Lon/Lat)",
    "自然地球 II":
        "Natural Earth II",
    "Nell 准等积":
        "Nell-Hammer",
    "Nicolosi 全球":
        "Nicolosi Globular",
    "斜轴等积圆柱":
        "Oblique Cylindrical Equal Area",
    "Patterson 圆柱":
        "Patterson Cylindrical",
    "多圆锥（Polyconic）":
        "Polyconic",
    "四边球面立方（Quadrilateralized）":
        "Quadrilateralized Spherical Cube",
    "Roussilhe 斜轴立体":
        "Roussilhe Oblique Stereographic",
    "矩形多圆锥":
        "Rectangular Polyconic",
    "立体投影":
        "Stereographic",
    "倾斜中央圆柱":
        "Tilted Central Cylindrical",
    "倾斜透视（Tilted Perspective）":
        "Tilted Perspective",
    "两等距点（Two Point Equidistant）":
        "Two Point Equidistant",
    "通用极球面（UPS）":
        "Universal Polar Stereographic (UPS)",
    "Urmaev 平极正弦":
        "Urmaev Flat-Polar Sinusoidal",
    "Winkel 三角":
        "Winkel Tripel",
    "Laborde 斜轴墨卡托":
        "Laborde Oblique Mercator",
    "埃及斜轴墨卡托（MisrSOM）":
        "Egypt Oblique Mercator (MisrSOM)",
    "格林尼治（0°）":
        "Greenwich (0°)",
    "巴黎（2.3372°E）":
        "Paris (2.3372°E)",
    "雅典（23.4259°E）":
        "Athens (23.4259°E)",
    "伯尔尼（7.2623°E）":
        "Bern (7.2623°E)",
    "波哥大（74.0451°W）":
        "Bogota (74.0451°W)",
    "布鲁塞尔（4.2205°E）":
        "Brussels (4.2205°E)",
    "哥本哈根（12.3440°E）":
        "Copenhagen (12.3440°E)",
    "费罗（17.4°W）":
        "Ferro (17.4°W)",
    "雅加达（106.4828°E）":
        "Jakarta (106.4828°E)",
    "里斯本（9.0755°W）":
        "Lisbon (9.0755°W)",
    "马德里（3.4115°W）":
        "Madrid (3.4115°W)",
    "奥斯陆（10.4323°E）":
        "Oslo (10.4323°E)",
    "罗马（12.4523°E）":
        "Rome (12.4523°E)",
    "斯德哥尔摩（18.0583°E）":
        "Stockholm (18.0583°E)",
    "自定义经度…":
        "Custom longitude…",
    "复制坐标系定义（WKT）": "Copy coordinate system definition (WKT)",
    "已复制坐标系定义（WKT）": "Coordinate system definition copied (WKT)",
    "导入坐标系…": "Import coordinate system…",
    "导入坐标系": "Import coordinate system",
    "从字符串创建…": "Create from string…",
    "导出坐标系到文件（WKT）": "Export coordinate system to file (WKT)",
    "栅格与矢量数据": "Raster and vector data",
    "坐标系文件": "Coordinate system file",
    "读取失败：{0}": "Read failed: {0}",
    "没能从该文件读出坐标系":
        "Could not read a coordinate system from this file",
    "没能解析出有效的坐标系": "Could not parse a valid coordinate system",
    "已导入坐标系：{0}": "Coordinate system imported: {0}",
    "已复制{0}到剪贴板": "{0} copied to clipboard",
    "已导出坐标系定义到：{0}":
        "Coordinate system definition exported to: {0}",
    "这个坐标系没有 WKT 形式": "This coordinate system has no WKT form",
    "导出失败：{0}": "Export failed: {0}",
    "特别声明": "Special notices",
    "查看第三方许可声明": "View third-party license notices",
    "本软件的许可声明": "License notice for this software",
    "本软件许可声明": "Software license notice",
    "许可证类型": "License type",
    "许可证文件": "License file",
    "随包未附带单独文件（弱 copyleft 的全文见 THIRD_PARTY_NOTICES.md）":
        "No standalone file shipped (weak-copyleft full texts: see THIRD_PARTY_NOTICES.md)",
    "PROJ 串": "PROJ string",
    "EPSG 编号": "EPSG code",
    "复制坐标系定义（{0}）": "Copy coordinate system definition ({0})",
    "已复制坐标系定义（{0}）": "Coordinate system definition copied ({0})",
    "这个坐标系没有 {0} 形式": "This coordinate system has no {0} form",
    "双击「下限 / 上限」可手动修改分级区间": "Double-click Lower / Upper to edit the class breaks manually",
    "分级区间无效": "Invalid class breaks",
    "上下限必须严格递增（每一档的下限小于上限，且相邻两档的断点不能相等）；已忽略这次修改。": "Lower and upper limits must increase strictly (each class's lower bound is below its upper bound, and adjacent break values must differ); this change was ignored.",
    "编辑规则": "Edit Rule",
    "留空 = 匹配全部要素": "Leave empty to match all features",
    "图例里显示的名字": "Name shown in the legend",
    "打开表达式构建器": "Open expression builder",
    "无法打开表达式构建器": "Cannot open the expression builder",
    "规则符号": "Rule symbol",
    "兜底规则无条件命中（用来兜住前面都不匹配的要素），所以没有过滤表达式。": "The else rule matches unconditionally (it catches features that match none of the rules above), so it has no filter expression.",
    "无法打开规则编辑窗口": "Cannot open the rule editor",
    "添加图层": "Add Layers",
    "已选 {0} / {1}": "Selected {0} / {1}",
    "埃克特 I": "Eckert I",
    "埃克特 II": "Eckert II",
    "埃克特 III": "Eckert III",
    "埃克特 IV": "Eckert IV",
    "埃克特 V": "Eckert V",
    "埃克特 VI": "Eckert VI",
    "范德格林滕 I": "van der Grinten I",
    "范德格林滕 II": "van der Grinten II",
    "范德格林滕 III": "van der Grinten III",
    "范德格林滕 IV": "van der Grinten IV",
    "艾托夫": "Aitoff",
    "法赫伊": "Fahey",
    "富科": "Foucaut",
    "金斯堡 VIII": "Ginsburg VIII",
    "拉格朗日": "Lagrange",
    "拉里维": "Larrivée",
    "洛希等距": "Loximuthal",
    "奥特柳斯": "Ortelius",
    "乌尔马耶夫 V": "Urmaev V",
    "瓦格纳 I": "Wagner I",
    "瓦格纳 II": "Wagner II",
    "瓦格纳 III": "Wagner III",
    "瓦格纳 IV": "Wagner IV",
    "瓦格纳 V": "Wagner V",
    "瓦格纳 VI": "Wagner VI",
    "瓦格纳 VII": "Wagner VII",
    "温克尔 I": "Winkel I",
    "温克尔 II": "Winkel II",
    "世界与伪圆柱投影": "World and pseudocylindrical projections",
    "CGCS2000": "CGCS2000",
    "北京 1954": "Beijing 1954",
    "西安 1980": "Xian 1980",
    "NAD83": "NAD83",
    "NAD27": "NAD27",
    "ETRS89": "ETRS89",
    "ED50": "ED50",
    "GDA94 / GDA2020": "GDA94 / GDA2020",
    "日本 JGD": "Japan JGD",
    "其他基准": "Other datums",
    "分类（{0} 个值）": "Categorized ({0} values)",
    "无法打开样式配置窗口": "Cannot open the symbol editor",
    "背景值": "Background value",
    "RGB 合成": "RGB composite",
    "显示背景值": "Show background value",
    "勾上才把背景值画出来；颜色设成全透明同样等于不画": "Tick to draw background values; a fully transparent color also means not drawn",
    "色彩合成": "Colour composite",
    "色彩映射表": "Colour map",
    "调色板": "Palette",
    "计算当前波段的全部唯一值并加入下表":
        "Compute all unique values of the current band and add them to the list",
    "分类数较多（{0} 个）": "Many classes ({0})",
    "分类/分级数过多时提醒":
        "Warn when there are too many classes/grades",
    "提醒阈值": "Warn above",
    " 个": " classes",
    "渲染出错，详见日志": "Render error - see the log",
    "正在统计当前波段的全部取值…":
        "Collecting all values of the current band...",
    "重建分级": "Rebuild classes",
    "正在按字段重新计算断点…": "Recomputing breaks from the field...",
    "重建分类": "Rebuild categories",
    "正在按字段重新分类…": "Recategorising by field...",
    "类数超过这个值就弹一次提醒；同一档只提醒一次（越调越大才再提醒，调回阈值以内后下次再超还会提醒）。只提醒，不会改动你设的类数。":
        "A one-off reminder appears when the number of classes exceeds this "
        "value (once per value; it re-arms after you drop back below the "
        "threshold). It only reminds - your class count is never changed.",
    "正在渲染": "Rendering",
    "正在渲染：{0}": "Rendering: {0}",
    "当前波段取值过于连续（不同值超过 256 个），无法按唯一值渲染；请改用拉伸 / 分类。":
        "This band is too continuous (more than 256 distinct values) for unique "
        "values; use Stretch or Classification instead.",
    "{0} 波段": "{0} band",
    "数据源自带的调色板（当前生效的配色）": "Palette provided by the data source (currently applied colours)",
    "恢复为数据源自带的配色": "Restore the colours provided by the data source",
    "0% = 完全显示，100% = 完全透明；不影响像素本身，拖动时不必重算图像":
        "0% = fully shown, 100% = fully transparent; does not affect the "
        "pixels themselves, so dragging needs no recomputation",
    "改段数会按拉伸区间重新均分断点（已改过的区间会被重置）":
        "Changing the class count re-splits the breaks evenly over the "
        "stretch range (edited ranges are reset)",
    "最大最小": "Minimum / Maximum",
    "百分比截断": "Percent clip",
    "直方图均衡化": "Histogram equalize",
    "直方图规定化": "Histogram specification",
    "拉伸设置": "Stretch settings",
    "标注值": "Range labels",
    "恢复为当前类型算出来的区间":
        "Restore the range computed from the current type",
    "当前生效拉伸区间的上界（只读）":
        "Upper bound of the active stretch range (read-only)",
    "当前生效拉伸区间的下界（只读）":
        "Lower bound of the active stretch range (read-only)",
    "拉伸区间的上界（实际值）；改动会自动切到「自定义」":
        "Upper bound of the stretch range (actual value); editing it "
        "switches the type to Custom",
    "拉伸区间的下界（实际值）；改动会自动切到「自定义」":
        "Lower bound of the stretch range (actual value); editing it "
        "switches the type to Custom",
    "分级色彩": "Graduated colours",
    "基于规则": "Rule-based",
    "方法": "Method",
    "显示其他所有值": "Show all other values",
    "勾上：值不在列表里的要素照常画出，并按下面那一行的颜色着色；不勾：这些要素不画": "Checked: features whose value is not listed are still drawn with the colour of the row below; unchecked: they are not drawn",
    "共 {0} 个分类值": "{0} categories",
    "条件": "Condition",
    "透明度波段": "Transparency band",
    "参考波段": "Reference band",
    "改段数会按当前方法重新算断点（自定义时按拉伸区间重新均分）": "Changing the class count recomputes the breaks with the current method (with Custom they are re-split evenly over the stretch range)",
    "读取中": "Reading",
    "正在读取…": "Reading…",
    "正在读取：{0}": "Reading: {0}",
    "正在读取工程：{0}": "Reading project: {0}",
    "读取数据": "Reading data",
    "正在建立显示金字塔，之后缩放平移会明显更快…":
        "Building the display pyramid; zooming and panning will be much "
        "faster afterwards…",

    "删除规则": "Delete rule",
    "编辑规则…": "Edit rule…",
    "图例中「最大」那个标注的文字（不影响渲染）；留空 = 用上面的值":
        "Text for the “Max” annotation in the legend (does not affect "
        "rendering); empty = use the value above",
    "图例中「最小」那个标注的文字（不影响渲染）；留空 = 用上面的值":
        "Text for the “Min” annotation in the legend (does not affect "
        "rendering); empty = use the value above",
    "无法打开过滤对话框": "Cannot open the filter dialog",
    "规则样式": "Rule style",
    "新增值": "Add value",
    "新增值…": "Add value…",
    "新增值（从未添加的值里挑一个）": "Add a value (pick one from the values not yet added)",
    "删除值": "Remove value",
    "删除值（删除当前行）": "Remove value (delete the current row)",
    "新增所有值": "Add all values",
    "新增所有值（把剩下没添加的值一次补齐）":
        "Add all values (add every remaining value at once)",
    "选择要添加的值": "Choose a value to add",
    "新建分级": "New class",
    "新建分级（在选中那一档里再分出一档）":
        "New class (split the selected class in two)",
    "删除分级": "Remove class",
    "删除分级（区间并入相邻档）":
        "Remove class (its range is merged into the neighbouring class)",
    "编辑样式…": "Edit style…",
    "（已隐藏 {0} 个不含数据的分级）":
        " ({0} classes with no data are hidden)",
    "地图当前被一个模态对话框挡住，取不到颜色。请先关掉它，再回到这里取色。":
        "The map is covered by a modal dialog right now, so no colour can "
        "be picked. Close that dialog and come back here to pick a colour.",

    "编辑色带…": "Edit Colour Ramp…",
    "内置色带只读；「新建 / 复制为自定义」后用「编辑色带…」改色标，再点「保存」":
        "Built-in ramps are read-only; use New / Copy as custom, then Edit"
        "Colour Ramp… to change the stops, and press Save.",
    "色标已改，点「保存」写入": "Stops changed - press Save to write them.",
    "已新建：{0}（可在「编辑色带…」里改色标）": "Created: {0} (change its stops via Edit Colour Ramp…)",
    "已复制：{0}": "Copied: {0}",
    "色标至少要有两个": "A colour ramp needs at least two stops",
    "色带保存失败（色标不合法？）": "Saving the colour ramp failed (invalid stops?)",
    "色带保存失败（名字为空或色标少于两个）": "Saving the colour ramp failed (empty name, or fewer than two stops)",
    "共 {0} 个色标": "{0} stops",
    "色带编辑器不可用": "The colour-ramp editor is unavailable",
    "标注表达式": "Label expression",
    "选择字段，或输入含 [字段名] 的表达式": "Pick a field, or type an expression containing [field]",
    "从下拉选择字段会在光标处插入 [字段名]；也可直接输入表达式，如 [name] 或 [name]（[code]）": "Picking a field inserts [field] at the cursor; you can also type an expression such as [name] or [name] ([code])",
    "高级": "Advanced",
    "例如：[地名] + \" \" + [区划码]": "e.g. [name] + \" \" + [code]",
    "重置为打开时的内容": "Reset to the value it had when opened",
    "验证：用图层第一个要素的真实值算一遍": "Verify: evaluate with the real values of the first feature",
    "复制表达式": "Copy expression",
    "过滤": "Filter",
    "输入关键字过滤": "Type to filter",
    "函数": "Functions",
    "表达式已复制到剪贴板": "Expression copied to the clipboard",
    "表达式为空": "The expression is empty",
    "图层没有要素，无法验证": "The layer has no features, nothing to verify",
    "验证通过，但结果是空文字（检查字段名）": "Verified, but the result is empty text (check the field name)",
    "验证通过（用第一个要素）：{0}": "Verified (first feature): {0}",
    "验证失败：{0}": "Verification failed: {0}",
    "打开标注表达式对话框（字段 / 函数）": "Open the label expression dialog (fields / functions)",
    "当前表达式：{0}": "Current expression: {0}",
    "首字母大写、其余小写": "Capitalize the first letter",
    "全部小写": "Lower case",
    "全部大写": "Upper case",
    "每个词首字母大写": "Title case (first letter of every word)",
    "大小写互换": "Swap case",
    "去掉首尾空白": "Strip leading and trailing spaces",
    "去掉左侧空白": "Strip leading spaces",
    "去掉右侧空白": "Strip trailing spaces",
    "把「旧」替换成「新」": "Replace old with new",
    "左侧补 0 到指定宽度（区划码常用）": "Left-pad with zeros",
    "居中并用填充字符补齐": "Center and pad",
    "左对齐并用填充字符补齐": "Left-align and pad",
    "右对齐并用填充字符补齐": "Right-align and pad",
    "数值四舍五入到指定小数位（本项目扩展）": "Round a number to N decimals (project extension)",
    "双击字段：插入到表达式": "Double-click a field to insert it",
    "双击函数：插入到表达式（需勾选「高级」）": "Double-click a function to insert it (requires Advanced)",
    "勾选后可用 Python 函数（如 [name].upper()）自定义表达式": "Checked: you can use Python functions (e.g. [name].upper()) to customise the expression",
    "请先勾选「高级」再使用函数": "Check Advanced first to use functions",
    "表达式里用了 Python 函数，请勾选「高级」": "The expression uses Python functions; please check Advanced",
    "双击函数：插入到表达式": "Double-click a function to insert it",
    "勾选后表达式按 Python 代码执行：可用 def 定义自己的函数": "Checked: the expression runs as Python code (define your own function with def)",
    "例如：def FindLabel(attrs): 然后 return [地名] + ' ' + [区划码]": "e.g. def FindLabel(attrs): then return [name] + ' ' + [code]",
    "（默认）": "(Default)",
    "输入以搜索字体": "Type to search fonts",
    "清除表达式": "Clear the expression",
    "地图视图": "Map view",
    "新建布局视图": "New layout view",
    "关闭视图": "Close view",
    "关闭其他视图": "Close other views",
    "关闭全部视图": "Close all views",
    "确定要关闭全部 {0} 个视图吗？":
        "Close all {0} view(s)?",
    "重命名…": "Rename…",
    "重命名视图": "Rename view",
    "名称：": "Name:",
    "已关闭视图（布局仍保留在工程中）":
        "View closed (the layout is kept in the project)",
    "已关闭视图（模型仍保留在工程中）":
        "View closed (the model is kept in the project)",
    "新建布局失败：{0}": "Failed to create the layout: {0}",
    "布局视图打开失败：{0}": "Failed to open the layout view: {0}",
    "视图容器或当前布局不可用":
        "the view container or the current layout is unavailable",
    "新建视图": "New view",
    "地图视图（切回已有）": "Map view (switch back to the existing one)",
    "布局视图": "Layout view",
    "模型构建器打开失败：{0}": "Failed to open the model builder: {0}",
    "模型": "Model",
    "新建模型构建器": "New Model Builder",
    "中断正在运行的模型": "Abort the running model",
    "置于顶层": "Bring to Front",
    "置于底层": "Send to Back",
    "移到所有元素之上": "Move above all elements",
    "移到所有元素之下": "Move below all elements",
    "分布": "Distribute",
    "横向分布": "Distribute Horizontally",
    "纵向分布": "Distribute Vertically",
    "把选中元素按等间距分布（至少选 3 个）": "Space the selected elements evenly (select at least 3)",
    "分布至少需要选中 3 个元素": "Distributing needs at least 3 selected elements",
    "已按等间距分布 {0} 个元素": "Distributed {0} elements evenly",
    "已置于顶层": "Brought to front",
    "已置于底层": "Sent to back",
    "在右侧「元素设置」里改这个元素": "Edit this element in \u201cElement Settings\u201d on the right",

    "视图属性": "View Properties",
    "视图属性…": "View Properties…",
    "视图名称": "View name",
    "视图名称：": "View name:",
    "视图标识（不可修改）": "View ID (read-only)",
    "地图（切回已有）": "Map (switch to existing)",


    "添加到画布": "Add to canvas",
    "未选中节点": "No node selected",
    "在画布上点一个节点，这里显示它的参数与连线":
        "Click a node on the canvas to see its parameters and links here",
    "数据 · {0}": "Data · {0}",
    "算子 · {0}": "Operator · {0}",
    "结果 · {0}": "Result · {0}",
    "未选择图层": "No layer selected",
    "未命名": "Untitled",
    "画布上这个节点显示的名字；留空则用默认名":
        "Name shown for this node on the canvas; empty = default name",
    "这个节点读取工程里的哪一份矢量图层": "Which vector layer of the project this node reads",
    "跑完之后结果图层用什么名字": "Name of the result layer after the run",
    "选择要写出的文件": "Choose the file to write",
    "这个算法没有可调参数": "This algorithm has no adjustable parameters",
    "负数为收缩（腐蚀）": "A negative value shrinks (erodes) the features",
    "留空 = 全部融成一个要素": "Empty = merge everything into one feature",
    "去重字段": "Deduplicate field",
    "留空 = 按几何去重；选了字段 = 按该字段取值去重":
        "Empty = deduplicate by geometry; a field = deduplicate by its value",
    "输入{0}": "Input {0}",
    "图层已不在工程中": "layer is no longer in the project",
    "（节点已删除）": "(node deleted)",

    "至少要保留一个视图": "At least one view must remain",
    "已关闭地图视图（再点「＋」可随时打开）": "Map view closed (use + to open it again)",
    "地图视图打开失败：{0}": "Could not open the map view: {0}",
    "导出数据": "Export data",
    "导出样式": "Export style",
    "导出图层样式": "Export layer style",
    "导出样式失败：{0}": "Style export failed: {0}",
    "导出样式：{0} → {1}": "Export style: {0} → {1}",
    "已导出图层样式 → {0}": "Layer style exported → {0}",
    "GmaGIS 图层样式 (*.ggisstyle);;JSON (*.json)":
        "GmaGIS layer style (*.ggisstyle);;JSON (*.json)",

    "栅格重采样": "Raster resampling",
    "栅格缓存": "Raster cache",
    "存储位置": "Storage location",
    "日志文件": "Log file",

    "渲染方法": "Rendering method",
    "CPU 子进程（默认）": "CPU subprocess (default)",
    "GPU 瓦片合成": "GPU tile compositing",

    "毫米": "Millimeters",
    "厘米": "Centimeters",
    "英寸": "Inches",
    "布局名称": "Layout name",
    "宽度 × 高度": "Width × Height",
    "缩放到视图范围": "Zoom to view extent",
    "缩放到比例尺": "Zoom to scale",
    "把激活地图框的范围设成主窗口地图视图当前的范围":
        "Set the active map frame extent to the current map view extent",
    "把激活地图框的比例尺设成主窗口地图当前的比例尺":
        "Set the active map frame scale to the current map scale",

    "点选": "Point",
    "多边形": "Polygon",
    "圆": "Circle",
    "拖框选择元素": "Drag a box to select elements",
    "逐点点击画多边形，双击 / 右键 / 回车闭合":
        "Click to add points; double-click / right-click / Enter to close",
    "按住左键自由描圈选择": "Hold the left button and draw freely to select",
    "按住拖出圆（内切椭圆）选择": "Drag out a circle (inscribed ellipse) to select",
    "拖一条线，选中与它相交的元素": "Drag a line to select the elements it crosses",
    "按元素类型选择（地图框 / 图例 / 比例尺 …）":
        "Select by element type (map frame / legend / scale bar …)",
    "选中与当前选中元素相交的元素": "Select elements that intersect the current selection",
    "选择方式：{0}": "Select mode: {0}",
    "已按类型选中 {0} 个元素": "Selected {0} element(s) by type",
    "页面里没有这种元素": "No element of this type on the page",
    "请先选中一个元素，再按位置选择": "Select an element first, then use Select By Location",
    "已按位置追加选中 {0} 个元素": "Added {0} element(s) by location",

    "在页面上拖出一个方框 = 插入{0}（Esc / 右键取消）":
        "Drag a box on the page to insert {0} (Esc / right-click to cancel)",
    "插入地图框（在页面上拖出一个方框）": "Insert map frame (drag a box on the page)",
    "（无地图视图）": "(No map view)",
    "请先选中一个地图框": "Select a map frame first",
    "请先选中一个地图框，再开关格网": "Select a map frame first, then toggle its grid",
    "格网创建失败：{0}": "Failed to create the grid: {0}",
    "已为地图框「{0}」打开格网": "Grid enabled for map frame: {0}",
    "已关闭该地图框的格网": "Map frame grid turned off",
    "给这个地图框加格网（取消 = 删掉）；格网贴着地图框的边框、跟着它一起移动缩放":
        "Add a grid to this map frame (uncheck to remove); the grid follows the frame border as it moves and scales",
    "需要先打开地图视图（＋ → 地图）": "Open a map view first (＋ → Map)",

    "从 .ggismodel 文件读入一张模型": "Import a model from a .ggismodel file",
    "写点说明（会显示在画布上）：": "Write a note (it will be shown on the canvas):",
    "启用此节点": "Enable this node",
    "导入模型": "Import model",
    "导出模型": "Export model",
    "已切换 {0} 个节点的启用状态": "Toggled the enabled state of {0} node(s)",
    "已复制 {0} 个节点": "Copied {0} node(s)",
    "已导入模型": "Model imported",
    "已导出模型": "Model exported",
    "已按依赖关系整理": "Rearranged by dependency",
    "已撤销": "Undone",
    "已禁用": "Disabled",
    "已粘贴 {0} 个节点": "Pasted {0} node(s)",
    "已跳过（节点被禁用）": "Skipped (node disabled)",
    "已重做": "Redone",
    "把当前这张模型存成 .ggismodel 文件": "Save the current model as a .ggismodel file",
    "按依赖关系重新排布（数据在左、结果在右）": "Rearrange by dependency (data on the left, results on the right)",
    "撤销上一步改动（Ctrl+Z）": "Undo the last change (Ctrl+Z)",
    "放大节点图": "Zoom in the node graph",
    "整理排列": "Tidy up",
    "模型文件 (*.ggismodel);;JSON 文件 (*.json)": "Model files (*.ggismodel);;JSON files (*.json)",
    "模型文件 (*.ggismodel);;JSON 文件 (*.json);;所有文件 (*)": "Model files (*.ggismodel);;JSON files (*.json);;All files (*)",
    "没有可撤销的操作": "Nothing to undo",
    "没有可重做的操作": "Nothing to redo",
    "注释 · 双击画布上的便签改内容": "Note · double-click the sticky note on the canvas to edit it",
    "添加注释": "Add note",
    "禁用此节点": "Disable this node",
    "编辑注释…": "Edit note…",
    "缩小节点图": "Zoom out the node graph",
    "运行中": "Running",
    "运行结束": "Run finished",
    "重做刚撤销的那一步（Ctrl+Shift+Z）": "Redo the last undone change (Ctrl+Shift+Z)",
    "（还是空的，双击画布上的便签即可编辑）": "(Still empty — double-click the sticky note on the canvas to edit)",
    "列统计 — {0}": "Column Statistics — {0}",
    "管理列": "Organize Columns",
    "管理列…": "Organize Columns…",
    "条件格式": "Conditional Formatting",
    "字段管理": "Field Manager",
    "字段计算器": "Field Calculator",
    "字段计算器 — {0}": "Field Calculator \u2014 {0}",
    "可用函数": "Available Functions",
    "输出到新字段": "Output to a new field",
    "更新已有字段": "Update an existing field",
    "仅更新选中的要素": "Only update selected features",
    "删除所选": "Delete Selected",
    "重命名所选": "Rename Selected",
    "添加规则": "Add Rule",
    "高亮色": "Highlight Color",
    "选择高亮色": "Choose Highlight Color",
    "请填写字段名称": "Please enter a field name",
    "新增字段失败：{0}": "Failed to add field: {0}",
    "删除字段失败：{0}": "Failed to delete field: {0}",
    "重命名字段失败：{0}": "Failed to rename field: {0}",
    "本图层当前不可编辑，无法执行该操作": "This layer is not editable right now \u2014 the operation cannot be performed",
    "请选择一个字段": "Please select a field",
    "新名称：": "New name:",
    "字段管理 — {0}": "Field Manager \u2014 {0}",
    "空值数": "Null count",
    "空值数（前 {0} 行）": "Null count (first {0} rows)",
    "新建字段": "New field",
    "重命名字段": "Rename field",
    "请输入表达式": "Please enter an expression",
    "表达式无法编译": "The expression could not be compiled",
    "没有可更新的字段": "No field available to update",
    "没有可更新的要素": "No features to update",
    "写入失败：{0}": "Write failed: {0}",
    "应用列设置失败：{0}": "Failed to apply column settings: {0}",
    "应用条件格式失败：{0}": "Failed to apply conditional formatting: {0}",
    "请输入条件表达式": "Please enter a condition expression",
    "上移": "Move Up",
    "下移": "Move Down",
    "全部显示": "Show All",
    "全部隐藏": "Hide All",
    "冻结": "Freeze",
    "冻结到左侧": "Freeze to Left",
    "取消冻结": "Unfreeze",
    "升序排列": "Sort Ascending",
    "降序排列": "Sort Descending",
    "清除排序": "Clear Sort",
    "隐藏此列": "Hide This Column",
    "显示所有列": "Show All Columns",
    "列统计": "Column Statistics",
    "自动列宽": "Auto Column Width",
    "新字段名": "New field name",
    "有未保存的编辑": "has unsaved edits",
    "有尚未确认的折点改动": "has unconfirmed vertex changes",
    "剪切图层": "Cut layer",
    "已取消剪切": "Cut cancelled",

    "图层「{0}」{1}。\n{2}之后这些改动会丢失，且无法撤销。\n确定要{2}吗？":
        "Layer “{0}” {1}.\n{2}之后这些改动会丢失，且无法撤销。\n确定要{2}吗？",

    "按当前比例尺的 1.2 屏幕像素抽稀矢量几何（QGIS 口径）。底图与选中高亮使用同一份简化结果，所以两者的轮廓始终重合。":
        "Simplify vector geometry to 1.2 screen pixels at the current scale (the QGIS rule). The basemap and the selection highlight share the same simplified geometry, so their outlines always match exactly.",

    "简化容差": "Simplify tolerance",
    "抽稀容差，以屏幕像素计：1 像素最精细也最慢，数值越大越快，但小于容差的细小多边形可能被整个吃掉。QGIS 的默认值是 1.2 像素。":
        "Simplification tolerance in screen pixels: 1 px is the finest (and slowest); larger values are faster but may swallow tiny polygons smaller than the tolerance. The QGIS default is 1.2 px.",
    "按当前比例尺抽稀矢量几何。底图与选中高亮使用同一份简化结果，所以两者的轮廓始终重合。":
        "Simplify vector geometry at the current scale. The basemap and the selection highlight share the same simplified geometry, so their outlines always match exactly.",

    "矢量抗锯齿": "Vector anti-aliasing",
    "3×": "3x",
    "矢量线与面的抗锯齿超采样倍率。倍率越高边缘越细腻，但渲染开销按倍率的平方增长。":
        "Supersampling factor for vector line and polygon anti-aliasing. Higher values give smoother edges, but rendering cost grows with the square of the factor.",
    "选中要素轮廓的描边宽度（屏幕像素）。0 表示跟随图层符号自身的线宽。":
        "Outline width of the selection highlight (screen pixels). 0 means follow the layer symbol's own line width.",
    "在线瓦片与显示金字塔的存放位置（可再生，可随手删）。留空则放在用户目录下、与日志文件同级。也可填绝对路径，如 D:/GmaGIS-cache":
        "Where online tiles and display pyramids are stored (regenerable, safe to delete). Leave empty to use the user directory, next to the log file. You can also enter an absolute path such as D:/GmaGIS-cache",
    "尺寸单位": "Size unit",
    "新建符号的尺寸与线宽用哪个单位保存。已有符号仍按各自保存的单位显示。":
        "The unit used to store sizes and line widths of new symbols. Existing symbols keep the unit they were saved with.",

    "简化复杂几何": "Simplify complex geometry",
    "1×": "1x",
    "2×": "2x",
    "4×": "4x",
    "按当前比例尺抽稀矢量几何，可提速，但可能吃掉细小的多边形。底图与选中高亮使用同一份简化结果，所以两者的轮廓始终重合。":
        "Simplify vector geometry at the current scale; faster, but tiny polygons may be swallowed. The basemap and the selection highlight share the same simplified geometry, so their outlines always match exactly.",
    "矢量线与面的抗锯齿超采样倍率。倍率越高边缘越细腻，但渲染开销按倍率的平方增长。1× 为关闭，2× 为推荐值，4× 最平滑也最慢。":
        "Supersampling factor for vector line and polygon anti-aliasing. Higher values give smoother edges, but rendering cost grows with the square of the factor. 1x is off, 2x is the recommended value, 4x is the smoothest and the slowest.",
    "选中要素轮廓的描边宽度，单位为屏幕像素。填0 表示跟随图层符号自身的线宽。":
        "Outline width of the selection highlight, in screen pixels. Enter 0 to follow the layer symbol's own line width.",
    "选中要素的线条宽度，单位为屏幕像素。填0 表示跟随图层符号自身的线宽。":
        "Line width of the selection highlight, in screen pixels. Enter 0 to follow the layer symbol's own line width.",
    "在线瓦片与显示金字塔的存放位置，可再生，可随手删。留空则使用用户目录下与日志文件同级的默认位置。也可填绝对路径，如 D:/GmaGIS-cache":
        "Where online tiles and display pyramids are stored; regenerable and safe to delete. Leave empty to use the default location in the user directory, next to the log file. You can also enter an absolute path such as D:/GmaGIS-cache",
    "图层与数据": "Layers and data",
    "结果与信息": "Results and messages",
    "新开一张独立的地图视图（各自的选择集、渲染进程与视野）": "Open a separate map view (its own selection, render process and extent)",
    "新建一张布局：先确认大小、单位、方向与标签名，再在主窗口内打开": "New layout: confirm its size, unit, orientation and tab name first, then open it in the main window",

    "图标": "Icon",
    "图标 + 文本": "Icon and text",
    "可切换": "Toggle",
    "位置：{0}, {1}": "Location: {0}, {1}",
    "（尚未点击地图）": "(not clicked on the map yet)",


    "＋ 新建字段…": "＋ New field…",
    "代码块（可选）": "Code Block (optional)",
    "用 def 定义函数，表达式里即可调用，例如：\ndef 翻倍(x):\n    return x * 2\n之后表达式写：翻倍(面积)":
        "Define functions with def and call them in the expression, e.g.:\ndef double(x):\n    return x * 2\nThen write in the expression: double(area)",
    "例如：面积 * 2、round(单价, 2)、upper(名称)":
        "e.g. area * 2, round(price, 2), upper(name)",
    "输入表达式后，这里显示前 5 条预览":
        "After you enter an expression, a preview of the first 5 features appears here",
    "预览（前 {0} 条）：": "Preview (first {0} features):",
    "fid {0} 出错：{1}": "fid {0} error: {1}",
    "将更新全部 {0} 个要素": "Will update all {0} features",
    "将更新选中的 {0} 个要素": "Will update the {0} selected features",
    "请填写新字段名": "Please enter a new field name",
    "第 {0} 个要素计算失败：{1}（已中止，未写入任何数据）":
        "Feature {0} failed to calculate: {1} (aborted — no data was written)",
    "字段计算器表达式 (*.cal)": "Field Calculator expression (*.cal)",
    "导入 .cal 表达式文件": "Import .cal expression file",
    "导入字段计算器表达式": "Import Field Calculator expression",
    "导出为 .cal 表达式文件": "Export as .cal expression file",
    "导出字段计算器表达式": "Export Field Calculator expression",
    "已导出：{0}": "Exported: {0}",

    "表达式不能为空": "The expression cannot be empty",
    "表达式尚未编译": "The expression has not been compiled yet",
    "代码块里没有可调用的函数（请用 def 定义一个）":
        "The code block has no callable function (define one with def)",
    "当前没有要素属性，[%s] 无处可取":
        "No feature attributes are available, so [%s] cannot be read",
    "字段「%s」不存在": "Field “%s” does not exist",
    "不是有效的 .cal 文件（文件头应为 %s）":
        "Not a valid .cal file (the header should be %s)",
    "无法识别的小节「%s」": "Unrecognized section “%s”",
    "缺少「表达式」小节": "Missing the “Expression” section",

    "数学": "Math",
    "转换": "Conversion",
    "log(x) 或 log(底, x)": "log(x) or log(base, x)",
    "round(x[, 小数位])": "round(x[, decimals])",
    "replace(s, 旧, 新)": "replace(s, old, new)",
    "substr(s, 起始[, 长度])": "substr(s, start[, length])",

    "绝对值": "Absolute value",
    "平方根（负数→空）": "Square root (negative → empty)",
    "自然指数": "Natural exponential",
    "自然对数": "Natural logarithm",
    "对数": "Logarithm",
    "常用对数": "Common logarithm (base 10)",
    "四舍五入": "Round",
    "向下取整": "Round down",
    "向上取整": "Round up",
    "正弦": "Sine",
    "余弦": "Cosine",
    "正切": "Tangent",
    "反正弦": "Arcsine",
    "反余弦": "Arccosine",
    "反正切": "Arctangent",
    "四象限反正切": "Four-quadrant arctangent",
    "幂（同 x ^ y）": "Power (same as x ^ y)",
    "常数 π": "Constant π",
    "字符串长度": "String length",
    "转小写": "Convert to lowercase",
    "转大写": "Convert to uppercase",
    "首字母大写": "Convert to title case",
    "去首尾空白": "Trim leading and trailing whitespace",
    "去左空白": "Trim leading whitespace",
    "去右空白": "Trim trailing whitespace",
    "替换": "Replace",
    "子串（起始 1-based，可为负）":
        "Substring (start is 1-based and may be negative)",
    "取首个非空": "First non-empty value",
    "拼接（空值跳过）": "Concatenate (skips empty values)",
    "转整数（截断）": "Convert to integer (truncated)",
    "转实数": "Convert to a real number",
    "转文本": "Convert to text",

    "数值缩放": "Scale value",
    "保留两位": "Round to 2 decimals",
    "文本大写": "Uppercase",
    "拼接后缀": "Append suffix",
    "整数": "Integer",
    "实数": "Real",
    "浮点": "Float",
    "日期": "Date",
    "二进制": "Binary",

    "字段名称": "Field name",
    "字段名称（现有或新建）": "Field name (existing or new)",
    "助手": "Functions",
    "坡度": "Slope",
    "坡向": "Aspect",
    "山体阴影": "Hillshade",
    "等高线": "Contour",
    "按范围裁剪": "Clip by extent",
    "按掩模裁剪": "Clip by mask",
    "波段提取": "Extract band",
    "栅格计算器": "Raster calculator",
    "重分类": "Reclassify",
    "归一化": "Normalize",
    "栅格转面": "Raster to polygons",
    "根据 DEM 计算每个像元的最大高程变化率（度）。计算用 Horn 有限差分。":
        "Compute the maximum elevation change rate (degrees) per cell from a DEM. Uses the Horn finite difference.",
    "每个像元的坡面朝向（度，0=正北、90=正东）。平坦像元记为 -1。":
        "Aspect (facing direction) per cell in degrees (0=N, 90=E). Flat cells are marked -1.",
    "用太阳高度角 / 方位角给地形打光，得到明暗浮雕（0-255）。":
        "Shade terrain by sun altitude/azimuth to produce a relief image (0-255).",
    "按等高距提取等高程线（矢量）。无 scipy，采用按高程阈值 polygonize 取环成线的方式逼近。":
        "Extract contour lines (vector) by interval. No scipy: approximate by polygonizing per elevation threshold and taking rings.",
    "按一个矩形范围把栅格裁出来（范围不填则用输入图层自身范围）。":
        "Clip a raster by a rectangle extent (uses the input layer's own extent if not given).",
    "用一个矢量多边形把栅格裁出来，范围外记为 nodata。":
        "Clip a raster by a vector polygon mask; outside becomes nodata.",
    "把栅格重采样到新的像元大小（米）。连续数据默认双线性，分类数据用最近邻。":
        "Resample a raster to a new cell size (meters). Bilinear for continuous data, nearest for categorical by default.",
    "把多波段栅格里的某一个波段单独提取成一张单波段栅格。":
        "Extract a single band from a multi-band raster into a single-band raster.",
    "对波段做数学运算。变量为 b1/b2/…（按波段号），如 b1 + b2、((b1 - b2) / (b1 + b2 + 1e-9)) * 100。仅允许数学函数。":
        "Math on bands. Variables are b1/b2/... (by band index), e.g. b1 + b2 or ((b1 - b2) / (b1 + b2 + 1e-9)) * 100. Only math functions allowed.",
    "把数值归并到若干区间。手动模式填 lo:hi:val;lo:hi:val（左闭右开）；等分模式按最小值到最大值切成 N 类。":
        "Merge values into classes. Manual: lo:hi:val;lo:hi:val (left-closed, right-open); Equal: split min-max into N classes.",
    "把数值线性归一化到 0-1（按有效像元的最小/最大值）。":
        "Linearly normalize values to 0-1 (by min/max of valid cells).",
    "把相同值的连通区合并成面（矢量），属性带原始栅格值。适合分类 / 整型栅格。":
        "Merge connected regions of equal value into polygons (vector); attribute carries the original raster value. Good for classified/integer rasters.",
    "太阳高度角（度）": "Sun altitude (degrees)",
    "太阳方位角（度）": "Sun azimuth (degrees)",
    "垂直夸张": "Vertical exaggeration",
    "等高距": "Contour interval",
    "起始高程": "Base elevation",
    "最小 X": "Min X",
    "最小 Y": "Min Y",
    "最大 X": "Max X",
    "最大 Y": "Max Y",
    "裁剪范围": "Clip extent",
    "X 像元大小（米）": "X cell size (m)",
    "Y 像元大小（米）": "Y cell size (m)",
    "重采样方法": "Resampling method",
    "波段号（从 1 起）": "Band number (from 1)",
    "区间（手动，lo:hi:val;…）": "Ranges (manual, lo:hi:val;...)",
    "类数（等分）": "Number of classes (equal)",
    "百分位数截断": "Percentile clip",
    "1（不变）": "1 (no change)",
    "输入图层自身范围": "Input layer's extent",
    "自定义矩形": "Custom rectangle",
    "双线性（连续）": "Bilinear (continuous)",
    "最近邻（分类）": "Nearest (categorical)",
    "三次卷积": "Cubic convolution",
    "均值（降采样）": "Average (downsampling)",
    "手动区间": "Manual ranges",
    "等分区间": "Equal intervals",
    "不截断（min-max）": "No clip (min-max)",
    "2%/98% 截断": "2%/98% clip",
    "栅格分析": "Raster analysis",
    "输入栅格": "Input raster",
    "裁剪掩模（矢量）": "Clip mask (vector)",
    "请先选择输入栅格图层": "Please select an input raster layer first",
    "请先选择裁剪掩模（矢量图层）": "Please select a clip mask (vector layer) first",
    "请先填写输出文件": "Please specify an output file first",
    "读不出这个栅格文件：{0}": "Cannot read this raster file: {0}",
    "选择栅格文件": "Select raster file",
    "栅格分析失败：{0}": "Raster analysis failed: {0}",
    "栅格分析已取消": "Raster analysis cancelled",
    "栅格分析没有产生任何结果": "Raster analysis produced no result",
    "栅格结果路径缺失": "Raster result path missing",
    "读回栅格结果失败：{0}": "Failed to read back raster result: {0}",
    "栅格结果图层无效": "Raster result layer is invalid",
    "矢量结果图层无效": "Vector result layer is invalid",
    "栅格结果": "Raster result",
    "栅格": "Raster",
    "「{0}」完成（{1}）": "{0} done ({1})",
    "「{0}」完成：{1} 个要素": "{0} done: {1} features",
    "提取范围": "Extract",
    "合并要素": "Merge Features",
    "几何修正": "Geometry Repair",
    "邻近分析": "Proximity Analysis",
    "地形分析": "Terrain Analysis",
    "栅格处理": "Raster Processing",
    "栅格代数": "Raster Algebra",
    "不透明度": "Opacity",
    "专用控件": "Dedicated Controls",
    "修改数据源": "Change Data Source",
    "修改数据源（服务地址）": "Change Data Source (Service URL)",
    "修改数据源：选好新文件后**立即**重新读取": "Change Data Source: re-read immediately after selecting the new file",
    "值示例": "Value Example",
    "内存图层没有可修改的数据源；请先导出为文件。": "In-memory layers have no editable data source; export to a file first.",
    "单位与地图坐标系（显示 / 坐标相关设置）": "Units and map coordinate system (display / coordinate settings)",
    "单位（显示 / 坐标相关设置）": "Units (display / coordinate settings)",
    "可切换（选中保留边框）": "Toggleable (border kept when selected)",
    "大地基准参数": "Geodetic Datum Parameters",
    "日志写入的文件路径；留空使用默认位置（%APPDATA%/GmaGIS/logs）。": "Log file path; leave blank for the default location (%APPDATA%/GmaGIS/logs).",
    "服务地址（瓦片 URL 模板，需含 {z}/{x}/{y}）：": "Service URL (tile URL template, must include {z}/{x}/{y}):",
    "标准按钮": "Standard Buttons",
    "消息与对话框": "Messages and Dialogs",
    "渲染方法更改需要重启程序才完全生效。": "Render method changes require a restart to take full effect.",
    "示例分组": "Example Group",
    "输入图层（勾选多个）": "Input Layer (check multiple)",
    "输入输出": "Input/Output",
    "键": "Key",
    "默认尺寸单位": "Default Size Unit",
    '对波段做数学运算。变量为 b1/b2/…（按波段号），如 "b1 + b2"、"((b1 - b2) / (b1 + b2 + 1e-9)) * 100"。仅允许数学函数。': 'Perform math on bands. Variables are b1/b2/… (by band number), e.g. "b1 + b2", "((b1 - b2) / (b1 + b2 + 1e-9)) * 100". Only mathematical functions are allowed.',
    "从路径…": "From Path…",
    "切换标注": "Toggle Labels",
    "地理包": "GeoPackage",
    "定位到当前位置": "Locate Current Position",
    "缩放至可见图层范围": "Zoom to Visible Layer Extent",
    "缩放到当前地图视图中所有可见图层的合并范围；没有可见图层时不可用": "Zoom to the combined extent of all visible layers in the current map view; unavailable when no layer is visible",
    "导出地图图片…": "Export Map Image…",
    "数据库 / Web 服务…": "Database / Web Service…",
    "新建文件": "New File",
    "栅格符号系统…": "Raster Symbology…",
    "样式管理器…": "Style Manager…",
    "添加图形图层…": "Add Graphic Layer…",
    "添加文本数据 (CSV)…": "Add Text Data (CSV)…",
    "直方图…": "Histogram…",
    "选择折点": "Select Vertex",
    "选项…": "Options…",
    "从文件添加数据（自动识别矢量 / 栅格 / 文本）": "Add data from file (auto-detect vector / raster / text)",
    "修整：画一条线切一刀，只保留含原中心的那一块": "Trim: draw a line to cut; keep only the piece containing the original center",
    "关闭当前工程并新建空工程 (Ctrl+Shift+N)": "Close the current project and create a new empty one (Ctrl+Shift+N)",
    "分割：画一条分割线，被穿过的要素被切开（所有块都保留）": "Split: draw a split line; crossed features are cut (all pieces kept)",
    "创建：按活动图层的几何类型在地图上数字化新要素 (Ctrl+.)": "Create: digitize a new feature on the map by the active layer's geometry type (Ctrl+.)",
    "删除折点：单击折点即删除": "Delete Vertex: click a vertex to remove it",
    "删除选中的要素（需先选中要素，与「选择要素」配合使用）": "Delete selected features (select features first; used with \"Select Features\")",
    "剪切活动图层：从图层树移除，粘贴时恢复 (Ctrl+X)": "Cut the active layer: remove from the layer tree; restore on paste (Ctrl+X)",
    "取消活动图层的全部选择 (Ctrl+Shift+D)": "Clear all selections on the active layer (Ctrl+Shift+D)",
    "合并：所选要素合为一个多部件要素": "Merge: combine selected features into one multipart feature",
    "复制活动图层数据源路径到系统剪贴板": "Copy the active layer's data source path to the system clipboard",
    "复制活动图层（可重复粘贴）(Ctrl+C)": "Copy the active layer (can be pasted repeatedly) (Ctrl+C)",
    "完成编辑：提交当前折点编辑（等价于在地图上双击）": "Finish Editing: commit the current vertex edits (equivalent to double-clicking on the map)",
    "对齐：画一条参考线，所选要素整体平移到其中心的投影点": "Align: draw a reference line; selected features shift as a whole to the projection of their center",
    "开 / 关活动图层的标注显示": "Turn the active layer's label display on / off",
    "打开 / 收起「坐标转换」面板：在源 / 目标坐标系之间换算坐标": "Open / collapse the \"Coordinate Conversion\" panel: convert coordinates between source and target CRS",
    "打开基础工具箱（空间分析算法）(Ctrl+Alt+T)": "Open the basic toolbox (spatial analysis algorithms) (Ctrl+Alt+T)",
    "打开工程文件 (Ctrl+O)": "Open a project file (Ctrl+O)",
    "打开活动图层的属性窗口": "Open the active layer's properties window",
    "打开符号系统面板（栅格页）：色带、波段、对比度拉伸与透明度": "Open the symbology panel (raster page): color ramp, bands, contrast stretch and transparency",
    "打断：画一条线，线图层中与线相交的要素在交点处断开": "Break: draw a line; line features intersecting it are split at the intersection",
    "把剪贴板里的图层添加到图层树 (Ctrl+V)": "Add the layer from the clipboard to the layer tree (Ctrl+V)",
    "把当前地图画布保存为 PNG 图片": "Save the current map canvas as a PNG image",
    "把当前选择换成未选中的那些要素 (Ctrl+Shift+U)": "Invert the current selection to the unselected features (Ctrl+Shift+U)",
    "把活动栅格图层另存为 GeoTIFF 等格式": "Save the active raster layer as GeoTIFF or another format",
    "拆分多部件要素：选中要素的每个部件拆成独立要素": "Explode multipart features: split each part of the selected feature into an independent feature",
    "新建一张模型：弹名称框确认后，在主窗口内打开一个独立的模型构建器视图（可与已有模型共存、同时打开多张）": "Create a new model: after a name dialog confirms, open an independent model builder view in the main window (multiple models can coexist and be open at once)",
    "查看栅格像元值分布并调整对比度拉伸": "View the raster cell-value distribution and adjust the contrast stretch",
    "查看选中要素的属性（弹出窗口，可复制）": "View the selected feature's attributes (popup window, copyable)",
    "根据当前网络 IP 获取所在地理位置，并把地图平移到该处": "Get the current location from the network IP and pan the map there",
    "概化：按容差简化所选要素几何（Douglas-Peucker）": "Generalize: simplify selected feature geometry by tolerance (Douglas-Peucker)",
    "测量两条线之间的角度": "Measure the angle between two lines",
    "点击放大一档 (Alt+2)": "Zoom in one step (Alt+2)",
    "版本、运行环境与项目说明": "Version, runtime environment and project notes",
    "用对话框导出活动矢量图层（可选格式/CRS/字段）": "Export the active vector layer via a dialog (optional format / CRS / fields)",
    "用表达式筛选活动图层的要素 (Ctrl+F3)": "Filter the active layer's features by expression (Ctrl+F3)",
    "点击地图上任意位置即可画出该点的剖面曲线；再点其他位置就换一张图": "Click any location on the map to draw that point's profile curve; click another to switch",
    "矩形框选要素": "Select features by rectangle",
    "移动：按住选中的要素拖动 (Ctrl+Alt+M)": "Move: drag the selected feature while holding (Ctrl+Alt+M)",
    "绘制活动图层选中字段的分布": "Plot the distribution of the active layer's selected field",
    "编辑折点：拖动折点移动、双击线段加点、Delete 删除所选折点": "Edit Vertices: drag a vertex to move, double-click a segment to add, Delete to remove selected vertices",
    "缩放到活动图层范围 (Ctrl+Shift+L)": "Zoom to the active layer's extent (Ctrl+Shift+L)",
    "缩放到矢量图层中选中的要素 (Ctrl+J)": "Zoom to the selected features in the vector layer (Ctrl+J)",
    "融合：选中要素的几何合并为一个，属性保留最大要素": "Dissolve: merge selected feature geometries into one, keeping the largest feature's attributes",
    "设置图层的符号系统（矢量：颜色/符号/渲染方式；栅格：波段/色带/拉伸/重采样）": "Set the layer's symbology (vector: color/symbol/renderer; raster: bands/ramp/stretch/resampling)",
    "输入 XY 坐标，视图平移到该点（支持工程坐标或经纬度）": "Enter XY coordinates to pan the view to that point (project coordinates or lat/long supported)",
    "工程设置（名称 / 单位）与应用程序选项（主题 / 语言等）": "Project settings (name / units) and application options (theme / language, etc.)",
    "选择折点：单击折点选中（Ctrl 加选 / 减选）": "Select Vertex: click a vertex to select it (Ctrl to add / subtract)",
    'GmaGIS许可声明': 'GmaGIS License Notice',
    'RGB: {0}, {1}, {2}': 'RGB: {0}, {1}, {2}',
    'WKT 文件 (*.wkt *.prj *.txt)': 'WKT Files (*.wkt *.prj *.txt)',
    'X,Y；多个点用分号隔开': 'X,Y; separate multiple points with semicolons',
    'X（经度 / 东向）': 'X (longitude / easting)',
    'Y（纬度 / 北向）': 'Y (latitude / northing)',
    '{0}（{1} 项）': '{0} ({1} items)',
    '{0}（列 {1}, 行 {2}）': '{0} (col {1}, row {2})',
    '像素（列, 行） = {0}, {1}': 'Pixel (col, row) = {0}, {1}',
    '全部 {0}\u3000|\u3000选中 {1}': 'All {0}\u3000|\u3000Selected {1}',
    '全部图层': 'All Layers',
    '全部要素：显示该图层所有要素': 'All features: show all features of this layer',
    '内存图层': 'In-Memory Layer',
    '分组属性对话框加载失败：{}': 'Failed to load the group properties dialog: {}',
    '创建选项…': 'Create Options…',
    '删除该字段': 'Delete This Field',
    '勾选「显示」控制列可见；勾选「冻结」把列钉在左侧。用上下按钮调整顺序。': 'Check "Show" to toggle column visibility; check "Freeze" to pin the column to the left. Use the up/down buttons to reorder.',
    '匹配 {0} / {1}（点「应用」或「确定」后生效）': 'Matched {0} / {1} (takes effect after "Apply" or "OK")',
    '取消选中此要素': 'Deselect this feature',
    '可见图层': 'Visible Layers',
    '在地图上显示测量结果': 'Show measurement results on the map',
    '在线瓦片「{0}」在当前坐标系 {1} 下无法显示（投影失败），已保留图层。': 'Online tile layer "{0}" cannot be displayed in the current CRS {1} (reprojection failed); the layer has been kept.',
    '地图工具「{}」不可用：工具对象未建出来（详见日志）': 'Map tool "{}" is unavailable: the tool object was not created (see the log)',
    '坐标参照：': 'Coordinate reference:',
    '坐标格式无法识别：{0}, {1}': 'Unrecognized coordinate format: {0}, {1}',
    '坐标系定义': 'Coordinate System Definition',
    '处理中': 'Processing',
    '复制单元格': 'Copy Cell',
    '复制整行': 'Copy Row',
    '如 4,2,1,2 —— 画线长、空白长…循环（线宽倍数）': 'e.g. 4,2,1,2 — dash, gap… repeating (multiples of line width)',
    '字段管理：新增 / 删除 / 重命名字段': 'Field Manager: add / delete / rename fields',
    '字段计算器：用表达式批量计算字段值': 'Field Calculator: compute field values in batch with expressions',
    '定位': 'Locate',
    '导出坐标系到文件': 'Export Coordinate System to File',
    '导出已取消': 'Export cancelled',
    '导出要素': 'Export Features',
    '将导出选中的 {0} 个要素': '{0} selected features will be exported',
    '展开': 'Expand',
    '属性表面板初始化失败': 'Failed to initialize the attribute table panel',
    '已定位到当前位置（{0}, {1}）': 'Located at the current position ({0}, {1})',
    '已应用：保留 {0} / {1}（取消可还原）': 'Applied: keeping {0} / {1} (Cancel to revert)',
    '已选中：{0} / {1}（取消可还原）': 'Selected: {0} / {1} (Cancel to revert)',
    '已新建内存图层：{0}（{1}）': 'Created in-memory layer: {0} ({1})',
    '已生成图层「{0}」': 'Generated layer "{0}"',
    '已生成图层「{0}」（{1} 个要素）': 'Generated layer "{0}" ({1} features)',
    '当前位置坐标转换失败': 'Failed to transform coordinates of the current position',
    '总和': 'Sum',
    '所选要素：仅显示被选中的要素': 'Selected features: show only the selected features',
    '打开列管理失败：{0}': 'Failed to open the column manager: {0}',
    '打开字段管理失败：{0}': 'Failed to open the field manager: {0}',
    '打开字段计算器失败：{0}': 'Failed to open the field calculator: {0}',
    '执行失败': 'Execution Failed',
    '折叠': 'Collapse',
    '掩膜背景': 'Mask Background',
    '搜索候选值…（先点「获取唯一值」）': 'Search candidate values… (click "Get Unique Values" first)',
    '文件路径：{0}': 'File path: {0}',
    '文件路径：尚未保存': 'File path: not saved yet',
    '无法启动任务': 'Failed to Start Task',
    '显示缩放': 'Display Scaling',
    '最短文本': 'Shortest text',
    '最近': 'Recent',
    '最长文本': 'Longest text',
    '未找到 license.txt。': 'license.txt not found.',
    '本次导出有 {0} 张瓦片下载失败（缺图处留空或填黑块）。请检查网络后重试，或缩小范围 / 降低层级再下载。': '{0} tiles failed to download in this export (missing areas are left blank or filled black). Check the network and retry, or reduce the extent / level and download again.',
    '本软件许可全文': 'Full license of this software',
    '标注面板初始化失败': 'Failed to initialize the labeling panel',
    '样式面板初始化失败': 'Failed to initialize the symbology panel',
    '正在获取当前位置…': 'Getting the current position…',
    '波段 {0}: {1}': 'Band {0}: {1}',
    '添加字段': 'Add Field',
    '清空所有点': 'Clear All Points',
    '渲染中': 'Rendering',
    '演示结果（置信度存疑）': 'Demo result (low confidence)',
    '点「运行」后观察任务面板：条目进度、终止按钮、双击条目回显本窗口、完成/失败/取消三态与结果行。': 'Click "Run" and watch the task panel: item progress, the stop button, double-click an item to bring back this window, the done/failed/cancelled states and the result row.',
    '点击：设置底图坐标系': 'Click: set the basemap CRS',
    '瓦片下载不完整': 'Tile Download Incomplete',
    '瓦片层级 z={0}（{1}, {2}）': 'Tile level z={0} ({1}, {2})',
    '确定要清空列表中的所有坐标点吗？此操作不可撤销。': 'Clear all coordinate points in the list? This cannot be undone.',
    '确定要移除全部 {0} 个图层吗？\n{1}': 'Remove all {0} layers?\n{1}',
    '移除全部图层': 'Remove All Layers',
    '窗口': 'Windows',
    '第三方组件许可全文': 'Full licenses of third-party components',
    '经纬度转换失败': 'Lat/long transformation failed',
    '经纬度（WGS84）': 'Lat/Long (WGS84)',
    '缩放到要素': 'Zoom to Feature',
    '缩放到选中要素': 'Zoom to Selected Features',
    '缩放至选中要素': 'Zoom to Selected Features',
    '缺少必填参数': 'Missing Required Parameters',
    '获取唯一值': 'Get Unique Values',
    '获取当前位置失败：{0}': 'Failed to get the current position: {0}',
    '表达式为空白，点「应用 / 确定」将清除现有过滤': 'The expression is empty; clicking "Apply / OK" will clear the existing filter',
    '表达式已清空，点「应用 / 确定」将清除现有过滤': 'The expression has been cleared; clicking "Apply / OK" will clear the existing filter',
    '要素: {0}': 'Feature: {0}',
    '许可声明': 'License Notice',
    '识别时查哪些图层：可见图层 / 全部图层（含隐藏）/ 顶部图层（图层树最上方一个）': 'Which layers to query when identifying: visible layers / all layers (including hidden) / top layer (the topmost one in the layer tree)',
    '识别范围': 'Identify Scope',
    '识别：点击地图查看每个图层在该位置的值': "Identify: click the map to view each layer's values at that location",
    '请先设置视图坐标系，再使用测量工具': 'Set the view CRS before using the measure tools',
    '读完整个图层取该字段的唯一值（大图层会慢一点）': 'Reads the entire layer to collect unique values of the field (slower on large layers)',
    '输入目标坐标，把视图平移到该点（保持当前比例尺）。': 'Enter target coordinates to pan the view to that point (the current scale is kept).',
    "输入过滤条件，例如：  POP >= 500  AND  NAME LIKE '南%'\n（字段/值可双击插入；留空点「确定」即清除现有过滤）": 'Enter a filter expression, e.g.:  POP >= 500  AND  NAME LIKE \'South%\'\n(Double-click fields/values to insert; leave empty and click "OK" to clear the existing filter)',
    '选中此要素': 'Select this feature',
    '选中要素': 'Selected Features',
    '选中要素没有可缩放的几何': 'The selected features have no zoomable geometry',
    '顶部图层': 'Top Layer',
    '项目': 'Item',
    '默认无字段，点击下方「添加字段」增加': 'No fields by default; click "Add Field" below to add some',
    '（无内容）': '(no content)',
    '（瓦片未缓存）': '(tile not cached)',
    '文件关联': 'File association',
    '重置文件关联': 'Reset file association',
    '按当前程序位置重建 .ggs 工程文件关联（写入用户级注册表，'
    '无需管理员权限，立即生效）。双击 .ggs 打不开或图标显示'
    '不对时用它修复。':
        'Rebuild the .ggs file association from the current program '
        'location (writes a per-user registry entry; no administrator '
        'rights required; takes effect immediately). Use this if '
        'double-clicking a .ggs file does not open it, or its icon '
        'looks wrong.',
    '文件关联仅支持 Windows 系统。': 'File association is only supported on Windows.',
    '已关联 .ggs 工程文件': 'Associated .ggs project files.',
    '新建工程（选择位置与名称）':
        'New Project (choose location and name)',

    '已取消 .ggs 文件关联': 'Removed .ggs file association.',
    '文件关联失败：{}': 'File association failed: {}',
    "光谱工具": "Spectral Tools",
    "光谱曲线": "Spectral Profile",
    "X（画布坐标）": "X (canvas coordinates)",
    "Y（画布坐标）": "Y (canvas coordinates)",
    "横轴：波段序号（共 {0} 个图层）": "X axis: band index ({0} layers in total)",
    "（该取样点无数据）": "(no data at this sample point)",
    "（还没有图层，点「添加图层」）": '(no layers yet; click "Add Layers")',
    "正在初始化窗口…": "Initializing the window…",
    "正在注册服务与区域…": "Registering services and regions…",
    "正在构建状态栏…": "Building the status bar…",
    "正在初始化拖放过滤…": "Preparing drop filters…",
    "正在准备视图区域…": "Preparing the view area…",
    "正在布置视图边框…": "Arranging view docks…",
    "正在创建地图画布…": "Creating the map canvas…",
    "正在初始化视图服务…": "Initializing view services…",
    "正在连接信号与收尾…": "Connecting signals and wrapping up…",
    "正在恢复窗口布局…": "Restoring window layout…",
    "正在完成启动…": "Finishing startup…",
    "圆形": "Circle",
    "浏览 / 平移地图": "Browse / pan the map",
    "查询要素属性": "Query feature attributes",
    "多边形框选要素": "Select features by polygon",
    "套索圈选要素": "Select features by lasso",
    "圆形框选要素": "Select features by circle",
    "折线框选要素": "Select features by polyline",
    "测量多边形面积": "Measure polygon area",
    "XY 表转点…": "XY table to point…",
    "打开剖面曲线面板：选择波段、在地图上取点，画出该点行 / 列方向的像素值曲线": "Open the profile panel: pick a band and a map point to plot pixel values along the row / column",
    "打开光谱曲线面板：在多个栅格图层的同一位置取各波段值，画成多色折线对比": "Open the spectral panel: sample band values at one location across raster layers, drawn as multi-colour lines",
    "批量修改属性": "Batch edit attributes",
    "添加字段 {0}": "Add field {0}",
    "删除字段 {0}": "Delete field {0}",
    "重命名字段 {0} → {1}": "Rename field {0} → {1}",
    "提示": "Notice",
    "以下在线瓦片在当前坐标系 {0} 下无法投影，已停止渲染（图层已保留）：\n{1}": "The following online tiles cannot be reprojected to CRS {0}; rendering stopped (layers kept):\n{1}",
    "按属性选择：用表达式选择要素": "Select by attributes: choose features with an expression",
    "打开按属性选择失败：{0}": "Failed to open Select by Attributes: {0}",
    "沿行": "Along row",
    "沿列": "Along column",
    "（尚未取点）": "(no point picked yet)",
    "正在提取数据…": "Extracting data…",
    "　当前值：{0}": "　Current value: {0}",
    "　当前值：—": "　Current value: —",
    "剖面取数": "Profile sampling",
    "CPU 子进程（回退）": "CPU subprocess (fallback)",
    "CPU 子进程：稳定的默认渲染方式。GPU 瓦片合成：交互平移 / 缩放更跟手，需要本机支持 OpenGL；不可用时会自动回退。更改后需重启程序生效。": "CPU subprocess: the stable default renderer. GPU tile compositing: smoother interactive pan / zoom, requires OpenGL support on this machine; falls back automatically when unavailable. Restart the app after changing.",
    "正在读取数据…": "Reading data…",
    "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;TIFF 图片 (*.tif *.tiff);;SVG 矢量图 (*.svg);;PDF 文档 (*.pdf);;EPS 矢量图 (*.eps);;PostScript (*.ps);;WEBP 图片 (*.webp);;所有文件 (*.*)": "PNG images (*.png);;JPEG images (*.jpg *.jpeg);;TIFF images (*.tif *.tiff);;SVG vector (*.svg);;PDF documents (*.pdf);;EPS vector (*.eps);;PostScript (*.ps);;WEBP images (*.webp);;All files (*.*)",
    "导出画布": "Export canvas",
    "没有可导出的画布": "No canvas to export",
    "选择图层…": "Select layers…",
    "尚未取点": "No point picked yet",
    "请在地图上点击取样点（或等待自动定位到视野中心）": "Click a sample point on the map (or wait for auto-centring on the view)",
    "无法换算坐标：取不到地图视图的坐标系，请激活地图视图并加载图层后重试": "Cannot transform coordinates: the map view has no CRS. Activate a map view with layers loaded and retry",
    "取样点在所有图层的数据范围之外（或读不到像素）——请缩放到图层范围后在地图上重新取点": "The sample point is outside all layer extents (or pixels unreadable) — zoom to the layer extent and pick again on the map",
    "已选 %d 个图层": "%d layer(s) selected",
    "光谱取数": "Spectral sampling",
    "请先加载至少一个栅格图层 —— 然后在上方下拉框中勾选要对比的图层": "Load at least one raster layer first — then tick the layers to compare in the dropdown above",
    "请在上方下拉框中勾选要对比的栅格图层": "Tick the raster layers to compare in the dropdown above",
    "没有可见图层，无法缩放": "No visible layers to zoom to",
    "长度 {}": "Length {}",
    "面积 {}": "Area {}",
    "夹角 {}": "Angle {}",
    "直线距离 {}": "Straight-line distance {}",
    "方位角 {} / {}": "Azimuth {} / {}",
    "量测面积：左键逐点绘制多边形，右键 / 双击结束，Esc 清除":
        "Measure area: click to add vertices; right-click / double-click to finish; Esc clears",
    "量测角度：依次点三个点（顶点在第二个点）":
        "Measure angle: click three points (the second is the vertex)",
    "量测距离：左键逐点，右键 / 双击结束，Backspace 退点，Esc 清除":
        "Measure distance: click to add points; right-click / double-click to finish; Backspace removes the last point; Esc clears",
    "BMP 图片": "BMP image",
    "JPEG 图片": "JPEG image",
    "PNG 图片": "PNG image",
    "WebP 图片": "WebP image",
    "XYZ 文本网格": "XYZ text grid",
    "GeoPackage 栅格": "GeoPackage raster",
    "GDAL VRT（只记引用）": "GDAL VRT (references only)",
    "掩膜": "Mask",
    "参数分组（标准）": "Parameter Group (Standard)",

    "矢量": "Vector",

    "自动保存": "Auto Save",
    " 分钟": " min",
    "保存间隔": "Save Interval",
    "自动保存：开启后按「选项」里设置的间隔定时保存工程":
        "Auto Save: when enabled, saves the project at the interval set in Options",
    "图层显隐": "Toggle Layer Visibility",
    "图层排序": "Reorder Layers",
    "按文件名建分组添加": "Add into a Group Named After the File",
    "图层组": "Layer Group",
    "CRS 不一致：{0} 是 {1}，视图是 {2}，将实时投影显示":
        "CRS mismatch: {0} is {1}, the map view is {2}; reprojecting on the fly",
    "重置窗口": "Reset Window",
    "把窗口重置到默认位置和大小（取消最大化/最小化）":
        "Reset the window to its default position and size (unmaximize / unminimize)",
    "开启或关闭定时自动保存工程（间隔在选项里设置）":
        "Turn timed auto-save on or off (interval set in Options)",
    "撤销图层操作": "Undo Layer Operation",
    "撤销上一次图层操作（显隐、删除、恢复、排序）":
        "Undo the last layer operation (visibility, delete, restore, reorder)",
    "重做图层操作": "Redo Layer Operation",
    "重做上一次被撤销的图层操作":
        "Redo the last undone layer operation",

}


def _app():
    try:
        from PySide6.QtCore import QCoreApplication

        return QCoreApplication.instance()
    except Exception:
        _log.exception("silent exception in _app")
        return None


def install_translators(setting=None):
    if setting is None:
        try:
            from . import settings as _st

            setting = _st.get("language")
        except Exception:
            _log.exception("silent exception in install_translators")
            setting = "system"
    lang = init(setting)
    return install_qgis_translators(lang)


def install_qgis_translators(lang):
    installed = []
    if lang == "zh_CN":
        try:
            from PySide6.QtCore import QTranslator, QLibraryInfo
            path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if path and os.path.isdir(path):
                t = QTranslator(_app())
                if t.load("qtbase_zh_CN", path):
                    _app().installTranslator(t)
                    _translators.append(t)
                    installed.append("qtbase")
        except Exception:
            _log.exception("silent exception in install_qgis_translators")
        try:

            from .qt_zh import QtZhTranslator

            t = QtZhTranslator(_app())
            _app().installTranslator(t)
            _translators.append(t)
            installed.append("qt-zh")
        except Exception:
            _log.exception("silent exception in install_qgis_translators")
        try:
            from PySide6.QtCore import QTranslator

            t = _PlatformZhTranslator(_app())
            _app().installTranslator(t)
            _translators.append(t)
            installed.append("qt-platform")
        except Exception:
            _log.exception("silent exception in install_qgis_translators")
    return installed


class _PlatformZhTranslator(QTranslator):

    _TABLE = {
        "OK": "确定", "&OK": "确定",
        "Cancel": "取消", "&Cancel": "取消",
        "Apply": "应用", "&Apply": "应用",
        "Close": "关闭", "&Close": "关闭",
        "Help": "帮助", "&Help": "帮助",
        "Save": "保存", "&Save": "保存",
        "Open": "打开", "&Open": "打开",
        "Yes": "是", "&Yes": "是",
        "No": "否", "&No": "否",
        "Yes to &All": "全部是", "No to All": "全部否",
        "Do &not Save": "不保存",
        "Discard": "放弃", "&Discard": "放弃",
        "Reset": "重置", "&Reset": "重置",
        "Restore Defaults": "恢复默认",
        "Done": "完成", "Finish": "完成", "&Finish": "完成",
        "Next": "下一步", "&Next >": "下一步 >",
        "Back": "上一步", "< &Back": "< 上一步",
        "Abort": "中止", "Retry": "重试", "Ignore": "忽略",
        "Undo": "撤销", "Redo": "重做",
        "Cut": "剪切", "Copy": "复制", "Paste": "粘贴",
        "Select All": "全选",
        "All Files (*)": "所有文件 (*)",
    }

    def translate(self, context, source, disambiguation=None, n=-1):
        if context == "QPlatformTheme" or context == "QShortcut":
            return _PlatformZhTranslator._TABLE.get(source)
        return None
