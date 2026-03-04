"""
DadJoke GitHub App — Vercel serverless function (Flask WSGI).
Responds to @dadjoke mentions in issue/PR comments with a random dad joke.
"""

import hashlib
import hmac
import json
import os
import urllib.request
import urllib.error

from flask import Flask, request, jsonify

app = Flask(__name__)

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
    """Fetch a random dad joke from icanhazdadjoke.com."""
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


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "app": "DadJoke Bot"})


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return jsonify({"status": "ok", "message": "Webhook endpoint ready"})

    # 1. Verify signature
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, sig):
        return jsonify({"error": "Invalid signature"}), 403

    payload = request.json
    event = request.headers.get("X-GitHub-Event", "")

    # 2. Only handle comment events
    if event not in ("issue_comment", "pull_request_review_comment"):
        return jsonify({"message": f"Ignored event: {event}"}), 200

    # 3. Only newly created comments
    if payload.get("action") != "created":
        return jsonify({"message": "Ignored action"}), 200

    comment_body = payload.get("comment", {}).get("body", "")

    # 4. Check for trigger
    if TRIGGER.lower() not in comment_body.lower():
        return jsonify({"message": "No trigger found"}), 200

    # 5. Skip bot comments to avoid infinite loops
    comment_user = payload.get("comment", {}).get("user", {}).get("login", "")
    if comment_user.endswith("[bot]"):
        return jsonify({"message": "Ignoring bot comment"}), 200

    # 6. Get repo and issue/PR number
    repo = payload.get("repository", {}).get("full_name", "")
    if event == "issue_comment":
        issue_number = payload.get("issue", {}).get("number")
    else:
        issue_number = payload.get("pull_request", {}).get("number")

    if not repo or not issue_number:
        return jsonify({"error": "Missing repo or issue info"}), 400

    # 7. Fetch joke and post it
    joke = fetch_dad_joke()
    reply = (
        "\U0001f604 **Dad Joke incoming!**\n\n"
        f"> {joke}\n\n"
        "*— brought to you by DadJoke Bot* \U0001f916"
    )

    if post_comment(repo, issue_number, reply):
        return jsonify({"message": "Joke posted!"}), 200
    else:
        return jsonify({"error": "Failed to post comment"}), 500
