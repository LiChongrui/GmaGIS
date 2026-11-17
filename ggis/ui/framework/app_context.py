# -*- coding: utf-8 -*-

from PySide6.QtCore import QObject, Signal

from ggis.core.app import settings as _app_settings

SERVICE_NAMES = (
    "assembly",
    "wiring",
    "lifecycle",
    "projects",
    "settings_ctl",
    "views",
    "actions",
    "shell",
)

REGION_NAMES = ("title", "ribbon", "dock", "status", "view")


class EventBus(QObject):

    project_opened = Signal(object)
    project_dirty_changed = Signal(object)
    view_activated = Signal(object)
    view_closed = Signal(object)
    settings_applied = Signal(object)
    shutdown_started = Signal()


class SettingsPort:

    def get(self, key, default=None):
        return _app_settings.get(key, default)

    def set(self, key, value, persist=True):
        return _app_settings.set(key, value, persist=persist)

    def save(self, **kwargs):
        return _app_settings.save(**kwargs)

    def all_settings(self):
        return _app_settings.all_settings()


class AppContext:

    def __init__(self, mw):
        self.mw = mw
        self.view_host = None
        self.settings = SettingsPort()
        self.events = EventBus(mw)
        self.regions = {}
        self.services = {}
        self.boot_failures = []
        self.boot = lambda *_a, **_k: None
        self.wiring = None

    @property
    def project(self):
        from ggis.core.model.project import GgsProject
        return GgsProject.instance()

    def svc(self, name):
        if name not in SERVICE_NAMES:
            raise KeyError("未登记的服务: %s" % name)
        try:
            return self.services[name]
        except KeyError:
            raise RuntimeError("服务 %s 尚未实装" % name) from None

    def region(self, name):
        if name not in REGION_NAMES:
            raise KeyError("未知分区: %s" % name)
        return self.regions.get(name)

    def register(self, name, service):
        if name not in SERVICE_NAMES:
            raise KeyError("未登记的服务: %s" % name)
        self.services[name] = service
        return service
