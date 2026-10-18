"""Archive exact D1 payloads, verify published bytes, then acknowledge deletion.

Uses only the Python standard library. Secrets stay in environment variables;
installation hashes are used for acknowledgement only and never committed.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, token, *, method="GET", data=None, raw=False):
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "FlyTeam-training-archive",
               "Accept": "application/vnd.github.raw+json" if raw else "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    req = Request(url, headers=headers, data=body, method=method)
    with build_opener(NoRedirect).open(req, timeout=60) as response:
        content = response.read(12_000_001)
    if len(content) > 12_000_000:
        raise ValueError("Archive response exceeds size limit")
    return content if raw else json.loads(content)


def validate_record(row):
    raw = row["payload"].encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw)
    session = payload["session"]
    if not re.fullmatch(r"[a-f0-9]{64}", row["participant_hash"]):
        raise ValueError("Invalid archive identity")
    if not re.fullmatch(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}", row["session_id"]):
        raise ValueError("Invalid archive session ID")
    if type(row["revision"]) is not int or row["revision"] < 1:
        raise ValueError("Invalid archive revision")
    if row["mode"] not in ("examples", "feedback") or row["status"] not in ("gewonnen", "verloren", "aborted"):
        raise ValueError("Only completed learning sessions may be archived")
    if (payload.get("format") != "flyteam-learning-session" or payload.get("version") != 1
            or session["id"] != row["session_id"] or session["data_revision"] != row["revision"]
            or session["mode"] != row["mode"] or session["status"] != row["status"]
            or len(session["events"]) != row["event_count"] or not session.get("consent")
            or payload["received_at"] != row["received_at"] or digest != row["sha256"]):
        raise ValueError("Archive metadata or checksum mismatch")
    received = datetime.fromisoformat(row["received_at"].replace("Z", "+00:00"))
    if received.tzinfo is None:
        raise ValueError("Archive timestamp must include a timezone")
    day = received.astimezone(timezone.utc).date().isoformat()
    path = f"ai/data/archives/{day}/{row['mode']}/{row['session_id']}/r{row['revision']}-{digest}.json"
    return path, raw


class GitHubArchive:
    def __init__(self, repository, token, branch="main"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub repository")
        self.base = f"https://api.github.com/repos/{repository}"
        self.token, self.branch = token, branch

    def api(self, path, **kwargs):
        return request(self.base + path, self.token, **kwargs)

    def read(self, path, ref):
        return self.api(f"/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}", raw=True)

    def publish_and_verify(self, files, *, message=None):
        for attempt in range(3):
            head = self.api(f"/git/ref/heads/{quote(self.branch, safe='')}")["object"]["sha"]
            additions = []
            for path, raw in files.items():
                try:
                    existing = self.read(path, head)
                except HTTPError as exc:
                    if exc.code != 404:
                        raise
                    blob = self.api("/git/blobs", method="POST", data={
                        "content": base64.b64encode(raw).decode(), "encoding": "base64"})
                    additions.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
                else:
                    if existing != raw:
                        raise ValueError("Existing GitHub archive differs from source")
            commit = head
            if additions:
                base_tree = self.api(f"/git/commits/{head}")["tree"]["sha"]
                tree = self.api("/git/trees", method="POST", data={"base_tree": base_tree, "tree": additions})
                commit = self.api("/git/commits", method="POST", data={
                    "message": message or f"Archive {len(additions)} completed training sessions",
                    "tree": tree["sha"], "parents": [head]})["sha"]
                try:
                    self.api(f"/git/refs/heads/{quote(self.branch, safe='')}", method="PATCH",
                             data={"sha": commit, "force": False})
                except HTTPError as exc:
                    if exc.code in (409, 422) and attempt < 2:
                        continue  # A concurrent commit won; rebuild on its new head.
                    raise
            # Resolve through the branch after publishing. An orphan commit is not a backup.
            published_head = self.api(f"/git/ref/heads/{quote(self.branch, safe='')}")["object"]["sha"]
            for path, raw in files.items():
                downloaded = self.read(path, published_head)
                if downloaded != raw or hashlib.sha256(downloaded).digest() != hashlib.sha256(raw).digest():
                    raise ValueError("Published GitHub archive failed byte verification")
            return published_head
        raise RuntimeError("Could not publish archive after concurrent GitHub updates")

    def keep_schedule_active(self):
        # Public repositories disable scheduled workflows after 60 inactive days.
        # One deterministic file per month avoids that, including months without games.
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        path = f".github/archive-keepalive/{month}.txt"
        self.publish_and_verify({path: f"Training archive scheduler active for {month}.\n".encode()},
                                message=f"Keep daily training archive active for {month}")


def archive_batches(github, cloud, *, max_batches=100, output=print):
    total = 0
    for _ in range(max_batches):
        records = cloud("export", {})["records"]
        if not records:
            output(f"Finished: {total} sessions verified on GitHub; no eligible sessions remain.")
            return total
        if not 1 <= len(records) <= 5:
            raise ValueError("Unexpected export batch size")
        files = dict(validate_record(row) for row in records)
        commit = github.publish_and_verify(files)
        # This call is deliberately after publication AND remote byte verification.
        acknowledgement = [{key: row[key] for key in ("participant_hash", "session_id", "revision", "sha256")}
                           for row in records]
        results = cloud("ack", {"records": acknowledgement})["results"]
        if (len(results) != len(records) or any(
                result.get("session_id") != row["session_id"] or result.get("revision") != row["revision"]
                or result.get("status") not in ("deleted", "changed", "missing")
                for result, row in zip(results, records))):
            raise ValueError("Unexpected deletion acknowledgement; backups are already on GitHub")
        total += len(records)
        deleted = sum(result["status"] == "deleted" for result in results)
        output(f"Verified {len(records)} sessions in {commit}; deleted {deleted} unchanged Cloudflare copies.")
    raise RuntimeError("Daily batch limit reached; remaining data stays in Cloudflare for the next run")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-batches", type=int, default=100)
    args = parser.parse_args()
    if args.max_batches < 1:
        parser.error("--max-batches must be positive")
    base = os.environ["CLOUDFLARE_ARCHIVE_URL"].rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("Archive endpoint must use HTTPS")
    archive_token = os.environ["CLOUDFLARE_ARCHIVE_TOKEN"]
    github = GitHubArchive(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    def cloud(operation, body):
        return request(f"{base}/archive/{operation}", archive_token, method="POST", data=body)
    archive_batches(github, cloud, max_batches=args.max_batches)
    github.keep_schedule_active()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Archive stopped safely: {exc}", file=sys.stderr)
        sys.exit(1)
