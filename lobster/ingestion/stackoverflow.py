import httpx
from lobster.storage.db import save_raw
from lobster.ontology.models import SOQuestion, Edge, EdgeType


SO_API = "https://api.stackexchange.com/2.3"


def fetch_questions(tag: str, limit: int = 10) -> list[dict]:
    url = f"{SO_API}/questions"
    params = {
        "tagged": tag,
        "site": "stackoverflow",
        "order": "desc",
        "sort": "activity",
        "pagesize": limit,
        "filter": "!nNPvSNdWme",
    }
    with httpx.Client(timeout=10) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    save_raw("stackoverflow", tag, data)
    return data.get("items", [])


def build_so_nodes(library_id: str, tag: str) -> tuple[list[SOQuestion], list[Edge]]:
    raw = fetch_questions(tag)
    questions = []
    edges = []

    for item in raw:
        q = SOQuestion(
            id=f"so:{item['question_id']}",
            title=item.get("title", ""),
            score=item.get("score", 0),
            answer_count=item.get("answer_count", 0),
            is_answered=item.get("is_answered", False),
            created_at=str(item.get("creation_date", "")),
        )
        questions.append(q)
        edges.append(Edge(
            source_id=library_id,
            target_id=q.id,
            edge_type=EdgeType.HAS_QUESTION,
            weight=float(item.get("score", 1)),
        ))

    return questions, edges
