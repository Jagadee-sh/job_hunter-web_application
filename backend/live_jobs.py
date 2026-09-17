from __future__ import annotations

import ssl
from urllib.parse import urlencode, urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx
import truststore


TLS_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class LiveJobSourceError(RuntimeError):
    pass


def _matches(title: str, description: str, location: str, roles: list[str], locations: list[str]) -> bool:
    searchable = f"{title} {description}".casefold()
    role_terms = [role.casefold() for role in roles if role.strip()]
    location_terms = [item.casefold() for item in locations if item.strip()]
    return (not role_terms or any(term in searchable for term in role_terms)) and (
        not location_terms or any(term in location.casefold() for term in location_terms)
    )


def _job(url: str, title: str, company: str, location: str, description: str, source: str) -> dict[str, object]:
    return {
        "id": uuid5(NAMESPACE_URL, url),
        "title": title,
        "company": company,
        "location": location or "Location not listed",
        "salary": None,
        "description": description,
        "application_url": url,
        "source": source,
    }


async def _get_json(client: httpx.AsyncClient, url: str) -> object:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


async def search_arbeitnow(roles: list[str], locations: list[str], limit: int = 30) -> list[dict[str, object]]:
    """Fetch current public listings and keep only role/location matches."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=TLS_CONTEXT) as client:
            payload = await _get_json(client, "https://www.arbeitnow.com/api/job-board-api")
    except (httpx.HTTPError, ValueError) as error:
        raise LiveJobSourceError(f"Live job source is unavailable: {error}") from error

    results: list[dict[str, object]] = []
    for item in payload.get("data", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "Untitled role"))
        description = str(item.get("description", ""))
        location = str(item.get("location", ""))
        if url and _matches(title, description, location, roles, locations):
            results.append(_job(url, title, str(item.get("company_name", "Unknown company")), location, description, "arbeitnow"))
        if len(results) >= limit:
            break
    return results


async def search_jobicy(roles: list[str], locations: list[str], limit: int = 30) -> list[dict[str, object]]:
    """Fetch live remote roles from Jobicy's public, no-login API."""
    results: list[dict[str, object]] = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=TLS_CONTEXT) as client:
            for role in roles or [""]:
                params = urlencode({"count": min(max(limit * 4, 50), 200), "tag": role}) if role else urlencode({"count": min(max(limit * 4, 50), 200)})
                payload = await _get_json(client, f"https://jobicy.com/api/v2/remote-jobs?{params}")
                for item in payload.get("jobs", []) if isinstance(payload, dict) else []:
                    if not isinstance(item, dict):
                        continue
                    url = str(item.get("url", "")).strip()
                    title = str(item.get("jobTitle", "Untitled role"))
                    description = str(item.get("jobDescription", ""))
                    geo = str(item.get("jobGeo", "Anywhere"))
                    location = f"Remote - {geo}"
                    if url and _matches(title, description, location, roles, locations):
                        results.append(_job(url, title, str(item.get("companyName", "Unknown company")), location, description, "jobicy"))
                    if len(results) >= limit:
                        return results
    except (httpx.HTTPError, ValueError) as error:
        raise LiveJobSourceError(f"Jobicy is unavailable: {error}") from error

    unique = {str(job["application_url"]): job for job in results}
    return list(unique.values())[:limit]


async def search_ats_boards(board_urls: list[str], roles: list[str], locations: list[str], limit: int = 30) -> list[dict[str, object]]:
    """Read public Greenhouse, Lever, and Ashby boards supplied by the user."""
    results: list[dict[str, object]] = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=TLS_CONTEXT) as client:
            for board_url in board_urls:
                parsed = urlparse(board_url.strip())
                parts = [part for part in parsed.path.split("/") if part]
                host = parsed.netloc.casefold()
                if not parts:
                    continue
                token = parts[0]
                if "greenhouse.io" in host:
                    payload = await _get_json(client, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
                    items = payload.get("jobs", []) if isinstance(payload, dict) else []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        url = str(item.get("absolute_url", ""))
                        location = str((item.get("location") or {}).get("name", ""))
                        title = str(item.get("title", "Untitled role"))
                        description = str(item.get("content", ""))
                        if url and _matches(title, description, location, roles, locations):
                            results.append(_job(url, title, token, location, description, "greenhouse"))
                elif "lever.co" in host:
                    payload = await _get_json(client, f"https://api.lever.co/v0/postings/{token}?mode=json")
                    for item in payload if isinstance(payload, list) else []:
                        if not isinstance(item, dict):
                            continue
                        url = str(item.get("hostedUrl", ""))
                        categories = item.get("categories") or {}
                        location = str(categories.get("location", "")) if isinstance(categories, dict) else ""
                        title = str(item.get("text", "Untitled role"))
                        description = str(item.get("descriptionPlain", item.get("description", "")))
                        if url and _matches(title, description, location, roles, locations):
                            results.append(_job(url, title, token, location, description, "lever"))
                elif "ashbyhq.com" in host:
                    payload = await _get_json(client, f"https://api.ashbyhq.com/posting-api/job-board/{token}")
                    items = payload.get("jobs", []) if isinstance(payload, dict) else []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        url = str(item.get("jobUrl", item.get("applyUrl", "")))
                        location = str(item.get("location", ""))
                        title = str(item.get("title", "Untitled role"))
                        description = str(item.get("descriptionPlain", item.get("description", "")))
                        if url and _matches(title, description, location, roles, locations):
                            results.append(_job(url, title, token, location, description, "ashby"))
                if len(results) >= limit:
                    break
    except (httpx.HTTPError, ValueError) as error:
        raise LiveJobSourceError(f"An ATS board could not be reached: {error}") from error
    return results[:limit]
