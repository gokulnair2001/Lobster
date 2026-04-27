import httpx
from lobster.storage.db import save_raw
from lobster.ontology.models import Library


PYPI_API = "https://pypi.org/pypi"
PYPISTATS_API = "https://pypistats.org/api"


def fetch_pypi_info(package: str) -> dict:
    url = f"{PYPI_API}/{package}/json"
    with httpx.Client(timeout=10) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
    save_raw("pypi", package, data)
    return data


def fetch_weekly_downloads(package: str) -> int:
    url = f"{PYPISTATS_API}/packages/{package}/recent"
    with httpx.Client(timeout=10) as client:
        r = client.get(url)
        if r.status_code != 200:
            return 0
        data = r.json()
    save_raw("pypistats", package, data)
    return data.get("data", {}).get("last_week", 0)


def enrich_library_from_pypi(lib: Library) -> Library:
    """Enrich an existing Library object with PyPI data."""
    if not lib.pypi_name:
        return lib

    info = fetch_pypi_info(lib.pypi_name)
    pkg_info = info.get("info", {})

    lib.latest_version = pkg_info.get("version")
    lib.weekly_downloads = fetch_weekly_downloads(lib.pypi_name)

    if "pypi" not in lib.sources:
        lib.sources.append("pypi")

    return lib
