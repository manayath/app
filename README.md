# 🤡 DadJoke Bot — GitHub App

A simple GitHub App that replies with a random dad joke whenever someone mentions `@dadjoke` in an issue or pull request comment.

## How it works

1. You install a webhook on your GitHub repo
2. When someone comments `@dadjoke` on an issue or PR, GitHub sends a webhook event
3. The server fetches a random joke from [icanhazdadjoke.com](https://icanhazdadjoke.com/) and posts it as a reply

---

## Deploy to Vercel (free — recommended)

### 1. Push to GitHub

Create a new repo and push this project:

```bash
cd dadjoke-bot
git init
git add .
git commit -m "Initial commit"
gh repo create dadjoke-bot --public --push --source .
```

### 2. Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in with your GitHub account
2. Click **"Add New → Project"**
3. Import your `dadjoke-bot` repo
4. Under **Environment Variables**, add:
   - `GITHUB_TOKEN` — A [Personal Access Token](https://github.com/settings/tokens) with `repo` scope
   - `GITHUB_WEBHOOK_SECRET` — A secret string (make one up, e.g. `mysecret123`)
5. Click **Deploy**

Your app will be live at `https://dadjoke-bot.vercel.app` (or similar).

### 3. Create a GitHub webhook

Go to your target repo → **Settings → Webhooks → Add webhook**:

| Field            | Value                                                          |
|------------------|----------------------------------------------------------------|
| Payload URL      | `https://dadjoke-bot.vercel.app/webhook`                       |
| Content type     | `application/json`                                             |
| Secret           | Same value as your `GITHUB_WEBHOOK_SECRET`                     |
| Events           | Select **Issue comments** and **Pull request review comments** |

Click **Add webhook**.

### 4. Test it

Open any issue or PR in your repo, post a comment:

```
Hey @dadjoke tell me something funny!
```

The bot will reply with a random dad joke. 🎉

---

## Run locally (alternative)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python app.py           # starts on http://localhost:3000
```

Use [ngrok](https://ngrok.com/) to expose it: `ngrok http 3000`, then use the ngrok URL as your webhook Payload URL.

---

## Project structure

```
dadjoke-bot/
├── api/
│   ├── webhook.py         # Vercel serverless function
│   └── requirements.txt   # Vercel Python deps (none — stdlib only)
├── app.py                 # Standalone Flask app (local dev)
├── vercel.json            # Vercel routing config
├── requirements.txt       # Flask app dependencies
├── .env.example           # Environment variable template
└── README.md
```

## Other free hosting alternatives

- **[Render](https://render.com)** — Free tier for web services (spins down after inactivity)
- **[Railway](https://railway.app)** — Trial tier with $5 free credit
- **[Fly.io](https://fly.io)** — Free allowance for small apps
