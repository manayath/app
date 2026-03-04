"""
DadJoke GitHub App — responds to @dadjoke mentions in issue/PR comments
with a random dad joke from icanhazdadjoke.com
"""

import hashlib
import hmac
import os
import logging

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TRIGGER = "@dadjoke"
DADJOKE_API = "https://icanhazdadjoke.com/"


# ── Helpers ──────────────────────────────────────────────────────────────────

def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the webhook payload was sent by GitHub using the secret."""
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning("No webhook secret configured — skipping verification")
        return True

    if not signature_header:
        return False

    hash_object = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


def fetch_dad_joke() -> str:
    """Fetch a random dad joke from icanhazdadjoke.com."""
    try:
        resp = requests.get(
            DADJOKE_API,
            headers={
                "Accept": "application/json",
                "User-Agent": "DadJoke-GitHub-App (https://github.com)",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["joke"]
    except requests.RequestException as exc:
        logger.error("Failed to fetch dad joke: %s", exc)
        return "I wanted to tell you a dad joke… but it ran away. Try again later!"


def post_comment(repo_full_name: str, issue_number: int, body: str) -> bool:
    """Post a comment on a GitHub issue or pull request."""
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{issue_number}/comments"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"body": body},
        timeout=10,
    )
    if resp.status_code == 201:
        logger.info("Posted joke on %s#%s", repo_full_name, issue_number)
        return True
    else:
        logger.error("GitHub API error %s: %s", resp.status_code, resp.text)
        return False


# ── Webhook endpoint ─────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    # 1. Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 403

    event = request.headers.get("X-GitHub-Event", "")
    payload = request.json

    # 2. Only handle issue_comment and pull_request_review_comment events
    if event not in ("issue_comment", "pull_request_review_comment"):
        return jsonify({"message": f"Ignored event: {event}"}), 200

    # 3. Only handle newly created comments (not edits or deletions)
    if payload.get("action") != "created":
        return jsonify({"message": "Ignored action"}), 200

    comment_body = payload.get("comment", {}).get("body", "")

    # 4. Check if the trigger is mentioned
    if TRIGGER.lower() not in comment_body.lower():
        return jsonify({"message": "No trigger found"}), 200

    # 5. Don't respond to our own comments (avoid infinite loops)
    comment_user = payload.get("comment", {}).get("user", {}).get("login", "")
    if comment_user.endswith("[bot]"):
        return jsonify({"message": "Ignoring bot comment"}), 200

    # 6. Determine the repo and issue/PR number
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    if event == "issue_comment":
        issue_number = payload.get("issue", {}).get("number")
    else:
        issue_number = payload.get("pull_request", {}).get("number")

    if not repo_full_name or not issue_number:
        return jsonify({"error": "Missing repo or issue info"}), 400

    # 7. Fetch a joke and post it
    joke = fetch_dad_joke()
    reply = f"😄 **Dad Joke incoming!**\n\n> {joke}\n\n*— brought to you by DadJoke Bot* 🤖"

    if post_comment(repo_full_name, issue_number, reply):
        return jsonify({"message": "Joke posted!"}), 200
    else:
        return jsonify({"error": "Failed to post comment"}), 500


# ── Health check ─────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "app": "DadJoke Bot 🤡"})


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)
