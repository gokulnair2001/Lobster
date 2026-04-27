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
from lobster.analysis.health import compute_health, HealthReport
from lobster.analysis.decay import persist_snapshot

console = Console()


def _score_color(score: float) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"


def _analyze_one(package: str) -> HealthReport | None:
    identity = resolve(package)
    confidence_color = "green" if identity.confidence >= 0.9 else "yellow" if identity.confidence >= 0.6 else "red"
    console.print(
        f"  [{confidence_color}]{identity.resolution_method}[/] "
        f"{identity.github_owner}/{identity.github_repo} "
        f"({identity.confidence:.0%})"
    )

    try:
        graph = OntologyGraph()
        lib, developers, edges = build_library_from_github(
            identity.github_owner, identity.github_repo, identity.pypi_name
        )
        lib = enrich_library_from_pypi(lib)
        so_questions, so_edges = build_so_nodes(lib.id, identity.so_tag)
        hn_posts, hn_edges = build_hn_nodes(lib.id, identity.hn_query)

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
        persist_snapshot(report)
        return report
    except Exception as ex:
        console.print(f"  [red]Failed: {ex}[/]")
        return None


def run_compare(packages: list[str]):
    init_db()
    reports: list[HealthReport] = []

    console.rule("[bold cyan]Lobster — Resolving identities")
    for pkg in packages:
        console.print(f"[cyan]{pkg}[/]")
        report = _analyze_one(pkg)
        if report:
            reports.append(report)

    if not reports:
        console.print("[red]No results.[/]")
        return

    reports.sort(key=lambda r: r.score, reverse=True)

    console.rule("[bold green]Lobster — Comparison")
    table = Table(box=box.SIMPLE)
    table.add_column("Rank", style="dim", justify="right")
    table.add_column("Library", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Stars", justify="right")
    table.add_column("Downloads/wk", justify="right")
    table.add_column("Last Commit", justify="right")
    table.add_column("Open Issues", justify="right")
    table.add_column("SO Rate", justify="right")
    table.add_column("HN", justify="right")

    for i, r in enumerate(reports, 1):
        color = _score_color(r.score)
        table.add_row(
            str(i),
            r.library,
            f"[{color}]{r.score}[/]",
            f"{r.stars:,}",
            f"{r.weekly_downloads:,}",
            f"{r.last_commit_days_ago}d ago" if r.last_commit_days_ago else "?",
            str(r.open_issues),
            f"{r.so_answer_rate:.0%}",
            str(r.hn_mentions),
        )

    console.print(table)
