import webbrowser
from pathlib import Path
from dataclasses import asdict

from pyvis.network import Network

from lobster.ontology.graph import OntologyGraph
from lobster.ontology.models import NodeType, EdgeType
from lobster.storage.db import init_db, upsert_node, upsert_edge
from lobster.ontology.resolver import resolve
from lobster.ingestion.github import build_library_from_github
from lobster.ingestion.pypi import enrich_library_from_pypi
from lobster.ingestion.stackoverflow import build_so_nodes
from lobster.ingestion.hackernews import build_hn_nodes

NODE_STYLES = {
    NodeType.LIBRARY:     {"color": "#4C9BE8", "size": 40, "shape": "dot"},
    NodeType.DEVELOPER:   {"color": "#58C48A", "size": 20, "shape": "dot"},
    NodeType.SO_QUESTION: {"color": "#F5A623", "size": 12, "shape": "square"},
    NodeType.HN_POST:     {"color": "#E8734C", "size": 12, "shape": "triangle"},
    NodeType.COMPANY:     {"color": "#A87FE8", "size": 18, "shape": "dot"},
}

EDGE_LABELS = {
    EdgeType.HAS_MAINTAINER: "maintains",
    EdgeType.HAS_QUESTION:   "asked on SO",
    EdgeType.MENTIONED_IN:   "on HN",
    EdgeType.HAS_ISSUE:      "issue",
    EdgeType.WORKS_AT:       "works at",
}


def _node_label(node_id: str, node_data) -> str:
    t = node_data.get("type")
    d = node_data.get("data")
    if t == NodeType.LIBRARY:
        return d.name
    if t == NodeType.DEVELOPER:
        return d.login
    if t == NodeType.SO_QUESTION:
        return d.title[:40] + "…" if len(d.title) > 40 else d.title
    if t == NodeType.HN_POST:
        return d.title[:40] + "…" if len(d.title) > 40 else d.title
    return node_id


def _node_tooltip(node_id: str, node_data) -> str:
    t = node_data.get("type")
    d = node_data.get("data")
    if t == NodeType.LIBRARY:
        return (
            f"<b>{d.name}</b><br>"
            f"Stars: {d.stars:,}<br>"
            f"Downloads/wk: {d.weekly_downloads:,}<br>"
            f"Last commit: {d.last_commit_days_ago}d ago<br>"
            f"Open issues: {d.open_issues}"
        )
    if t == NodeType.DEVELOPER:
        return f"<b>{d.login}</b><br>Sources: {', '.join(d.sources)}"
    if t == NodeType.SO_QUESTION:
        return f"Score: {d.score} | Answers: {d.answer_count} | Answered: {d.is_answered}"
    if t == NodeType.HN_POST:
        return f"Points: {d.points} | Comments: {d.comments}"
    return node_id


def build_graph(packages: list[str]) -> OntologyGraph:
    from rich.console import Console
    console = Console()
    graph = OntologyGraph()
    init_db()

    for package in packages:
        with console.status(f"[cyan]Resolving {package}..."):
            identity = resolve(package)

        confidence_color = "green" if identity.confidence >= 0.9 else "yellow" if identity.confidence >= 0.6 else "red"
        console.print(
            f"[{confidence_color}]{package}[/] → "
            f"{identity.github_owner}/{identity.github_repo} "
            f"({identity.confidence:.0%} {identity.resolution_method})"
        )

        try:
            with console.status(f"[cyan]Fetching data for {package}..."):
                lib, developers, edges = build_library_from_github(
                    identity.github_owner, identity.github_repo, identity.pypi_name
                )
                lib = enrich_library_from_pypi(lib)
                so_questions, so_edges = build_so_nodes(lib.id, identity.so_tag)
                hn_posts, hn_edges = build_hn_nodes(lib.id, identity.hn_query)

            graph.add_library(lib)
            upsert_node(lib.id, "Library", asdict(lib))

            for dev in developers:
                graph.add_developer(dev)
                upsert_node(dev.id, "Developer", asdict(dev))
            for q in so_questions:
                graph.add_so_question(q)
                upsert_node(q.id, "SOQuestion", asdict(q))
            for post in hn_posts:
                graph.add_hn_post(post)
                upsert_node(post.id, "HNPost", asdict(post))
            for e in edges + so_edges + hn_edges:
                graph.add_edge(e)
                upsert_edge(e.source_id, e.target_id, e.edge_type, e.weight)

        except Exception as ex:
            console.print(f"[red]Failed {package}: {ex}[/]")

    return graph


def render(graph: OntologyGraph, output_path: str = "lobster_graph.html"):
    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ffffff",
        directed=True,
    )
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)

    g = graph.g

    # find developers shared across multiple libraries (the interesting cross-edges)
    dev_library_count: dict[str, int] = {}
    for node_id, data in g.nodes(data=True):
        if data.get("type") == NodeType.DEVELOPER:
            lib_neighbors = [
                n for n in g.predecessors(node_id)
                if g.nodes[n].get("type") == NodeType.LIBRARY
            ]
            dev_library_count[node_id] = len(lib_neighbors)

    for node_id, data in g.nodes(data=True):
        node_type = data.get("type", NodeType.DEVELOPER)
        style = NODE_STYLES.get(node_type, {"color": "#aaaaaa", "size": 10, "shape": "dot"})
        label = _node_label(node_id, data)
        tooltip = _node_tooltip(node_id, data)

        size = style["size"]
        color = style["color"]

        # highlight shared developers
        if node_type == NodeType.DEVELOPER and dev_library_count.get(node_id, 0) > 1:
            color = "#FFD700"
            size = 30
            label = f"★ {label}"
            tooltip = f"<b>Shared maintainer ({dev_library_count[node_id]} libraries)</b><br>{tooltip}"

        net.add_node(
            node_id,
            label=label,
            title=tooltip,
            color=color,
            size=size,
            shape=style["shape"],
        )

    for src, dst, data in g.edges(data=True):
        edge_type = data.get("type", "")
        label = EDGE_LABELS.get(edge_type, "")
        width = 1

        # thicker edges for maintainer relationships
        if edge_type == EdgeType.HAS_MAINTAINER:
            width = max(1, min(5, int(data.get("weight", 1) / 10)))

        net.add_edge(src, dst, title=label, width=width, color="#555577")

    # legend as a disconnected node cluster
    legend_items = [
        ("Library", "#4C9BE8"),
        ("Developer", "#58C48A"),
        ("Shared Dev", "#FFD700"),
        ("SO Question", "#F5A623"),
        ("HN Post", "#E8734C"),
    ]
    for i, (lbl, color) in enumerate(legend_items):
        nid = f"__legend_{i}"
        net.add_node(nid, label=lbl, color=color, size=12, x=-900, y=-300 + i * 60,
                     physics=False, shape="dot", font={"size": 11})

    out = Path(output_path)
    net.save_graph(str(out))
    webbrowser.open(out.resolve().as_uri())
    return str(out.resolve())
