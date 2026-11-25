import argparse

from .graph import Graph, build


def mermaid(g: Graph, focus: str | None = None) -> str:
    """Mermaid flowchart of column edges (optionally only those touching `focus`'s upstream/downstream)."""
    keep = None
    if focus:
        keep = {focus} | g.downstream(focus) | {p for c in g.downstream(focus) | {focus} for p in g.parents.get(c, ())}
        keep |= {c for c in g.parents if c in keep} | {p for c in list(keep) for p in g.parents.get(c, ())}
    nid = lambda s: s.replace(".", "__")  # noqa: E731
    lines = ["flowchart LR"]
    for child, ps in sorted(g.parents.items()):
        for p in sorted(ps):
            if keep is None or (child in keep and p in keep):
                lines.append(f'  {nid(p)}["{p}"] --> {nid(child)}["{child}"]')
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(prog="lineage", description="Column-level lineage for a folder of SQL models")
    ap.add_argument("--models", default="models")
    ap.add_argument("--sources", default="models/sources.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trace", help="which raw columns feed this column")
    t.add_argument("column")
    i = sub.add_parser("impact", help="what changes if this column changes")
    i.add_argument("column")
    m = sub.add_parser("mermaid", help="print a Mermaid diagram")
    m.add_argument("--focus")
    a = ap.parse_args()

    g = build(a.models, a.sources)
    if a.cmd == "trace":
        print(f"{a.column} is computed from:")
        for c in sorted(g.upstream(a.column)):
            print(f"  {c}")
    elif a.cmd == "impact":
        values = g.downstream(a.column)
        rows = g.downstream(a.column, include_filters=True) - values
        print(f"if {a.column} changes:")
        print(f"  values change in ({len(values)}):")
        for c in sorted(values):
            print(f"    {c}")
        print(f"  which rows are counted changes in ({len(rows)} more):")
        for c in sorted(rows):
            print(f"    {c}")
    else:
        print(mermaid(g, a.focus))


if __name__ == "__main__":
    main()
