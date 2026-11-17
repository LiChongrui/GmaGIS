# -*- coding: utf-8 -*-

from PySide6.QtCore import QObject, Signal


class RenderBackend(QObject):

    rendered = Signal(object, int, bool)

    backend_type = "base"

    def set_scene(self, version, specs, dst_crs=None):
        raise NotImplementedError

    def push_scene(self):
        raise NotImplementedError

    def request(self, seq, task):
        raise NotImplementedError

    def invalidate(self):
        raise NotImplementedError

    def is_warm(self):
        raise NotImplementedError

    def failed(self):
        raise NotImplementedError

    def is_busy(self):
        raise NotImplementedError

    def push_settings(self):
        raise NotImplementedError

    def push_tiles(self, recs):
        raise NotImplementedError

    def push_features(self, src, layer_name, wkbs, attrs):
        return False

    def prefetch(self, src, layer=None):
        return False

    def warmup(self):
        return False

    def builds_flat_in_subprocess(self):
        return True

    def stop(self):
        raise NotImplementedError


def make_backend(kind, host, multi_worker=False):
    if kind == "gpu_tile":
        from .gpu_tile.backend import GpuTileBackend
        return GpuTileBackend(host, multi_worker=multi_worker)
    raise ValueError("unknown render backend: %r" % (kind,))
