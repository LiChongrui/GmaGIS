# -*- coding: utf-8 -*-


from __future__ import annotations

class ViewControlGroup:

    def __init__(self, kind, docks=None, view_tag="",
                 toolbar_tabs=None, status_kind=None, canvas=None,
                 status_widgets=None):

        self.kind = kind
        self._docks = list(docks or [])
        self.view_tag = view_tag
        self.toolbar_tabs = list(toolbar_tabs or [])
        self.status_kind = status_kind or kind
        self.status_widgets = list(status_widgets or [])
        self.canvas = canvas

    def docks(self):
        return list(self._docks)

    def toolbar_pages(self):
        return [pg for _t, pg in self.toolbar_tabs if pg is not None]

    def show(self, main, view):
        k = self.kind
        if k == "map":
            main.dock_region._show_active_map_layer_dock(view)
        elif k == "layout":
            main.dock_region._set_layout_chrome_visible(True, view)
        elif k == "model":
            main.dock_region._set_model_chrome_visible(True, view)

    def hide(self, main):
        k = self.kind
        if k == "map":
            main.dock_region._hide_all_map_layer_docks()
        elif k == "layout":
            main.dock_region._set_layout_chrome_visible(False, None)
        elif k == "model":
            main.dock_region._set_model_chrome_visible(False, None)

    def teardown(self, main, vid):
        main._unregister_view_docks(vid)
