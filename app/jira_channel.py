import os

import httpx

IMPORT_LABEL = "enklima-imported"


def _client() -> tuple[httpx.Client, str]:
    base = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    key = os.getenv("JIRA_PROJECT_KEY")
    if not all([base, email, token, key]):
        raise RuntimeError("JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN / JIRA_PROJECT_KEY missing from .env")
    return httpx.Client(base_url=base, auth=(email, token), timeout=20), key


def _search(c: httpx.Client, params: dict) -> dict:
    # new cloud sites use /search/jql; older ones still answer /search. Try new, fall back.
    r = c.get("/rest/api/2/search/jql", params=params)
    if r.status_code == 404:
        r = c.get("/rest/api/2/search", params=params)
    r.raise_for_status()
    return r.json()


def fetch_new() -> list[dict]:
    # issues in our project not yet labeled as imported; the label IS the dedupe (like the email read-flag)
    c, key = _client()
    with c:
        jql = f'project = {key} AND (labels IS EMPTY OR labels != "{IMPORT_LABEL}") ORDER BY created ASC'
        data = _search(c, {"jql": jql, "fields": "summary,description,reporter", "maxResults": 50})
        out = []
        for issue in data.get("issues", []):
            f = issue["fields"]
            rep = f.get("reporter") or {}
            out.append(
                {
                    "issue_key": issue["key"],
                    "subject": f.get("summary") or "(no summary)",
                    "body": (f.get("description") or "").strip() or "(no description)",
                    "source": "jira",
                    "name": rep.get("displayName"),
                    "email": rep.get("emailAddress"),
                }
            )
            # stamp the label so the next sync skips it
            c.put(f"/rest/api/2/issue/{issue['key']}", json={"update": {"labels": [{"add": IMPORT_LABEL}]}}).raise_for_status()
        return out


def post_comment(issue_key: str, body: str) -> None:
    c, _ = _client()
    with c:
        c.post(f"/rest/api/2/issue/{issue_key}/comment", json={"body": body}).raise_for_status()


def transition_done(issue_key: str) -> bool:
    # find a transition whose name looks like Done and fire it; False if the workflow has none
    c, _ = _client()
    with c:
        r = c.get(f"/rest/api/2/issue/{issue_key}/transitions")
        r.raise_for_status()
        for t in r.json().get("transitions", []):
            if t["name"].lower() in ("done", "resolve", "resolved", "close", "closed"):
                c.post(f"/rest/api/2/issue/{issue_key}/transitions", json={"transition": {"id": t["id"]}}).raise_for_status()
                return True
        return False
