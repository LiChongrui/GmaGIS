# -*- coding: utf-8 -*-
import os
import subprocess
from PySide6.QtCore import (Qt, QDir, Signal, QModelIndex, QAbstractItemModel, QMimeData, QUrl)
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QAbstractItemView, QFileIconProvider
from ggis.common.styling import icons as _icons
from ggis.common.util.exc_report import exc_note
from ggis.common.widgets.itemviews import GgsTreeView
from ggis.core.app import settings as _settings
from ggis.io.registry import is_supported
from ggis.core.app import i18n as _i18n
_tr = _i18n.tr


class _BrowserNode:

    __slots__ = ("path", "name", "parent", "_kids", "_loaded", "_refreshing",
                 "_has_subs")

    def __init__(self, path, name, parent=None):
        self.path = path
        self.name = name
        self.parent = parent
        self._kids = []
        self._loaded = False
        self._refreshing = False

    def kids(self):
        if self._refreshing:
            return self._kids
        if self._loaded:
            return self._kids
        self._loaded = True
        if self.path and _is_gis_file(os.path.basename(self.path)):
            try:
                subs = _browser_sublayers(self.path)
            except Exception:
                exc_note("kids @ ggis/common/widgets/standard.py:2783")
                subs = []
            if subs:
                for lname, gtype in subs:
                    self._kids.append(
                        _DbLayerNode(self, self.path, lname, gtype))
                return self._kids
        try:
            d = QDir(self.path)
            d.setFilter(QDir.Filter.Dirs | QDir.Filter.Files
                        | QDir.Filter.NoDotAndDotDot
                        | QDir.Filter.Hidden)
            d.setSorting(QDir.SortFlag.DirsFirst | QDir.SortFlag.Name
                         | QDir.SortFlag.IgnoreCase)
            for fi in d.entryInfoList():
                name = fi.fileName()
                if fi.isDir():
                    self._kids.append(
                        _BrowserNode(fi.absoluteFilePath(), name, self))
                elif _is_gis_file(name):
                    self._kids.append(
                        _BrowserNode(fi.absoluteFilePath(), name, self))
        except Exception:
            exc_note("kids @ ggis/common/widgets/standard.py:2805")
            pass
        return self._kids

    def forget(self):
        self._kids = []
        self._loaded = False


class _DbLayerNode(_BrowserNode):

    __slots__ = ("layer_name", "gtype")

    def __init__(self, parent, path, layer_name, gtype=""):
        super().__init__(path, layer_name, parent)
        self.layer_name = str(layer_name or "")
        self.gtype = str(gtype or "")

    def kids(self):
        return []

    def forget(self):
        pass


def _is_gis_file(name):
    low = name.lower()
    return any(low.endswith(ext) for ext in _GIS_SUFFIXES)


def _norm_path(path):
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        exc_note("_norm_path @ ggis/common/widgets/standard.py:2861")
        return str(path or "")


def _folder_label(path):
    s = str(path or "").replace("\\", "/").rstrip("/")
    if not s:
        return str(path or "")
    name = s.rsplit("/", 1)[-1]
    if name.endswith(":"):
        return _tr("本地磁盘 ({})").format(name)
    return name


class _FavoritesNode(_BrowserNode):

    __slots__ = ("_model",)

    def __init__(self, model, name):
        super().__init__("", name)
        self._model = model

    def kids(self):
        if getattr(self, "_refreshing", False):
            return self._kids
        if self._loaded:
            return self._kids
        self._loaded = True
        out = []
        for p in self._model.favorites():
            out.append(_BrowserNode(p, _folder_label(p), self))
        self._kids = out
        return out

    def forget(self):
        super().forget()


class GgsBrowserModel(QAbstractItemModel):

    FAVORITES_KEY = "browser_favorites"
    FAVORITES_MAX = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons = QFileIconProvider()
        self._roots = []
        self._favorites_root = _FavoritesNode(self, _tr("收藏夹"))
        self._roots.append(self._favorites_root)
        home = QDir.homePath()
        if home:
            self._roots.append(_BrowserNode(home, _tr("主目录")))
        for fi in QDir.drives():
            path = fi.absoluteFilePath()
            label = path.rstrip("/\\") or path
            self._roots.append(
                _BrowserNode(path, _tr("本地磁盘 ({})").format(label)))

    def favorites(self):
        try:
            vals = _settings.get(self.FAVORITES_KEY) or []
        except Exception:
            exc_note("favorites @ ggis/common/widgets/standard.py:2951")
            vals = []
        out = []
        for p in vals:
            s = str(p or "").strip()
            if s and s not in out:
                out.append(s)
        return out

    def is_favorite(self, path):
        key = _norm_path(path)
        return any(_norm_path(p) == key for p in self.favorites())

    def add_favorite(self, path):
        path = str(path or "").strip()
        if not path or self.is_favorite(path):
            return False
        vals = self.favorites() + [path]
        self._save_favorites(vals[-self.FAVORITES_MAX:])
        self._favorites_root.forget()
        self._notify_favorites(add_row=len(vals) - 1)
        return True

    def remove_favorite(self, path):
        key = _norm_path(path)
        vals = self.favorites()
        row = next((i for i, p in enumerate(vals)
                    if _norm_path(p) == key), -1)
        if row < 0:
            return False
        vals.pop(row)
        self._save_favorites(vals)
        self._favorites_root.forget()
        self._notify_favorites(remove_row=row)
        return True

    def _save_favorites(self, vals):
        try:
            _settings.set(self.FAVORITES_KEY, list(vals))
        except Exception:
            exc_note("_save_favorites @ ggis/common/widgets/standard.py:2991")
            pass

    def favorites_index(self):
        if self._favorites_root in self._roots:
            return self.createIndex(
                self._roots.index(self._favorites_root), 0,
                self._favorites_root)
        return QModelIndex()

    def _notify_favorites(self, add_row=None, remove_row=None):
        idx = self.favorites_index()
        if not idx.isValid():
            return
        if add_row is not None:
            self.beginInsertRows(idx, add_row, add_row)
            self.endInsertRows()
        elif remove_row is not None:
            self.beginRemoveRows(idx, remove_row, remove_row)
            self.endRemoveRows()

    @staticmethod
    def _node_of(index):
        if index is None or not index.isValid():
            return None
        try:
            node = index.internalPointer()
        except Exception:
            exc_note("_node_of @ ggis/common/widgets/standard.py:3030")
            return None
        return node if isinstance(node, _BrowserNode) else None

    def columnCount(self, parent=QModelIndex()):
        return 1

    def flags(self, index):
        f = super().flags(index)
        if index.isValid() and self.filePath(index):
            f |= Qt.ItemFlag.ItemIsDragEnabled
        return f

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self._roots)
        node = self._node_of(parent)
        return len(node.kids()) if node is not None else 0

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            node = self._roots[row]
        else:
            p = self._node_of(parent)
            kids = p.kids() if p is not None else []
            if row >= len(kids):
                return QModelIndex()
            node = kids[row]
        return self.createIndex(row, column, node)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = self._node_of(index)
        if node is None or node.parent is None:
            return QModelIndex()
        p = node.parent
        if p in self._roots:
            return self.createIndex(self._roots.index(p), 0, p)
        gp = p.parent
        if gp is None:
            return QModelIndex()
        try:
            return self.createIndex(gp.kids().index(p), 0, p)
        except ValueError:
            exc_note("parent @ ggis/common/widgets/standard.py:3089")
            return QModelIndex()

    def hasChildren(self, parent=QModelIndex()):
        if not parent.isValid():
            return True
        node = self._node_of(parent)
        if node is None:
            return False
        if isinstance(node, _FavoritesNode):
            return True
        if isinstance(node, _DbLayerNode):
            return False
        if node.path and _is_gis_file(node.name):
            v = getattr(node, "_has_subs", None)
            if v is None:
                try:
                    v = bool(_browser_sublayers(node.path))
                except Exception:
                    exc_note("hasChildren @ ggis/common/widgets/standard.py:3113")
                    v = False
                node._has_subs = v
            if v:
                return True
        return QDir(node.path).exists() and not _is_gis_file(node.name)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        return None

    def canFetchMore(self, parent):
        return False

    def fetchMore(self, parent):
        pass

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = self._node_of(index)
        if node is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return node.name
        if role == Qt.ItemDataRole.DecorationRole:
            if isinstance(node, _FavoritesNode):
                try:
                    return _icons.icon("bookmark", size=16)
                except Exception:
                    exc_note("data @ ggis/common/widgets/standard.py:3146")
                    pass
            if isinstance(node, _DbLayerNode):
                try:
                    return _icons.icon("table", size=16)
                except Exception:
                    exc_note("data @ ggis/common/widgets/standard.py:3153")
                    pass
            try:
                return self._icons.icon(QFileIconProvider.IconType.Folder) \
                    if self._is_dir(node) else \
                    self._icons.icon(QFileIconProvider.IconType.File)
            except Exception:
                exc_note("data @ ggis/common/widgets/standard.py:3159")
                return None
        if role == Qt.ItemDataRole.ToolTipRole:
            if isinstance(node, _FavoritesNode):
                return node.name
            if isinstance(node, _DbLayerNode):
                tip = "%s | %s" % (node.path, node.layer_name)
                if node.gtype:
                    tip += "  (%s)" % _short_geom_type(node.gtype)
                return tip
            return node.path
        return None

    @staticmethod
    def _is_dir(node):
        if isinstance(node, _FavoritesNode):
            return True
        if isinstance(node, _DbLayerNode):
            return False
        return not _is_gis_file(node.name) and QDir(node.path).exists()

    def filePath(self, index):
        node = self._node_of(index)
        return node.path if node is not None else ""

    def mimeData(self, indexes):
        m = QMimeData()
        urls = []
        lines = []
        seen_paths = set()
        for i in indexes:
            node = self._node_of(i)
            if isinstance(node, _DbLayerNode):
                lines.append("%s|%s" % (node.path, node.layer_name))
                if node.path and node.path not in seen_paths:
                    seen_paths.add(node.path)
                    urls.append(QUrl.fromLocalFile(node.path))
                continue
            p = node.path if node is not None else ""
            if p:
                urls.append(QUrl.fromLocalFile(p))
        if urls:
            m.setUrls(urls)
        if lines:
            try:
                m.setData("application/x-ggis-uri",
                          "\n".join(lines).encode("utf-8"))
            except Exception:
                exc_note("mimeData @ ggis/common/widgets/standard.py:3226")
                pass
        return m

    def refresh(self, index=None):
        if index is None or not index.isValid():
            for row, root in enumerate(self._roots):
                self._refresh_node_children(self.createIndex(row, 0, root), root)
            return
        node = self._node_of(index)
        if node is None:
            return
        self._refresh_node_children(index, node)

    def _refresh_node_children(self, index, node):
        old = self.rowCount(index)
        node._kids = []
        node._loaded = False
        node._refreshing = True
        try:
            if old > 0:
                self.beginRemoveRows(index, 0, old - 1)
                self.endRemoveRows()
        finally:
            node._refreshing = False
        new = self.rowCount(index)
        if new > 0:
            self.beginInsertRows(index, 0, new - 1)
            self.endInsertRows()


def _browser_sublayers(path):
    sfx = os.path.splitext(str(path or ""))[1].lower()
    if sfx not in (".gpkg", ".gdb", ".sqlite", ".kml", ".kmz", ".gml"):
        return []
    try:
        from ggis.io.vector_io import list_vector_layers
        return list_vector_layers(path) or []
    except Exception:
        exc_note("_browser_sublayers @ ggis/common/widgets/standard.py:3289")
        return []


def _short_geom_type(gtype):
    s = str(gtype or "")
    for key, label in (("Point", "点"), ("LineString", "线"),
                       ("Polygon", "面"), ("Multi", "多部件"),
                       ("GeometryCollection", "集合")):
        if key in s:
            return label
    return s


class GgsBrowserView(GgsTreeView):

    fileActivated = Signal(str)
    layerActivated = Signal(str, str)
    databaseRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsBrowserView")
        self._model = GgsBrowserModel(self)
        self.setModel(self._model)
        self.setAnimated(False)
        self.setIndentation(16)
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setRootIsDecorated(True)
        self.setExpandsOnDoubleClick(True)
        self.setHeaderHidden(True)
        self.doubleClicked.connect(self._on_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._popup_menu)

    def _on_double_clicked(self, index):
        node = self._model._node_of(index)
        if isinstance(node, _DbLayerNode):
            self.layerActivated.emit(node.path, node.layer_name)
            return
        path = self._model.filePath(index)
        if not path or QDir(path).exists():
            return
        self.fileActivated.emit(path)

    def session_state(self):
        out = []

        def _walk(idx):
            m = self._model
            for r in range(m.rowCount(idx)):
                c = m.index(r, 0, idx)
                if not self.isExpanded(c):
                    continue
                p = str(m.filePath(c) or "")
                if p:
                    out.append(p)
                _walk(c)

        _walk(QModelIndex())
        return {"expanded": out} if out else None

    def restore_session(self, state):
        paths = (state or {}).get("expanded") \
            if isinstance(state, dict) else None
        if not isinstance(paths, (list, tuple)):
            return
        m = self._model

        def _key(s):
            s = str(s or "").replace("\\", "/")
            while len(s) > 1 and s.endswith("/"):
                s = s[:-1] or s
            return s.lower()

        want = {_key(p) for p in paths if isinstance(p, str) and p}
        if not want:
            return

        def _walk(idx):
            if m.canFetchMore(idx):
                m.fetchMore(idx)
            for r in range(m.rowCount(idx)):
                c = m.index(r, 0, idx)
                p = str(m.filePath(c) or "")
                if not p:
                    continue
                kp = _key(p)
                if kp in want:
                    self.expand(c)
                    _walk(c)
                elif any(w.startswith(kp + "/") for w in want):
                    _walk(c)

        _walk(QModelIndex())

    def _popup_menu(self, pos):
        idx = self.indexAt(pos)
        menu = self._build_menu(idx)
        if menu is not None and menu.actions():
            menu.exec(self.viewport().mapToGlobal(pos))

    def _build_menu(self, index):
        menu = QMenu(self)
        menu.setObjectName("GgsBrowserMenu")
        path = self._model.filePath(index) if index.isValid() else ""
        node = self._model._node_of(index)
        is_fav_root = isinstance(node, _FavoritesNode)

        def _add(text, icon_name, slot):
            a = menu.addAction(_icons.icon(icon_name, size=16), _tr(text))
            a.triggered.connect(slot)
            return a

        if isinstance(node, _DbLayerNode):
            label = node.layer_name if not node.gtype else \
                "%s  (%s)" % (node.layer_name, _short_geom_type(node.gtype))
            _add("添加到地图", "add_vector",
                 lambda _c=False, n=node:
                     self.layerActivated.emit(n.path, n.layer_name))
            menu.addSeparator()
            _add("复制完整路径", "copy_path",
                 lambda _c=False, t="%s | %s" % (node.path, node.layer_name):
                     self._copy_path(t))
            menu.addSeparator()
            _add("刷新", "refresh", self.refresh)
            return menu
        is_dir = bool(path) and QDir(path).exists() \
            and not _is_gis_file(os.path.basename(path))
        sub_layers = _browser_sublayers(path) if path and not is_dir else []
        supported = bool(path) and is_supported(path)

        if is_dir:
            _add("展开", "expand_all",
                 lambda: self.expand(index))
            _add("折叠", "collapse_all",
                 lambda: self.collapse(index))
            menu.addSeparator()
            if self._model.is_favorite(path):
                _add("从收藏夹移除", "bookmark",
                     lambda: self._remove_favorite(index))
            else:
                _add("添加到收藏夹", "bookmark",
                     lambda: self._add_favorite(index))
            menu.addSeparator()
            _add("在资源管理器中打开", "folder",
                 lambda: self._reveal_in_explorer(path))
            _add("复制完整路径", "copy_path",
                 lambda: self._copy_path(path))
            menu.addSeparator()
            _add("刷新", "refresh", self.refresh)
        elif sub_layers:
            _add("添加数据库到工程", "add_vector",
                 lambda: self.fileActivated.emit(path))
            sub = menu.addMenu(_icons.icon("table", size=16),
                               _tr("添加图层（{}）").format(len(sub_layers)))
            for lname, gtype in sub_layers:
                label = lname if not gtype else \
                    "%s  (%s)" % (lname, _short_geom_type(gtype))
                a = sub.addAction(_icons.icon("add_vector", size=16),
                                  _tr(label))
                a.triggered.connect(
                    lambda _c=False, p=path, n=lname:
                        self.layerActivated.emit(p, n))
            menu.addSeparator()
            _add("在资源管理器中显示", "folder",
                 lambda: self._reveal_in_explorer(path))
            _add("复制完整路径", "copy_path",
                 lambda: self._copy_path(path))
            menu.addSeparator()
            _add("刷新", "refresh", self.refresh)
        elif path and supported:
            _add("添加到地图", "add_vector",
                 lambda: self.fileActivated.emit(path))
            menu.addSeparator()
            _add("在资源管理器中显示", "folder",
                 lambda: self._reveal_in_explorer(path))
            _add("复制完整路径", "copy_path",
                 lambda: self._copy_path(path))
            menu.addSeparator()
            _add("刷新", "refresh", self.refresh)
        elif path:
            hint = menu.addAction(_tr("该文件不是受支持的数据源"))
            hint.setEnabled(False)
            hint.setIcon(_icons.icon("info", size=16))
            menu.addSeparator()
            _add("在资源管理器中显示", "folder",
                 lambda: self._reveal_in_explorer(path))
            _add("复制完整路径", "copy_path",
                 lambda: self._copy_path(path))
            menu.addSeparator()
            _add("刷新", "refresh", self.refresh)
        else:
            _add("添加文件夹到收藏夹…", "bookmark",
                 self._pick_favorite_folder)
            if is_fav_root and not self._model.favorites():
                hint = menu.addAction(_tr("（也可以右键任意文件夹加入）"))
                hint.setEnabled(False)
            menu.addSeparator()
            _add("刷新", "refresh", self.refresh)
        return menu

    def _pick_favorite_folder(self):
        from PySide6.QtWidgets import QFileDialog
        start = self._model.favorites()[-1] if self._model.favorites() \
            else QDir.homePath()
        path = QFileDialog.getExistingDirectory(
            self, _tr("添加到收藏夹"), start)
        if not path:
            return False
        if not self._model.add_favorite(path):
            return False
        fav = self._model.favorites_index()
        if fav.isValid():
            self.expand(fav)
            new = self._model.index(len(self._model.favorites()) - 1, 0, fav)
            if new.isValid():
                self.setCurrentIndex(new)
                self.scrollTo(new)
        return True
    def _add_favorite(self, index):
        path = self._model.filePath(index)
        if not path or not self._model.add_favorite(path):
            return False
        fav = self._model.favorites_index()
        if fav.isValid():
            self.expand(fav)
            row = len(self._model.favorites()) - 1
            new = self._model.index(row, 0, fav)
            if new.isValid():
                self.setCurrentIndex(new)
                self.scrollTo(new)
        return True

    def _remove_favorite(self, index):
        return self._model.remove_favorite(self._model.filePath(index))

    def _copy_path(self, path):
        try:
            QApplication.clipboard().setText(str(path))
        except Exception:
            exc_note("_copy_path @ ggis/common/widgets/standard.py:3592")
            pass

    def _reveal_in_explorer(self, path):
        p = str(path or "")
        if not p:
            return
        try:
            if os.path.isdir(p):
                os.startfile(p)
            else:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        except Exception:
            exc_note("_reveal_in_explorer @ ggis/common/widgets/standard.py:3605")
            try:
                os.startfile(os.path.dirname(p))
            except Exception:
                exc_note("_reveal_in_explorer @ ggis/common/widgets/standard.py:3608")
                pass

    def expand_favorites(self):
        fav = self._model.favorites_index()
        if fav.isValid():
            self.expand(fav)

    def path_of(self, index):
        return self._model.filePath(index)

    def refresh(self):
        idx = self.currentIndex()
        path = self._model.filePath(idx) if idx.isValid() else ""
        if not path:
            self._model.refresh()
            return
        self._model.refresh(idx)
        self.reveal_path(path)

    def reveal_path(self, path):
        want = _norm_path(path)
        if not want:
            return False
        try:
            for row in range(self._model.rowCount(QModelIndex())):
                if self._walk_to(self._model.index(row, 0, QModelIndex()),
                                 want):
                    return True
        except Exception:
            exc_note("reveal_path @ ggis/common/widgets/standard.py:3654")
            pass
        return False

    def _walk_to(self, idx, want):
        cur = _norm_path(self._model.filePath(idx))
        if cur == want:
            try:
                self.setCurrentIndex(idx)
                self.expand(idx)
                self.scrollTo(idx)
            except Exception:
                exc_note("_walk_to @ ggis/common/widgets/standard.py:3665")
                pass
            return True
        if cur and not want.startswith(cur + "/"):
            return False
        try:
            self.expand(idx)
            n = self._model.rowCount(idx)
        except Exception:
            exc_note("_walk_to @ ggis/common/widgets/standard.py:3674")
            return False
        for row in range(n):
            if self._walk_to(self._model.index(row, 0, idx), want):
                return True
        return False


_GIS_SUFFIXES = (
    ".shp", ".gpkg", ".geojson", ".json", ".kml", ".kmz", ".gml", ".dxf",
    ".csv", ".tif", ".tiff", ".img", ".asc", ".jpg", ".jpeg", ".png",
    ".mbtiles", ".sqlite", ".gdb", ".gpx", ".las", ".laz", ".nc", ".grib",
    ".qgz", ".qgs", ".qlr", ".gpkg-shm", ".zip",
)
