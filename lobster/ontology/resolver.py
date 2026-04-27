import re
import json
import httpx
from dataclasses import dataclass, asdict
from typing import Optional

from lobster.storage.db import save_raw, get_conn
from lobster.config import github_headers

GITHUB_API = "https://api.github.com"
PYPI_API = "https://pypi.org/pypi"

GITHUB_URL_RE = re.compile(r"https?://github\.com/([^/]+)/([^/\s#]+)")


@dataclass
class ResolvedIdentity:
    pypi_name: str
    github_owner: Optional[str]
    github_repo: Optional[str]
    so_tag: str
    hn_query: str
    confidence: float
    resolution_method: str  # "pypi_url" | "github_search" | "assumed"


def _extract_github_from_pypi(pypi_name: str) -> Optional[tuple[str, str]]:
    """Parse GitHub owner/repo from PyPI project_urls metadata."""
    url = f"{PYPI_API}/{pypi_name}/json"
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        r = client.get(url)
        if r.status_code != 200:
            return None
        data = r.json()

    save_raw("pypi_resolve", pypi_name, data)

    info = data.get("info", {})
    candidates = []

    # project_urls is a dict like {"Source": "https://github.com/..."}
    for value in (info.get("project_urls") or {}).values():
        m = GITHUB_URL_RE.search(value)
        if m:
            candidates.append((m.group(1), m.group(2).rstrip(".git")))

    # also check home_page and bugtrack_url
    for field in ["home_page", "bugtrack_url", "download_url"]:
        val = info.get(field) or ""
        m = GITHUB_URL_RE.search(val)
        if m:
            candidates.append((m.group(1), m.group(2).rstrip(".git")))

    return candidates[0] if candidates else None


def _search_github(query: str) -> Optional[tuple[str, str]]:
    """Search GitHub repositories and return the top match."""
    url = f"{GITHUB_API}/search/repositories"
    with httpx.Client(headers=github_headers(), timeout=10, follow_redirects=True) as client:
        r = client.get(url, params={"q": query, "sort": "stars", "per_page": 1})
        if r.status_code != 200:
            return None
        data = r.json()

    save_raw("github_search", query, data)
    items = data.get("items", [])
    if not items:
        return None

    top = items[0]
    return top["owner"]["login"], top["name"]


def _verify_repo(owner: str, repo: str) -> bool:
    """Check that a GitHub repo actually exists."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    with httpx.Client(headers=github_headers(), timeout=10, follow_redirects=True) as client:
        r = client.get(url)
        return r.status_code == 200


def _cache_get(package_name: str) -> Optional["ResolvedIdentity"]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data FROM nodes WHERE id = ?", (f"identity:{package_name}",)
        ).fetchone()
    if row is None:
        return None
    d = json.loads(row["data"])
    return ResolvedIdentity(**d)


def _cache_set(identity: "ResolvedIdentity"):
    from lobster.storage.db import upsert_node
    upsert_node(f"identity:{identity.pypi_name}", "Identity", asdict(identity))


def resolve(package_name: str) -> ResolvedIdentity:
    """
    Resolve a package name to its canonical identities across sources.
    Tries three strategies in order of confidence.
    Uses a local cache so repeat runs skip GitHub API calls.
    """
    cached = _cache_get(package_name)
    if cached:
        return cached

    github_owner = None
    github_repo = None
    confidence = 0.0
    method = "assumed"

    # Level 1: extract GitHub URL from PyPI metadata
    result = _extract_github_from_pypi(package_name)
    if result:
        owner, repo = result
        if _verify_repo(owner, repo):
            github_owner, github_repo = owner, repo
            confidence = 0.95
            method = "pypi_url"

    # Level 2: GitHub search fallback
    if not github_owner:
        result = _search_github(package_name)
        if result:
            owner, repo = result
            if _verify_repo(owner, repo):
                github_owner, github_repo = owner, repo
                confidence = 0.70
                method = "github_search"

    # Level 3: assume name matches
    if not github_owner:
        github_owner = package_name
        github_repo = package_name
        confidence = 0.40
        method = "assumed"

    identity = ResolvedIdentity(
        pypi_name=package_name,
        github_owner=github_owner,
        github_repo=github_repo,
        so_tag=package_name,
        hn_query=package_name,
        confidence=confidence,
        resolution_method=method,
    )
    if confidence >= 0.5:
        _cache_set(identity)
    return identity
