from dataclasses import dataclass
from lobster.ontology.graph import OntologyGraph
from lobster.ontology.models import NodeType


@dataclass
class HealthReport:
    library: str
    score: float                  # 0–100
    stars: int
    weekly_downloads: int
    last_commit_days_ago: int | None
    open_issues: int
    so_questions: int
    so_answer_rate: float         # 0–1
    hn_mentions: int
    signals: list[str]            # human-readable signals


def compute_health(graph: OntologyGraph, library_id: str) -> HealthReport:
    node = graph.get_node(library_id)
    if node is None:
        raise ValueError(f"Library {library_id} not in graph")

    lib = node["data"]
    signals = []
    score = 50.0

    # GitHub signals
    if lib.stars > 10_000:
        score += 10
        signals.append(f"High GitHub stars ({lib.stars:,})")
    elif lib.stars < 100:
        score -= 10
        signals.append(f"Low GitHub stars ({lib.stars:,})")

    if lib.last_commit_days_ago is not None:
        if lib.last_commit_days_ago <= 30:
            score += 10
            signals.append(f"Recently committed ({lib.last_commit_days_ago}d ago)")
        elif lib.last_commit_days_ago > 365:
            score -= 20
            signals.append(f"No commit in {lib.last_commit_days_ago}d — likely inactive")

    if lib.open_issues > 500:
        score -= 5
        signals.append(f"High open issue count ({lib.open_issues})")

    # PyPI signals
    if lib.weekly_downloads > 500_000:
        score += 15
        signals.append(f"High weekly downloads ({lib.weekly_downloads:,})")
    elif lib.weekly_downloads < 1_000:
        score -= 10
        signals.append(f"Low weekly downloads ({lib.weekly_downloads:,})")

    # SO signals
    so_nodes = graph.neighbors_of_type(library_id, NodeType.SO_QUESTION)
    so_questions = len(so_nodes)
    answered = sum(
        1 for n in so_nodes
        if graph.get_node(n)["data"].is_answered
    )
    answer_rate = answered / so_questions if so_questions else 0.0

    if answer_rate > 0.7:
        score += 5
        signals.append(f"Good SO answer rate ({answer_rate:.0%})")
    elif answer_rate < 0.3 and so_questions > 3:
        score -= 5
        signals.append(f"Low SO answer rate ({answer_rate:.0%}) — community may be thin")

    # HN signals
    hn_nodes = graph.neighbors_of_type(library_id, NodeType.HN_POST)
    hn_mentions = len(hn_nodes)
    if hn_mentions > 5:
        score += 5
        signals.append(f"Frequently discussed on HN ({hn_mentions} posts)")

    score = max(0.0, min(100.0, score))

    return HealthReport(
        library=lib.name,
        score=round(score, 1),
        stars=lib.stars,
        weekly_downloads=lib.weekly_downloads,
        last_commit_days_ago=lib.last_commit_days_ago,
        open_issues=lib.open_issues,
        so_questions=so_questions,
        so_answer_rate=answer_rate,
        hn_mentions=hn_mentions,
        signals=signals,
    )
