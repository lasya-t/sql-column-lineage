"""Column-level lineage across a set of SQL models.

1. Load every model (name = file name) and the raw source schemas.
2. Order models so each is parsed after the models it reads from (topological sort),
   and register each model's output columns as a schema, so later `SELECT *` can expand.
3. For every output column, ask sqlglot's lineage walker which columns of the tables in
   its FROM clause feed it, through CTEs, aliases, joins, functions and window expressions.
4. Stitch model-to-model edges together into one graph from raw columns to mart columns.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage
from sqlglot.optimizer.qualify import qualify

DIALECT = "duckdb"


@dataclass
class Graph:
    # edges: "model.column" -> set of direct parent "table.column"
    parents: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    models: dict[str, list[str]] = field(default_factory=dict)  # model -> output columns

    def children(self) -> dict[str, set[str]]:
        out = defaultdict(set)
        for child, ps in self.parents.items():
            for p in ps:
                out[p].add(child)
        return out

    def upstream(self, col: str) -> set[str]:
        """All columns this one ultimately depends on; returns only the raw sources (leaves)."""
        seen, stack, leaves = set(), [col], set()
        while stack:
            c = stack.pop()
            ps = self.parents.get(c, set())
            if not ps and c != col:
                leaves.add(c)
            for p in ps:
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return leaves

    def downstream(self, col: str) -> set[str]:
        """Every column, in any model, that would change if `col` changed."""
        kids, seen, stack = self.children(), set(), [col]
        while stack:
            for k in kids.get(stack.pop(), set()):
                if k not in seen:
                    seen.add(k)
                    stack.append(k)
        return seen


def _refs(sql: str) -> set[str]:
    tree = sqlglot.parse_one(sql, read=DIALECT)
    ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    return {".".join(p for p in (t.db, t.name) if p) for t in tree.find_all(exp.Table) if t.name not in ctes}


def _toposort(models: dict[str, str], sources: set[str]) -> list[str]:
    deps = {m: {r for r in _refs(sql) if r in models} for m, sql in models.items()}
    unknown = {r for sql in models.values() for r in _refs(sql)} - set(models) - sources
    if unknown:
        raise ValueError(f"models read from unknown tables: {sorted(unknown)}")
    order, ready = [], deque(sorted(m for m, d in deps.items() if not d))
    while ready:
        m = ready.popleft()
        order.append(m)
        for n, d in deps.items():
            if m in d:
                d.discard(m)
                if not d and n not in order and n not in ready:
                    ready.append(n)
    if len(order) != len(models):
        raise ValueError(f"cycle between models: {sorted(set(models) - set(order))}")
    return order


def _nested_schema(flat: dict[str, dict]) -> dict:
    """{'raw.orders': {...}, 'stg_orders': {...}} -> sqlglot's nested {db: {table: cols}} with a default db."""
    out: dict = defaultdict(dict)
    for name, cols in flat.items():
        db, _, table = name.rpartition(".")
        out[db or "main"][table] = cols
    return dict(out)


def _unquote(name: str) -> str:
    # qualify() quotes every identifier ("qty"); strip quotes so names match across models
    return name.replace('"', "")


def _leaf_columns(node) -> set[str]:
    out = set()
    for n in node.walk():
        if not n.downstream and isinstance(n.expression, exp.Table):
            t = n.expression
            table = ".".join(p for p in (t.db if t.db != "main" else "", t.name) if p)
            out.add(_unquote(f"{table}.{n.name.split('.')[-1]}"))
    return out


def build(model_dir: str | Path, sources_file: str | Path) -> Graph:
    model_dir = Path(model_dir)
    sources = json.loads(Path(sources_file).read_text())
    models = {p.stem: p.read_text() for p in sorted(model_dir.rglob("*.sql"))}
    schema = dict(sources)
    g = Graph()
    for name in _toposort(models, set(sources)):
        sql = models[name]
        nested = _nested_schema(schema)
        tree = qualify(sqlglot.parse_one(sql, read=DIALECT), schema=nested, dialect=DIALECT, db="main")
        cols = [s.alias_or_name for s in tree.selects]
        g.models[name] = cols
        schema[name] = {c: "unknown" for c in cols}
        for col in cols:
            node = lineage(col, tree, schema=nested, dialect=DIALECT)
            g.parents[f"{name}.{col}"] |= _leaf_columns(node)
    return g
