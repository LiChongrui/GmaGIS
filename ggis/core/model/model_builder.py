# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import copy
import uuid

from ggis.core.analysis import OPS, op_label
import logging
_log = logging.getLogger("gmagis")

__all__ = [
    "NODE_INPUT", "NODE_OP", "NODE_OUTPUT", "NODE_NOTE",
    "PARAM_KEYS", "ModelNode", "Model", "ModelError",
]

NODE_INPUT = "input"
NODE_OP = "op"
NODE_OUTPUT = "output"
NODE_W = 172.0
NODE_H = 56.0
NODE_NOTE = "note"

PARAM_KEYS = ("distance", "segments", "cap_style", "join_style", "dissolve",
              "by_field", "distance_unit", "centroid_inside", "tolerance",
              "decimals", "grid_size", "clip_kind", "selected_only",
              "extra")

_DEFAULT_PARAMS = {
    "distance": 0.0,
    "segments": 8,
    "cap_style": "round",
    "join_style": "round",
    "dissolve": False,
    "by_field": "",
    "distance_unit": "map",
    "centroid_inside": False,
    "tolerance": 0.0,
    "decimals": 6,
    "grid_size": 0.0,
    "clip_kind": "",
    "selected_only": False,
    "extra": {},
}


class ModelError(Exception):
    pass


def _new_id():
    return uuid.uuid4().hex[:8]


def default_params():
    d = dict(_DEFAULT_PARAMS)
    d["extra"] = {}
    return d


class ModelNode:

    __slots__ = ("nid", "kind", "x", "y", "title", "op", "params",
                 "layer_id", "layer_name", "output_name", "add_to_map",
                 "output_path", "text", "enabled")

    def __init__(self, kind, nid="", x=0.0, y=0.0, title="", op="",
                 params=None, layer_id="", layer_name="", output_name="",
                 add_to_map=True, output_path="", text="", enabled=True):
        self.nid = str(nid or _new_id())
        self.kind = str(kind or NODE_OP)
        self.x = float(x)
        self.y = float(y)
        self.title = str(title or "")
        self.op = str(op or "")
        self.params = default_params()
        if params:
            for k in dict(params):
                if k in PARAM_KEYS:
                    self.params[k] = params[k]
        ex = self.params.get("extra")
        self.params["extra"] = dict(ex) if isinstance(ex, dict) else {}
        self.layer_id = "" if layer_id is None else str(layer_id)
        self.layer_name = str(layer_name or "")
        self.output_name = str(output_name or "")
        self.add_to_map = bool(add_to_map)
        self.output_path = str(output_path or "")
        self.text = str(text or "")
        self.enabled = bool(enabled)

    def label(self):
        if self.kind == NODE_OP:
            return op_label(self.op) or self.op
        if self.kind == NODE_NOTE:
            return self.title or "注释"
        return self.title or ("数据" if self.kind == NODE_INPUT else "结果")

    def subtitle(self):
        if self.kind == NODE_INPUT:
            return self.layer_name or ""
        if self.kind == NODE_OUTPUT:
            return self.output_name or ""
        if self.kind == NODE_NOTE:
            return (str(self.text or "").strip().splitlines() or [""])[0]
        return self.op

    def to_dict(self):
        return {
            "id": self.nid,
            "kind": self.kind,
            "x": round(float(self.x), 2),
            "y": round(float(self.y), 2),
            "title": self.title,
            "op": self.op,
            "params": copy.deepcopy(self.params),
            "layer_id": self.layer_id,
            "layer_name": self.layer_name,
            "output_name": self.output_name,
            "add_to_map": bool(self.add_to_map),
            "output_path": self.output_path,
            "text": self.text,
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, raw):
        d = dict(raw or {})
        return cls(kind=d.get("kind") or NODE_OP,
                   nid=d.get("id") or "",
                   x=d.get("x") or 0.0,
                   y=d.get("y") or 0.0,
                   title=d.get("title") or "",
                   op=d.get("op") or "",
                   params=d.get("params") or {},
                   layer_id=d.get("layer_id") or "",
                   layer_name=d.get("layer_name") or "",
                   output_name=d.get("output_name") or "",
                   add_to_map=bool(d.get("add_to_map",
                                         d.get("add_to_view",
                                               d.get("add_to_project",
                                                     True)))),
                   output_path=d.get("output_path") or "",
                   text=d.get("text") or "",
                   enabled=bool(d.get("enabled", True)))


class Model:

    def __init__(self):
        self.nodes = {}
        self.edges = []

    def node(self, nid):
        return self.nodes.get(str(nid))

    def is_empty(self):
        return not self.nodes

    def inputs_of(self, nid):
        nid = str(nid)
        return [s for s, d in self.edges if d == nid]

    def outputs_of(self, nid):
        nid = str(nid)
        return [d for s, d in self.edges if s == nid]

    def op_nodes(self):
        return [n for n in self.nodes.values() if n.kind == NODE_OP]

    def has_edge(self, src, dst):
        return (str(src), str(dst)) in [(s, d) for s, d in self.edges]

    def add_node(self, node):
        if not isinstance(node, ModelNode):
            raise ModelError("add_node 需要 ModelNode")
        if node.nid in self.nodes:
            node.nid = _new_id()
        self.nodes[node.nid] = node
        return node

    def remove_node(self, nid):
        nid = str(nid)
        if nid not in self.nodes:
            return False
        self.nodes.pop(nid, None)
        self.edges = [(s, d) for s, d in self.edges if s != nid and d != nid]
        return True

    def connect(self, src, dst):
        src, dst = str(src), str(dst)
        if src not in self.nodes or dst not in self.nodes:
            raise ModelError("连线的一端不存在")
        if src == dst:
            raise ModelError("不能连到自己")
        if self.node(src).kind == NODE_NOTE \
                or self.node(dst).kind == NODE_NOTE:
            raise ModelError("注释节点不参与连线")
        if self.node(dst).kind == NODE_INPUT:
            raise ModelError("数据节点不能作为终点")
        if self.node(src).kind == NODE_OUTPUT:
            raise ModelError("结果节点不能再往后连")
        if (src, dst) in self.edges:
            return False
        spec = OPS.get(self.node(dst).op, {}) if self.node(dst).kind == NODE_OP \
            else {}
        limit = 2 if spec.get("needs_overlay") else 1
        if self.node(dst).kind == NODE_INPUT:
            limit = 0
        incoming = self.inputs_of(dst)
        if len(incoming) >= limit:
            self.edges = [(s, d) for s, d in self.edges
                          if not (d == dst and s == incoming[0])]
        self.edges.append((src, dst))
        if self._has_cycle():
            self.edges = [(s, d) for s, d in self.edges
                          if not (s == src and d == dst)]
            raise ModelError("这条连线会让模型形成环")
        return True

    def disconnect(self, src, dst):
        src, dst = str(src), str(dst)
        before = len(self.edges)
        self.edges = [(s, d) for s, d in self.edges
                      if not (s == src and d == dst)]
        return len(self.edges) != before

    def clear(self):
        self.nodes = {}
        self.edges = []

    def _has_cycle(self):
        try:
            self.topo_order()
            return False
        except ModelError:
            exc_note("_has_cycle @ ggis/core/model/model_builder.py:302")
            return True

    def topo_order(self):
        live = [n.nid for n in self.nodes.values()
                if n.kind not in (NODE_INPUT, NODE_NOTE)]
        indeg = {nid: 0 for nid in live}
        adj = {nid: [] for nid in live}
        for s, d in self.edges:
            if s in indeg and d in adj:
                adj[s].append(d)
                indeg[d] += 1
        queue = [nid for nid in self.nodes if nid in indeg and indeg[nid] == 0]
        out = []
        while queue:
            nid = queue.pop(0)
            out.append(nid)
            for d in adj[nid]:
                indeg[d] -= 1
                if indeg[d] == 0:
                    queue.append(d)
        if len(out) != len(live):
            raise ModelError("模型里存在循环连线，无法确定执行顺序")
        return out

    def _spec_of(self, node):
        return OPS.get(node.op, {}) if node.kind == NODE_OP else {}

    def problems(self, layer_ids=None):
        out = []
        if not [n for n in self.nodes.values() if n.kind != NODE_NOTE]:
            return [("模型是空的——请从左侧拖入算法与数据图层", ())]

        try:
            self.topo_order()
        except ModelError:
            exc_note("problems @ ggis/core/model/model_builder.py:352")
            out.append(("模型里存在循环连线，无法确定执行顺序", ()))

        inputs = [n for n in self.nodes.values() if n.kind == NODE_INPUT]
        outputs = [n for n in self.nodes.values() if n.kind == NODE_OUTPUT]
        ops = self.op_nodes()

        for n in inputs:
            if not n.layer_id:
                out.append(("「{0}」还没有选择图层", (n.label(),)))
            elif layer_ids is not None and n.layer_id not in layer_ids:
                out.append(("「{0}」的数据源图层已不在工程中", (n.label(),)))

        for n in ops:
            if not n.enabled:
                continue
            spec = self._spec_of(n)
            need = 2 if spec.get("needs_overlay") else 1
            got = len([s for s in self.inputs_of(n.nid)
                       if self.node(s) is not None
                       and self.node(s).kind != NODE_NOTE])
            if got < need:
                if need == 2 and got == 1:
                    out.append(("「{0}」还需要一路叠加输入", (n.label(),)))
                else:
                    out.append(("「{0}」缺少输入数据", (n.label(),)))

        if not outputs:
            out.append(("模型里没有「结果」节点，跑完不知道结果放哪", ()))
        for n in outputs:
            if not self.inputs_of(n.nid):
                out.append(("「{0}」没有接到任何上游节点", (n.label(),)))
            elif not str(n.output_name or "").strip():
                out.append(("「{0}」还没有起名字", (n.label(),)))
        return out

    def warnings(self, layer_ids=None):
        if self.problems(layer_ids):
            return []
        try:
            reach = self._reachable_from_outputs()
        except Exception:
            _log.exception("silent exception in warnings")
            return []
        out = []
        for n in self.op_nodes():
            if not n.enabled:
                out.append(("「{0}」已禁用，运行时会跳过它（下游改用它的输入）",
                            (n.label(),)))
        for n in self.op_nodes():
            if n.nid not in reach:
                out.append(("「{0}」的结果没有被任何结果节点接收，"
                            "跑完不会保留", (n.label(),)))
        return out

    def _reachable_from_outputs(self):
        seen = set()
        stack = [n.nid for n in self.nodes.values()
                 if n.kind == NODE_OUTPUT]
        while stack:
            nid = stack.pop()
            for s in self.inputs_of(nid):
                if s not in seen:
                    seen.add(s)
                    stack.append(s)
        return seen

    def copy_fragment(self, nids):
        keep = [str(n) for n in (nids or []) if str(n) in self.nodes]
        if not keep:
            return [], []
        nodes = [self.nodes[n].to_dict() for n in keep]
        edges = [(s, d) for s, d in self.edges
                 if s in keep and d in keep]
        return nodes, edges

    def paste_fragment(self, nodes, edges, dx=0.0, dy=0.0):
        mapping = {}
        out = []
        for nd in (nodes or []):
            try:
                n = ModelNode.from_dict(nd)
            except Exception:
                _log.exception("silent exception in paste_fragment")
                continue
            old = str(nd.get("id") or "")
            n.x = float(n.x) + float(dx)
            n.y = float(n.y) + float(dy)
            self.add_node(n)
            mapping[old] = n.nid
            out.append(n.nid)
        ok = 0
        for s, d in (edges or []):
            ns, nd = mapping.get(str(s)), mapping.get(str(d))
            if ns is None or nd is None:
                continue
            try:
                if self.connect(ns, nd):
                    ok += 1
            except ModelError:
                exc_note("paste_fragment @ ggis/core/model/model_builder.py:470")
                continue
        return out, ok

    def auto_layout(self, origin_x=40.0, origin_y=40.0,
                    col_gap=90.0, row_gap=28.0):
        try:
            order = self.topo_order()
        except ModelError:
            exc_note("auto_layout @ ggis/core/model/model_builder.py:489")
            order = [n.nid for n in self.nodes.values()
                     if n.kind not in (NODE_INPUT, NODE_NOTE)]
        depth = {}
        for nid in order:
            ins = [s for s in self.inputs_of(nid)
                   if self.node(s) is not None
                   and self.node(s).kind != NODE_NOTE]
            depth[nid] = (0 if not ins
                          else max(int(depth.get(s, 0)) for s in ins) + 1)
        for n in self.nodes.values():
            if n.kind == NODE_INPUT:
                depth.setdefault(n.nid, 0)
        cols = {}
        for nid, d in depth.items():
            cols.setdefault(int(d), []).append(nid)
        out = {}
        x = float(origin_x)
        for d in sorted(cols):
            ids = sorted(cols[d],
                         key=lambda n: (float(self.node(n).y),
                                        float(self.node(n).x)))
            y = float(origin_y)
            for nid in ids:
                out[nid] = (x, y)
                y += float(NODE_H) + float(row_gap)
            x += float(NODE_W) + float(col_gap)
        return out

    def to_dict(self):
        ids = set(self.nodes)
        return {
            "nodes": [self.nodes[i].to_dict() for i in self.nodes],
            "edges": [[s, d] for s, d in self.edges
                      if s in ids and d in ids],
        }

    @classmethod
    def from_dict(cls, raw):
        m = cls()
        d = dict(raw or {})
        for nd in d.get("nodes") or []:
            try:
                n = ModelNode.from_dict(nd)
            except Exception:
                _log.exception("silent exception in from_dict")
                continue
            if n.nid in m.nodes:
                n.nid = _new_id()
            m.nodes[n.nid] = n
        for e in d.get("edges") or []:
            try:
                s, t = str(e[0]), str(e[1])
            except Exception:
                _log.exception("silent exception in from_dict")
                continue
            if s in m.nodes and t in m.nodes and s != t:
                m.edges.append((s, t))
        return m
