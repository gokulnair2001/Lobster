from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class NodeType(str, Enum):
    LIBRARY = "Library"
    DEVELOPER = "Developer"
    COMPANY = "Company"
    ISSUE = "Issue"
    HN_POST = "HNPost"
    SO_QUESTION = "SOQuestion"


class EdgeType(str, Enum):
    HAS_MAINTAINER = "has_maintainer"
    HAS_ISSUE = "has_issue"
    MENTIONED_IN = "mentioned_in"
    HAS_QUESTION = "has_question"
    WORKS_AT = "works_at"


@dataclass
class Library:
    id: str                          # canonical: "pypi:{name}"
    name: str
    github_repo: Optional[str] = None
    pypi_name: Optional[str] = None
    stars: int = 0
    open_issues: int = 0
    last_commit_days_ago: Optional[int] = None
    weekly_downloads: int = 0
    latest_version: Optional[str] = None
    sources: list[str] = field(default_factory=list)


@dataclass
class Developer:
    id: str                          # canonical: "github:{login}"
    login: str
    name: Optional[str] = None
    company: Optional[str] = None
    sources: list[str] = field(default_factory=list)


@dataclass
class SOQuestion:
    id: str                          # canonical: "so:{question_id}"
    title: str
    score: int = 0
    answer_count: int = 0
    is_answered: bool = False
    created_at: Optional[str] = None


@dataclass
class HNPost:
    id: str                          # canonical: "hn:{object_id}"
    title: str
    points: int = 0
    comments: int = 0
    created_at: Optional[str] = None


@dataclass
class Edge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)
