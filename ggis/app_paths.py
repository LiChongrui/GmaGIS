# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import os

__all__ = [
    "app_root", "python_dir", "data_dir", "sample_dir",
    "resources_dir", "build_dir", "cache_dir", "tile_cache_dir",
    "ensure_dir",
    "APP_NAME", "user_root", "user_dir", "resource_path", "user_path",
    "log_dir", "ResourceManager",
]

APP_NAME = "GmaGIS"


def app_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def python_dir():
    return os.path.join(app_root(), "python")


def data_dir():
    return os.path.join(app_root(), "data")


def sample_dir():
    return os.path.join(data_dir(), "sample")


def resources_dir():
    return os.path.join(app_root(), "resources")


def build_dir():
    return os.path.join(app_root(), "build")


def user_root():
    env = os.environ.get("APPDATA")
    if env:
        return os.path.join(env, APP_NAME)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return os.path.join(xdg, APP_NAME)
    return os.path.join(os.path.expanduser("~"), ".config", APP_NAME)


def user_dir():
    return ensure_dir(user_root())


def resource_path(*parts):
    return os.path.join(resources_dir(), *parts)


def user_path(*parts, mkdir=True):
    p = os.path.join(user_root(), *parts)
    if mkdir and parts:
        last = parts[-1]
        target = os.path.dirname(p) if "." in last else p
        ensure_dir(target)
    return p


def log_dir():
    return ensure_dir(os.path.join(user_root(), "logs"))


def cache_dir():
    default = os.path.join(data_dir(), "cache")
    root = ""
    try:
        from ggis.core.app import settings as _S
        root = str(_S.get("cache_root") or "").strip()
    except Exception:
        exc_note("cache_dir @ ggis/app_paths.py:150")
        return _user_cache_dir(default)
    if not root:
        return _user_cache_dir(default)
    try:
        if not os.path.isabs(root):
            root = os.path.join(app_root(), root)
        return os.path.normpath(root)
    except Exception:
        exc_note("cache_dir @ ggis/app_paths.py:158")
        return _user_cache_dir(default)


def _user_cache_dir(fallback):
    try:
        p = ensure_dir(os.path.join(user_root(), "cache"))
        return p if p else fallback
    except Exception:
        exc_note("_user_cache_dir @ ggis/app_paths.py:171")
        return fallback


def tile_cache_dir():
    return os.path.join(cache_dir(), "tiles")


def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        exc_note("ensure_dir @ ggis/app_paths.py:189")
        pass
    return path


class ResourceManager:

    def __init__(self, app_root=None, user_root=None):
        mod = globals()
        self._app_root = os.path.abspath(app_root) if app_root \
            else mod["app_root"]()
        self._user_root = os.path.abspath(user_root) if user_root \
            else mod["user_root"]()

    @property
    def app_root(self):
        return self._app_root

    @property
    def resources_dir(self):
        return os.path.join(self._app_root, "resources")

    def resource_path(self, *parts):
        return os.path.join(self.resources_dir, *parts)

    @property
    def user_root(self):
        return self._user_root

    def user_path(self, *parts, mkdir=True):
        p = os.path.join(self._user_root, *parts)
        if mkdir:
            target = (os.path.dirname(p) if parts and "." in parts[-1] else p)
            ensure_dir(target)
        return p

    def __repr__(self):
        return "ResourceManager(app_root=%r, user_root=%r)" % (
            self._app_root, self._user_root)
