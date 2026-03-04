"""
Vercel serverless function — handles GitHub webhook events.
Responds with a dad joke when @dadjoke is mentioned in a comment.
"""

import hashlib
import hmac
import json
import os
import urllib.request
import urllib.error


# ── Configuration ────────────────────────────────────────────────────────────
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TRIGGER = "@dadjoke"
DADJOKE_API = "https://icanhazdadjoke.com/"


# ── Helpers ──────────────────────────────────────────────────────────────────

def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the webhook payload was sent by GitHub."""
    if not GITHUB_WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    mac = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature_header)


def fetch_dad_joke() -> str:
    """Fetch a random dad joke (stdlib only — no requests needed)."""
    try:
        req = urllib.request.Request(
            DADJOKE_API,
            headers={
                "Accept": "application/json",
                "User-Agent": "DadJoke-GitHub-App",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data["joke"]
    except Exception:
        return "I wanted to tell you a dad joke… but it ran away. Try again later!"


def post_comment(repo: str, issue_number: int, body: str) -> bool:
    """Post a comment on a GitHub issue or PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    payload = json.dumps({"body": body}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 201
    except Exception:
        return False


# ── Vercel serverless handler ────────────────────────────────────────────────

def handler(request):
    """Entry point for Vercel serverless function."""
    from http.server import BaseHTTPRequestHandler

    # Health check
    if request.method == "GET":
        return _response(200, {"status": "ok", "app": "DadJoke Bot"})

    if request.method != "POST":
        return _response(405, {"error": "Method not allowed"})

    # Read body
    body = request.body

    # Verify signature
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body, sig):
        return _response(403, {"error": "Invalid signature"})

    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "")

    # Only handle comment events
    if event not in ("issue_comment", "pull_request_review_comment"):
        return _response(200, {"message": f"Ignored event: {event}"})

    if payload.get("action") != "created":
        return _response(200, {"message": "Ignored action"})

    comment_body = payload.get("comment", {}).get("body", "")
    if TRIGGER.lower() not in comment_body.lower():
        return _response(200, {"message": "No trigger found"})

    # Skip bot comments to avoid loops
    comment_user = payload.get("comment", {}).get("user", {}).get("login", "")
    if comment_user.endswith("[bot]"):
        return _response(200, {"message": "Ignoring bot comment"})

    # Get repo + issue number
    repo = payload.get("repository", {}).get("full_name", "")
    if event == "issue_comment":
        issue_number = payload.get("issue", {}).get("number")
    else:
        issue_number = payload.get("pull_request", {}).get("number")

    if not repo or not issue_number:
        return _response(400, {"error": "Missing repo or issue info"})

    # Fetch joke and post
    joke = fetch_dad_joke()
    reply = f"\U0001f604 **Dad Joke incoming!**\n\n> {joke}\n\n*— brought to you by DadJoke Bot* \U0001f916"

    if post_comment(repo, issue_number, reply):
        return _response(200, {"message": "Joke posted!"})
    else:
        return _response(500, {"error": "Failed to post comment"})


class _response:
    """Minimal response object for Vercel Python runtime."""
    def __init__(self, status_code, body_dict):
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}
        self.body = json.dumps(body_dict)
