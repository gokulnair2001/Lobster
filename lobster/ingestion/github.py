import httpx
from datetime import datetime, timezone
from lobster.storage.db import save_raw
from lobster.ontology.models import Library, Developer, Edge, EdgeType
from lobster.config import github_headers

GITHUB_API = "https://api.github.com"


def fetch_repo(owner: str, repo: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    with httpx.Client(headers=github_headers(), timeout=10, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
    save_raw("github", f"{owner}/{repo}", data)
    return data


def fetch_contributors(owner: str, repo: str, limit: int = 10) -> list[dict]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contributors"
    with httpx.Client(headers=github_headers(), timeout=10, follow_redirects=True) as client:
        r = client.get(url, params={"per_page": limit})
        r.raise_for_status()
        data = r.json()
    save_raw("github_contributors", f"{owner}/{repo}", {"contributors": data})
    return data


def fetch_commits(owner: str, repo: str) -> list[dict]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    with httpx.Client(headers=github_headers(), timeout=10, follow_redirects=True) as client:
        r = client.get(url, params={"per_page": 1})
        r.raise_for_status()
        data = r.json()
    save_raw("github_commits", f"{owner}/{repo}", {"commits": data})
    return data


def days_since(iso_date: str) -> int:
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def build_library_from_github(owner: str, repo: str, pypi_name: str) -> tuple[Library, list[Developer], list[Edge]]:
    repo_data = fetch_repo(owner, repo)
    commits = fetch_commits(owner, repo)
    contributors_raw = fetch_contributors(owner, repo)

    last_commit_days = None
    if commits:
        last_commit_days = days_since(commits[0]["commit"]["committer"]["date"])

    lib = Library(
        id=f"pypi:{pypi_name}",
        name=pypi_name,
        github_repo=f"{owner}/{repo}",
        pypi_name=pypi_name,
        stars=repo_data.get("stargazers_count", 0),
        open_issues=repo_data.get("open_issues_count", 0),
        last_commit_days_ago=last_commit_days,
        sources=["github"],
    )

    developers = []
    edges = []
    for c in contributors_raw:
        dev = Developer(
            id=f"github:{c['login']}",
            login=c["login"],
            sources=["github"],
        )
        developers.append(dev)
        edges.append(Edge(
            source_id=lib.id,
            target_id=dev.id,
            edge_type=EdgeType.HAS_MAINTAINER,
            weight=c.get("contributions", 1),
        ))

    return lib, developers, edges
