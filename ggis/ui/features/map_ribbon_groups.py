# -*- coding: utf-8 -*-

from __future__ import annotations

from ggis.common.util.exc_report import exc_note
MAP_RIBBON_TAG = "map:__shared__"

from ._hostdeps import _tr, RibbonGroup, RibbonPage, QMenu, QAction, icons, \
    basemap_choices


class MapRibbonGroup(RibbonGroup):

    TITLE = ""

    def __init__(self, host, parent=None):
        super().__init__(_tr(self.TITLE), parent)
        self._host = host
        self.build()

    def act(self, name):
        return self._host.ctx.svc("actions").get(name)

    def menu(self, object_name="", items=()):
        m = QMenu(self)
        if object_name:
            m.setObjectName(object_name)
        for it in items:
            if it is None:
                m.addSeparator()
            else:
                m.addAction(self.act(it))
        return m

    def build(self):
        raise NotImplementedError


class MapClipboardGroup(MapRibbonGroup):

    TITLE = "剪贴板"

    def build(self):
        self.add_action(self.act("paste_features"),
                        variant="GgsBigCheckButtonStyle1")
        for n in ("cut_features", "copy_features", "copy_path"):
            self.add_action(self.act(n), big=False)


class NavGroup(MapRibbonGroup):

    TITLE = "导航"

    def build(self):
        self.add_action(self.act("pan"), variant="GgsBigCheckButtonStyle1")
        c1 = self.small_column()
        for n in ("zoom_in", "zoom_full", "locate_xy"):
            self.add_action(self.act(n), big=False, col=c1, icon_only=True)
        c2 = self.small_column()
        for n in ("zoom_out", "zoom_visible", "refresh"):
            self.add_action(self.act(n), big=False, col=c2, icon_only=True)


class BasemapLayerGroup(MapRibbonGroup):

    TITLE = "图层"

    def build(self):
        m_base = GgsBasemapMenu(self)
        host = self._host
        for key, src in basemap_choices():
            a = QAction(icons.icon(src.icon), _tr(src.title), self)
            icons.bind(a, src.icon, size=16)
            a.setData(key)
            a.triggered.connect(
                lambda _c=False, k=key: host.ctx.svc("views")._map_state().add_basemap(k))
            m_base.addAction(a)
        m_base.addSeparator()
        m_base.addAction(self.act("add_tile"))
        self.add_dropdown(self.act("basemap"), m_base, style2=True,
                          variant="GgsBigMenuButtonStyle1",
                          tip=_tr("添加在线底图"))

        m_add = QMenu(self)
        m_add.addAction(self.act("add_browse"))
        m_add.addAction(self.act("add_from_path"))
        m_add.addSeparator()
        m_add.addAction(self.act("add_db_layer"))
        self.add_dropdown(self.act("add_data"), m_add, style2=True,
                          variant="GgsBigMenuButtonStyle3",
                          tip=_tr("向当前工程添加图层 / 数据"))

        self.add_action(self.act("new_layer"), big=True,
                        variant="GgsBigButtonStyle1",
                        tip=_tr("新建矢量图层"))


class MapSelectGroup(MapRibbonGroup):

    TITLE = "选择"

    def build(self):
        m_sel = self.menu("GgsSelectMenuMap",
                          ("select_rect", "select_poly", "select_lasso",
                           "select_circle", "select_line"))
        self.add_dropdown(self.act("select"), m_sel, style2=True,
                          variant="GgsBigMenuButtonStyle4",
                          tip=_tr("框选地图要素"))
        col = self.small_column()
        for n in ("select_attr", "select_bylocation", "select_clear"):
            self.add_action(self.act(n), big=False, col=col)


class QueryGroup(MapRibbonGroup):

    TITLE = "查询"

    def build(self):
        m_meas = self.menu("GgsMeasureMenu",
                           ("measure_dist", "measure_area", "measure_angle"))
        self.add_dropdown(self.act("measure_len"), m_meas, style2=True,
                          variant="GgsBigMenuButtonStyle4",
                          tip=_tr("测量地图上的距离"))
        self.add_action(self.act("identify"), big=True,
                        variant="GgsBigButtonStyle1",
                        tip=_tr("识别"))
        self.add_action(self.act("coord_transform"), big=True,
                        variant="GgsBigButtonStyle1")


class GeoprocessingGroup(MapRibbonGroup):

    TITLE = "地理处理"

    def build(self):
        self.add_action(self.act("toolbox"), variant="GgsBigButtonStyle1")


class SpectralToolsGroup(MapRibbonGroup):

    TITLE = "光谱工具"

    def build(self):
        self.add_action(self.act("spectral_profile"),
                        variant="GgsBigButtonStyle1")


class EditClipboardGroup(MapRibbonGroup):

    TITLE = "剪贴板"

    def build(self):
        m = self.menu(items=("paste_feat", "paste_feat_to"))
        self.add_dropdown(self.act("paste_feat"), m, big=True, style2=True,
                          variant="GgsBigMenuButtonStyle2")
        for n in ("copy_feat", "cut_feat"):
            self.add_action(self.act(n), big=False)


class EditSessionGroup(MapRibbonGroup):

    TITLE = "编辑会话"

    def build(self):
        self.add_action(self.act("save_edits"), big=True,
                        variant="GgsBigCheckButtonStyle1")
        col = self.small_column()
        for n in ("undo_edit", "redo_edit", "discard_edits"):
            self.add_action(self.act(n), big=False, col=col)


class FeatureSelectGroup(MapRibbonGroup):

    TITLE = "要素选择"

    def build(self):
        m = self.menu("GgsSelectMenuEdit",
                      ("edit_select_rect", "edit_select_poly",
                       "edit_select_lasso", "edit_select_circle",
                       "edit_select_line"))
        self.add_dropdown(self.act("edit_select"), m, style2=True,
                          variant="GgsBigMenuButtonStyle4",
                          tip=_tr("框选当前图层的要素"))
        col = self.small_column()
        for n in ("zoom_sel", "selected_attrs", "select_clear"):
            self.add_action(self.act(n), big=False, col=col)


class FeatureEditGroup(MapRibbonGroup):

    TITLE = "要素编辑"

    def build(self):
        for n in ("add_feature", "move_feature", "delete_feature"):
            self.add_action(self.act(n), variant="GgsBigCheckButtonStyle1")


class VertexEditGroup(MapRibbonGroup):

    TITLE = "折点编辑"

    def build(self):
        self.add_action(self.act("vertex_edit"),
                        variant="GgsBigCheckButtonStyle1")
        m_vsel = self.menu("GgsVertexSelectMenu",
                           ("vertex_select_rect", "vertex_select_lasso"))
        self.add_dropdown(self.act("vertex_select"), m_vsel, style2=True,
                          variant="GgsBigMenuButtonStyle4",
                          active_by_main=True,
                          tip=_tr("选择折点"))
        col = self.small_column()
        for n in ("vertex_add", "vertex_move", "vertex_delete"):
            self.add_action(self.act(n), big=False, col=col)
        col_out = self.small_column()
        for n in ("commit_edit", "cancel_edit", "reset_edit"):
            self.add_action(self.act(n), big=False, col=col_out)


class SnapGroup(MapRibbonGroup):

    TITLE = "捕捉"

    def build(self):
        m = GgsSnapMenu(self)
        for n in self._host.ctx.svc("actions").snap_acts():
            m.addAction(self.act(n))
        self.add_dropdown(self.act("snap_enable"), m, style2=True,
                          variant="GgsBigMenuButtonStyle4",
                          active_by_main=True,
                          tip=_tr("捕捉设置：选择要吸附到的几何部位"))


class GeometryOpGroup(MapRibbonGroup):

    TITLE = "几何操作"

    def build(self):
        for n in ("split_features", "reshape_features"):
            self.add_action(self.act(n), variant="GgsBigCheckButtonStyle1")
        for n in ("merge_selected", "combine_selected", "multipart_single",
                  "align_features", "break_features", "simplify_selected"):
            self.add_action(self.act(n), big=False)


class RasterProfileGroup(MapRibbonGroup):

    TITLE = "剖面"

    def build(self):
        self.add_action(self.act("raster_profile"),
                        variant="GgsBigButtonStyle1")


class GgsPanelDockGroup(MapRibbonGroup):

    def __init__(self, host, title, items, parent=None):
        self._items = tuple(items or ())
        self.TITLE = title
        super().__init__(host, parent)

    def build(self):
        host = self._host
        for dock, dock_title, icon_name in self._items:
            if callable(dock):
                try:
                    dock = dock()
                except Exception:
                    exc_note("build @ ggis/ui/features/map_ribbon_groups.py:462")
                    dock = None
            if dock is None:
                continue
            a = host.ctx.region("dock")._panel_activate_action(dock, dock_title, icon_name)
            host._panel_acts.append((dock, a))
            self.add_action(a, big=True, variant="GgsBigButtonStyle1")


class GgsViewToolsGroup(MapRibbonGroup):

    TITLE = "对话框"

    def build(self):
        self.add_action(self.act("style_manager"), big=True,
                        variant="GgsBigButtonStyle1")


def build_map_ribbon_pages(host):
    pg_map = RibbonPage()
    pg_map.add_group(MapClipboardGroup(host))
    pg_map.add_group(NavGroup(host))
    pg_map.add_group(BasemapLayerGroup(host))
    pg_map.add_group(MapSelectGroup(host))
    pg_map.add_group(QueryGroup(host))
    pg_analyze = RibbonPage()
    pg_analyze.add_group(GeoprocessingGroup(host))
    pg_analyze.add_group(SpectralToolsGroup(host))
    pg_view = RibbonPage()
    pg_edit = RibbonPage()
    pg_edit.add_group(EditClipboardGroup(host))
    pg_edit.add_group(EditSessionGroup(host))
    pg_edit.add_group(FeatureSelectGroup(host))
    pg_edit.add_group(FeatureEditGroup(host))
    pg_edit.add_group(VertexEditGroup(host))
    pg_edit.add_group(SnapGroup(host))
    pg_edit.add_group(GeometryOpGroup(host))
    pg_raster = RibbonPage()
    pg_raster.add_group(RasterProfileGroup(host))
    return {
        "map": pg_map,
        "analyze": pg_analyze,
        "view": pg_view,
        "edit": pg_edit,
        "raster": pg_raster,
    }


class GgsBasemapMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsBasemapMenu")
class GgsSnapMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSnapMenu")
