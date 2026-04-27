<p align="center">
  <img src="assets/logo.svg" alt="Lobster" width="380"/>
</p>

<p align="center">
  <b>Heterogeneous data fusion for developer ecosystem intelligence</b><br/>
  Inspired by how Palantir works — built for learning.
</p>

---

## What is Lobster?

Lobster fuses data from four unrelated sources — GitHub, PyPI, Stack Overflow, and HackerNews — into a unified ontology graph, then analyzes it to answer one question:

> **Is this library healthy, growing, or dying?**

No single source can answer that reliably. Downloads can be high on an abandoned library. Stars can be high on one nobody uses. Lobster fuses all signals and scores them together.

---

## Graph

<p align="center">
  <img src="https://github.com/user-attachments/assets/3884ccab-f43f-4876-8e69-c0323ac09016" alt="Lobster relationship graph" width="100%"/>
</p>

Each run builds a live relationship graph across libraries and their maintainers, questions, and mentions. **Gold nodes** are developers shared across multiple libraries — the real interdependency signal.

| Node | Meaning |
|---|---|
| 🔵 Blue circle | Library |
| 🟢 Green circle | Developer / Maintainer |
| 🟡 Gold circle ★ | Shared developer (maintains multiple libraries) |
| 🟠 Orange square | Stack Overflow question |
| 🔴 Red triangle | HackerNews mention |

---

## How it works

```
PyPI ──────────┐
GitHub ────────┤  ingestion  →  ontology graph  →  analysis  →  report
Stack Overflow ┤             (common object model)
HackerNews ────┘
```

1. **Ingestion** — each source has an isolated module that fetches and translates raw API data
2. **Ontology** — raw data is lifted into typed objects (`Library`, `Developer`, `SOQuestion`, `HNPost`) connected by typed edges
3. **Identity resolution** — given just a package name, Lobster figures out which GitHub repo it maps to (via PyPI metadata → GitHub search → fallback), with a confidence score
4. **Analysis** — health scoring, decay detection, and cross-library comparison run on the graph, not on individual sources
5. **Visualization** — interactive HTML graph rendered with pyvis

---

## Concepts from Palantir

| Palantir | Lobster |
|---|---|
| Data connectors | `lobster/ingestion/` |
| Ontology layer | `lobster/ontology/models.py` + `graph.py` |
| Identity resolution | `lobster/ontology/resolver.py` |
| Link analysis | shared developer nodes |
| Temporal analysis | decay detection via snapshots |

---

## Setup

```bash
git clone <repo>
cd Lobster
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export GITHUB_TOKEN=your_token_here   # github.com/settings/tokens — no scopes needed
```

---

## Usage

**Analyze a single library**
```bash
python main.py fastapi
```

**Compare multiple libraries (ranked table)**
```bash
python main.py compare fastapi flask django
```

**Interactive relationship graph**
```bash
python main.py graph fastapi httpx starlette
```
Opens `lobster_graph.html` in your browser. Drag, zoom, hover for details.

---

## Example output

```
Resolved: pypi=scikit-learn  github=scikit-learn/scikit-learn  confidence=95% (pypi_url)

────────────── Lobster — scikit-learn ──────────────
  Health Score       60.0/100
  GitHub Stars       65,931
  Weekly Downloads   0
  Last Commit        1d ago
  Open Issues        2,048
  SO Questions       10
  SO Answer Rate     70%
  HN Mentions        10

Signals:
  • High GitHub stars (65,931)
  • Recently committed (1d ago)
  • High open issue count (2,048)
```

---

## Project structure

```
lobster/
├── ingestion/       # one file per data source
│   ├── github.py
│   ├── pypi.py
│   ├── stackoverflow.py
│   └── hackernews.py
├── ontology/        # common object model + graph
│   ├── models.py
│   ├── graph.py
│   └── resolver.py  # identity resolution
├── storage/         # sqlite persistence + snapshots
│   └── db.py
└── analysis/        # health scoring, decay, comparison, visualization
    ├── health.py
    ├── decay.py
    ├── compare.py
    └── visualize.py
```

---

## Supported packages

Any PyPI package. Lobster resolves GitHub identity automatically. No configuration needed.

Identity resolution confidence:
- **95%** — GitHub URL found directly in PyPI metadata
- **70%** — matched via GitHub repository search
- **40%** — name assumed identical across sources (low confidence, flagged)

Resolved identities are cached locally so repeat runs skip API calls.

---

*Built as a learning exercise in heterogeneous data fusion. Not affiliated with Palantir.*
