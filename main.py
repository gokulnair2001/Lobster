import sys
from dataclasses import asdict

from rich.console import Console
from rich.table import Table
from rich import box

from lobster.storage.db import init_db, upsert_node, upsert_edge
from lobster.ontology.graph import OntologyGraph
from lobster.ontology.resolver import resolve
from lobster.ingestion.github import build_library_from_github
from lobster.ingestion.pypi import enrich_library_from_pypi
from lobster.ingestion.stackoverflow import build_so_nodes
from lobster.ingestion.hackernews import build_hn_nodes
from lobster.analysis.health import compute_health
from lobster.analysis.decay import compute_decay, persist_snapshot
from lobster.analysis.compare import run_compare
from lobster.analysis.visualize import build_graph, render

console = Console()


def run(package: str):
    init_db()
    graph = OntologyGraph()

    with console.status(f"[cyan]Resolving identity for '{package}'..."):
        identity = resolve(package)

    confidence_color = "green" if identity.confidence >= 0.9 else "yellow" if identity.confidence >= 0.6 else "red"
    console.print(
        f"[{confidence_color}]Resolved:[/] "
        f"pypi={identity.pypi_name}  "
        f"github={identity.github_owner}/{identity.github_repo}  "
        f"confidence={identity.confidence:.0%} ({identity.resolution_method})"
    )

    if identity.confidence < 0.5:
        console.print("[yellow]Warning: low-confidence resolution — results may be inaccurate[/yellow]")

    with console.status(f"[cyan]Fetching GitHub data for {identity.github_owner}/{identity.github_repo}..."):
        lib, developers, edges = build_library_from_github(
            identity.github_owner, identity.github_repo, identity.pypi_name
        )

    with console.status("[cyan]Fetching PyPI data..."):
        lib = enrich_library_from_pypi(lib)

    with console.status("[cyan]Fetching Stack Overflow questions..."):
        so_questions, so_edges = build_so_nodes(lib.id, identity.so_tag)

    with console.status("[cyan]Fetching HackerNews mentions..."):
        hn_posts, hn_edges = build_hn_nodes(lib.id, identity.hn_query)

    # populate graph
    graph.add_library(lib)
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

    upsert_node(lib.id, "Library", asdict(lib))

    report = compute_health(graph, lib.id)
    decay_signals = compute_decay(report)
    persist_snapshot(report)

    console.rule(f"[bold green]Lobster — {report.library}")

    summary = Table(box=box.SIMPLE, show_header=False)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="white")
    summary.add_row("Health Score", f"[bold]{report.score}/100[/bold]")
    summary.add_row("GitHub Stars", f"{report.stars:,}")
    summary.add_row("Weekly Downloads", f"{report.weekly_downloads:,}")
    summary.add_row("Last Commit", f"{report.last_commit_days_ago}d ago" if report.last_commit_days_ago else "unknown")
    summary.add_row("Open Issues", str(report.open_issues))
    summary.add_row("SO Questions", str(report.so_questions))
    summary.add_row("SO Answer Rate", f"{report.so_answer_rate:.0%}")
    summary.add_row("HN Mentions", str(report.hn_mentions))
    console.print(summary)

    console.print("[bold]Signals:[/bold]")
    for s in report.signals:
        console.print(f"  • {s}")

    if decay_signals:
        console.print("\n[bold]Decay / Trend:[/bold]")
        for d in decay_signals:
            color = "red" if d.severity == "warn" else "yellow" if d.severity == "watch" else "green"
            console.print(f"  [{color}]{d.message}[/]")

    stats = graph.stats()
    console.print(f"\n[dim]Graph: {stats['nodes']} nodes, {stats['edges']} edges[/dim]")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        console.print("Usage: main.py <package> | compare <pkg1> <pkg2> ...")
        sys.exit(1)

    if args[0] == "compare":
        if len(args) < 2:
            console.print("[red]Provide at least one package to compare[/]")
            sys.exit(1)
        run_compare(args[1:])
    elif args[0] == "graph":
        if len(args) < 2:
            console.print("[red]Provide at least one package[/]")
            sys.exit(1)
        graph = build_graph(args[1:])
        path = render(graph)
        console.print(f"\n[green]Graph saved → {path}[/]")
        stats = graph.stats()
        console.print(f"[dim]{stats['nodes']} nodes, {stats['edges']} edges[/dim]")
    else:
        run(args[0])
