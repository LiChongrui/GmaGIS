# -*- coding: utf-8 -*-

from PySide6.QtCore import QObject, Signal
import logging
import uuid

_log = logging.getLogger("gmagis")


class _MLayer:

    __slots__ = ("id", "layer", "visible", "parent", "seq")

    kind = "layer"

    def __init__(self, layer, visible=True, seq=None):
        try:
            self.id = str(layer.id())
        except Exception:
            _log.exception("silent exception in _MLayer.__init__")
            self.id = uuid.uuid4().hex
        self.layer = layer
        self.visible = bool(visible)
        self.parent = None
        self.seq = seq


class _MGroup:

    __slots__ = ("id", "name", "visible", "expanded", "children", "parent")

    kind = "group"

    def __init__(self, name, visible=True, expanded=True):
        self.id = uuid.uuid4().hex
        self.name = str(name or "")
        self.visible = bool(visible)
        self.expanded = bool(expanded)
        self.children = []
        self.parent = None


class MapLayerTree(QObject):

    layerAdded = Signal(object)
    layerRemoved = Signal(str)
    visibilityChanged = Signal(str, bool)
    orderChanged = Signal()
    membershipChanged = Signal()
    structureChanged = Signal()

    def __init__(self, project):
        super().__init__()
        self._project = project
        self._roots = []
        self._seq_counter = 0
        try:
            project.layerRemoved.connect(self._on_proj_layer_removed)
        except Exception:
            _log.exception("silent exception in __init__")

    def next_seq(self):
        self._seq_counter += 1
        return self._seq_counter

    def dispose(self):
        try:
            self._project.layerRemoved.disconnect(self._on_proj_layer_removed)
        except Exception:
            _log.exception("silent exception in dispose")

    def _walk_layers(self):
        stack = [c for c in reversed(self._roots)]
        while stack:
            nd = stack.pop()
            if nd.kind == "group":
                stack.extend(reversed(nd.children))
            else:
                yield nd

    def _layer_nodes(self):
        return list(self._walk_layers())

    def _find_layer(self, layer_id):
        lid = str(layer_id)
        for nd in self._walk_layers():
            if nd.id == lid:
                return nd
        return None

    def _find_group(self, group_id):
        gid = str(group_id or "")
        if not gid:
            return None
        stack = list(self._roots)
        while stack:
            nd = stack.pop()
            if nd.kind != "group":
                continue
            if nd.id == gid:
                return nd
            stack.extend(nd.children)
        return None

    def _find_node(self, node_id):
        nid = str(node_id or "")
        if not nid:
            return None
        stack = list(self._roots)
        while stack:
            nd = stack.pop()
            if nd.id == nid:
                return nd
            if nd.kind == "group":
                stack.extend(nd.children)
        return None

    def _effective(self, node):
        vis = True
        nd = node
        while nd is not None:
            vis = vis and bool(nd.visible)
            if not vis:
                return False
            nd = nd.parent
        return bool(vis)

    def _container_of(self, node):
        if node.parent is None:
            return self._roots
        return node.parent.children

    def _attach(self, node, group, pos=None):
        children = self._roots if group is None else group.children
        node.parent = group
        if pos is None or int(pos) >= len(children):
            children.append(node)
        else:
            children.insert(max(0, int(pos)), node)

    def _detach(self, node):
        cont = self._container_of(node)
        if cont is None:
            return False
        try:
            cont.remove(node)
        except ValueError:
            return False
        node.parent = None
        return True

    def _is_descendant(self, node, ancestor):
        nd = node
        while nd is not None:
            if nd is ancestor:
                return True
            nd = nd.parent
        return False

    def _emit_render(self, order=False):
        if order:
            self.orderChanged.emit()
        self.membershipChanged.emit()
        self.structureChanged.emit()

    def _mark_dirty(self):
        try:
            self._project.set_dirty(True)
        except Exception:
            _log.exception("silent exception in _mark_dirty")

    def init_from_project(self):
        self._roots = [_MLayer(l, l.is_visible())
                       for l in reversed(list(self._project.layers()))]
        self.membershipChanged.emit()
        self.structureChanged.emit()

    def from_built(self, built):
        self._roots = []
        self._load_built_list(built or [])
        self.membershipChanged.emit()
        self.structureChanged.emit()

    def _load_built_list(self, nodes):
        has_group = any(isinstance(e, dict) for e in nodes)
        seq = list(nodes) if has_group else list(reversed(nodes))
        seen = set()
        for nd in seq:
            if isinstance(nd, dict) and str(nd.get("kind") or "") == "group":
                g = _MGroup(str(nd.get("name") or ""),
                            visible=bool(nd.get("visible", True)),
                            expanded=bool(nd.get("expanded", True)))
                self._roots.append(g)
                self._load_group_children(g, nd.get("children") or [], seen)
            elif isinstance(nd, (tuple, list)) and nd and nd[0] is not None:
                lyr = nd[0]
                try:
                    lid = str(lyr.id())
                except Exception:
                    _log.exception("silent exception in _load_built_list")
                    continue
                if lid in seen:
                    continue
                seen.add(lid)
                vis = bool(nd[2]) if len(nd) > 2 else True
                self._roots.append(_MLayer(lyr, vis))

    def _load_group_children(self, group, kids, seen):
        for nd in (kids or []):
            if isinstance(nd, dict) and str(nd.get("kind") or "") == "group":
                g = _MGroup(str(nd.get("name") or ""),
                            visible=bool(nd.get("visible", True)),
                            expanded=bool(nd.get("expanded", True)))
                g.parent = group
                group.children.append(g)
                self._load_group_children(g, nd.get("children") or [], seen)
            elif isinstance(nd, (tuple, list)) and nd and nd[0] is not None:
                lyr = nd[0]
                try:
                    lid = str(lyr.id())
                except Exception:
                    _log.exception("silent exception in _load_group_children")
                    continue
                if lid in seen:
                    continue
                seen.add(lid)
                vis = bool(nd[2]) if len(nd) > 2 else True
                m = _MLayer(lyr, vis)
                m.parent = group
                group.children.append(m)

    def add(self, layer, index=None, visible=True, pos=None, group=None,
            seq=None):
        if self.has(layer.id()):
            return
        m = _MLayer(layer, visible, seq)
        dst = self._find_group(group) if group else None
        children = dst.children if dst is not None else self._roots
        if pos is not None:
            self._attach(m, dst, max(0, int(pos)))
        elif index is not None:
            total = len(self._layer_nodes())
            p = max(0, total - max(0, int(index)))
            self._insert_at_dfs(m, p)
        else:
            target = int(seq) if seq is not None else 0
            p = 0
            for nd in children:
                s = getattr(nd, "seq", None)
                s = 0 if s is None else int(s)
                if s <= target:
                    break
                p += 1
            self._attach(m, dst, p)
        self.layerAdded.emit(layer)
        self._emit_render(order=True)
        self._mark_dirty()

    def _insert_at_dfs(self, node, p):
        def _count(children):
            n = 0
            for c in children:
                n += _count(c.children) if c.kind == "group" else 1
            return n

        def _place(children, group):
            cnt = 0
            for i, c in enumerate(children):
                if cnt == p:
                    self._attach(node, group, i)
                    return True
                if c.kind == "group":
                    sub = _count(c.children)
                    if p < cnt + sub:
                        return _place(c.children, c)
                    cnt += sub
                else:
                    cnt += 1
            if cnt == p:
                self._attach(node, group)
                return True
            return False

        if not _place(self._roots, None):
            self._attach(node, None)

    def remove(self, layer_id):
        lid = str(layer_id)
        m = self._find_layer(lid)
        if m is None:
            return
        self._detach(m)
        self.layerRemoved.emit(lid)
        self._emit_render()

    def has(self, layer_id):
        return self._find_layer(layer_id) is not None

    def place_layer(self, layer, group_id=None, pos=0, visible=None):
        lid = str(layer.id())
        m = self._find_layer(lid)
        fresh = False
        if m is None:
            m = _MLayer(layer, True if visible is None else bool(visible))
            self._roots.insert(0, m)
            self.layerAdded.emit(layer)
            fresh = True
        elif visible is not None and bool(visible) != m.visible:
            m.visible = bool(visible)
            self.visibilityChanged.emit(lid, m.visible)
        dst = self._find_group(group_id) if group_id else None
        children = self._roots if dst is None else dst.children
        cur_cont = self._container_of(m)
        try:
            cur_idx = cur_cont.index(m)
        except (ValueError, AttributeError):
            cur_idx = -1
        want = max(0, int(pos or 0))
        if (not fresh and cur_cont is children
                and cur_idx == min(want, len(children))):
            self.structureChanged.emit()
            return
        self._detach(m)
        self._attach(m, dst, want)
        self._emit_render(order=True)
        self._mark_dirty()

    def set_visible(self, layer_id, on):
        m = self._find_layer(str(layer_id))
        if m is None:
            return
        on = bool(on)
        if m.visible == on:
            return
        m.visible = on
        self.visibilityChanged.emit(m.id, on)
        self.membershipChanged.emit()
        self._mark_dirty()

    def set_group_visible(self, group_id, on):
        g = self._find_group(group_id)
        if g is None:
            return
        on = bool(on)
        if g.visible == on:
            return
        g.visible = on
        self.membershipChanged.emit()
        self.structureChanged.emit()
        self._mark_dirty()

    def is_visible(self, layer_id):
        m = self._find_layer(layer_id)
        return bool(m.visible) if m is not None else False

    def is_effectively_visible(self, layer_id):
        m = self._find_layer(layer_id)
        if m is None:
            return False
        return self._effective(m)

    def group_visible(self, group_id):
        g = self._find_group(group_id)
        return bool(g.visible) if g is not None else True

    def group_name(self, group_id):
        g = self._find_group(group_id)
        return str(g.name) if g is not None else ""

    def set_group_all_visible(self, group_id, on):
        g = self._find_group(group_id)
        if g is None:
            return
        on = bool(on)
        g.visible = on
        stack = list(g.children)
        while stack:
            nd = stack.pop()
            if nd.kind == "group":
                stack.extend(nd.children)
            elif nd.visible != on:
                nd.visible = on
                self.visibilityChanged.emit(nd.id, on)
        self.membershipChanged.emit()
        self.structureChanged.emit()
        self._mark_dirty()

    def add_group(self, name="组", parent_id=None, pos=None):
        g = _MGroup(name)
        dst = self._find_group(parent_id) if parent_id else None
        children = self._roots if dst is None else dst.children
        if pos is None:
            children.append(g)
        else:
            children.insert(max(0, min(int(pos), len(children))), g)
        self.structureChanged.emit()
        self._mark_dirty()
        return g

    def remove_group(self, group_id):
        g = self._find_group(group_id)
        if g is None:
            return
        gone = []
        stack = [g]
        while stack:
            nd = stack.pop()
            if nd.kind == "group":
                stack.extend(nd.children)
            else:
                gone.append(nd)
        self._detach(g)
        for m in gone:
            m.parent = None
            self.layerRemoved.emit(m.id)
        self._emit_render()
        self._mark_dirty()

    def rename_group(self, group_id, name):
        g = self._find_group(group_id)
        if g is None:
            return
        g.name = str(name or "")
        self._mark_dirty()

    def set_group_expanded(self, group_id, expanded):
        g = self._find_group(group_id)
        if g is None:
            return
        g.expanded = bool(expanded)

    def reorder(self, ids_bottom_to_top):
        target = [str(x) for x in (ids_bottom_to_top or [])]
        target_ui = list(reversed(target))
        node_map = {n.id: n for n in self._layer_nodes()}
        seq = []
        seen = set()
        for lid in target_ui:
            n = node_map.pop(lid, None)
            if n is not None and id(n) not in seen:
                seen.add(id(n))
                seq.append(n)
        for n in self._layer_nodes():
            if id(n) not in seen:
                seen.add(id(n))
                seq.append(n)
        if not seq:
            return
        self._reorder_layout(seq)
        self._emit_render(order=True)

    def _reorder_layout(self, seq):
        lyr_parent = {}
        group_parent = {}

        def _scan(children, parent):
            for nd in children:
                if nd.kind == "group":
                    group_parent[nd] = parent
                    _scan(nd.children, nd)
                else:
                    lyr_parent[nd] = parent

        _scan(self._roots, None)
        all_groups = list(group_parent)
        self._roots = []
        for g in all_groups:
            g.children = []
            g.parent = None
        for m in seq:
            m.parent = None

        def _ensure_chain(g):
            chain = []
            p = g
            while p is not None:
                chain.append(p)
                p = group_parent.get(p)
            for grp in reversed(chain):
                if grp.parent is None and grp not in self._roots:
                    self._attach(grp, group_parent.get(grp))

        for m in seq:
            par = lyr_parent.get(m)
            if par is None:
                self._attach(m, None)
            else:
                _ensure_chain(par)
                self._attach(m, par)
        for g in all_groups:
            if g.parent is None and g not in self._roots:
                par = group_parent.get(g)
                if par is not None and (par in self._roots
                                        or par.parent is not None):
                    self._attach(g, par)
                else:
                    self._attach(g, None)

    def move_nodes(self, node_ids, dst_group_id=None, dst_index=0):
        nodes = []
        seen = set()
        for nid in (node_ids or []):
            n = self._find_node(nid)
            if n is None or id(n) in seen:
                continue
            seen.add(id(n))
            nodes.append(n)
        if not nodes:
            return False
        dst = self._find_group(dst_group_id) if dst_group_id else None
        if dst_group_id and dst is None:
            return False
        for n in nodes:
            if n.kind != "group":
                continue
            if dst is not None and self._is_descendant(dst, n):
                return False
        children = self._roots if dst is None else dst.children
        before = 0
        for n in nodes:
            cont = self._container_of(n)
            if cont is children:
                try:
                    if cont.index(n) < int(dst_index or 0):
                        before += 1
                except ValueError:
                    pass
        taken = []
        for n in nodes:
            old = (self._container_of(n), )
            try:
                old_idx = old[0].index(n)
            except (ValueError, AttributeError):
                old_idx = -1
            self._detach(n)
            taken.append((n, old_idx))
        eff = max(0, int(dst_index or 0) - before)
        for k, (n, _old) in enumerate(taken):
            self._attach(n, dst, eff + k)
        self._emit_render(order=True)
        self._mark_dirty()
        return True

    def layers(self):
        return [nd.layer for nd in reversed(self._layer_nodes())]

    def visible_layers(self):
        out = []
        for nd in self._layer_nodes():
            if self._effective(nd) and not nd.layer.is_table():
                out.append(nd.layer)
        out.reverse()
        return out

    def entries(self):
        out = []
        for nd in self._layer_nodes():
            out.append((nd.layer, self._effective(nd)))
        out.reverse()
        return out

    def layer_ids(self):
        return [nd.id for nd in reversed(self._layer_nodes())]

    def tree_snapshot(self):
        out = []

        def _walk(children):
            for nd in children:
                if nd.kind == "group":
                    out.append({"kind": "group", "id": nd.id,
                                "name": nd.name,
                                "visible": bool(nd.visible),
                                "expanded": bool(nd.expanded),
                                "children": _walk(nd.children)})
                else:
                    out.append({"kind": "layer", "id": nd.id,
                                "visible": bool(nd.visible)})

        _walk(self._roots)
        return out

    def _on_proj_layer_removed(self, layer_id):
        self.remove(layer_id)
