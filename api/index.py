"""
DadJoke GitHub App — Vercel Serverless Function.
Responds to @dadjoke mentions in issue/PR comments with a random dad joke.

Uses BaseHTTPRequestHandler — Vercel's native Python handler format.
No external dependencies required.
"""

import hashlib
import hmac
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler

# ── Configuration ────────────────────────────────────────────────────────────
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TRIGGER = "@dadjoke"
DADJOKE_API = "https://icanhazdadjoke.com/"


# ── Helpers ──────────────────────────────────────────────────────────────────

def verify_signature(payload_body: bytes, signature_header: str) -> bool:
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
        return "I wanted to tell you a dad joke... but it ran away. Try again later!"


def post_comment(repo: str, issue_number: int, body: str) -> bool:
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


def send_json(handler, status: int, data: dict):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode("utf-8"))


# ── Vercel Handler ───────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        send_json(self, 200, {"status": "ok", "app": "DadJoke Bot"})

    def do_POST(self):
        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Verify signature
        sig = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(body, sig):
            send_json(self, 403, {"error": "Invalid signature"})
            return

        payload = json.loads(body)
        event = self.headers.get("X-GitHub-Event", "")

        # Only handle comment events
        if event not in ("issue_comment", "pull_request_review_comment"):
            send_json(self, 200, {"message": f"Ignored event: {event}"})
            return

        # Only newly created comments
        if payload.get("action") != "created":
            send_json(self, 200, {"message": "Ignored action"})
            return

        comment_body = payload.get("comment", {}).get("body", "")

        # Check for trigger
        if TRIGGER.lower() not in comment_body.lower():
            send_json(self, 200, {"message": "No trigger found"})
            return

        # Skip bot comments to avoid loops
        comment_user = payload.get("comment", {}).get("user", {}).get("login", "")
        if comment_user.endswith("[bot]"):
            send_json(self, 200, {"message": "Ignoring bot comment"})
            return

        # Get repo and issue/PR number
        repo = payload.get("repository", {}).get("full_name", "")
        if event == "issue_comment":
            issue_number = payload.get("issue", {}).get("number")
        else:
            issue_number = payload.get("pull_request", {}).get("number")

        if not repo or not issue_number:
            send_json(self, 400, {"error": "Missing repo or issue info"})
            return

        # Fetch joke and post it
        joke = fetch_dad_joke()
        reply = (
            "\U0001f604 **Dad Joke incoming!**\n\n"
            f"> {joke}\n\n"
            "*\u2014 brought to you by DadJoke Bot* \U0001f916"
        )

        if post_comment(repo, issue_number, reply):
            send_json(self, 200, {"message": "Joke posted!"})
        else:
            send_json(self, 500, {"error": "Failed to post comment"})
