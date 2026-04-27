import httpx
from lobster.storage.db import save_raw
from lobster.ontology.models import HNPost, Edge, EdgeType
from datetime import datetime


HN_SEARCH_API = "https://hn.algolia.com/api/v1/search"


def fetch_mentions(query: str, limit: int = 10) -> list[dict]:
    params = {"query": query, "tags": "story", "hitsPerPage": limit}
    with httpx.Client(timeout=10) as client:
        r = client.get(HN_SEARCH_API, params=params)
        r.raise_for_status()
        data = r.json()
    save_raw("hackernews", query, data)
    return data.get("hits", [])


def build_hn_nodes(library_id: str, query: str) -> tuple[list[HNPost], list[Edge]]:
    raw = fetch_mentions(query)
    posts = []
    edges = []

    for hit in raw:
        post = HNPost(
            id=f"hn:{hit['objectID']}",
            title=hit.get("title") or hit.get("story_title", ""),
            points=hit.get("points") or 0,
            comments=hit.get("num_comments") or 0,
            created_at=hit.get("created_at", ""),
        )
        posts.append(post)
        edges.append(Edge(
            source_id=library_id,
            target_id=post.id,
            edge_type=EdgeType.MENTIONED_IN,
            weight=float(post.points),
        ))

    return posts, edges
