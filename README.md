# Reddit Pick Alerts

A small, **alert-only** tool. It polls a Reddit user's public comment feed and
sends you a **Telegram** message within about a minute of them posting a new
betting pick.

> It never places bets and never talks to any sportsbook. It only reads a
> public Atom feed and sends Telegram messages.

## What it does

- Polls `https://www.reddit.com/user/<name>/comments.rss` every 60s (configurable).
- Treats a comment as a **pick** only when its text contains **all** the
  trigger keywords (default: `Stake:` **and** `Odds:`), so ordinary chat
  replies are ignored.
- Sends a Telegram alert with: the username, the post time in **IST**, the
  pick line, posted odds, stake in units, the **minimum acceptable odds**
  (parsed from phrases like "only take it at 1.85 or better"), the full body
  (trimmed to ~800 chars), and the comment link.
- Detects **edits**: if an already-alerted comment's text changes, you get one
  short `UPDATED` alert.
- **Dedupes across restarts** with a JSON state file. On first run (and when
  you add a new user later) it records existing comments as seen *without*
  alerting.
- **Health check**: warns you once over Telegram if polling has been failing
  for 15 minutes, then sends a recovery message when it's working again.

## Project layout

```
reddit-pick-alerts/
├── main.py                 # poll loop, health, backoff
├── alerts/
│   ├── config.py           # YAML config + env secrets
│   ├── feed.py             # fetch + parse the RSS feed
│   ├── parse.py            # HTML unescape + odds/stake/min-odds extraction
│   ├── notifier.py         # compose + send the alert
│   ├── telegram.py         # Telegram sendMessage
│   └── state.py            # JSON dedupe/edit state
├── tools/send_test_alert.py  # send a fake alert to verify Telegram
├── tests/test_parse.py       # unit tests
├── config.example.yaml       # copy to config.yaml
├── .env.example              # copy to .env (secrets)
├── requirements.txt
├── Dockerfile
└── deploy/reddit-pick-alerts.service   # systemd unit
```

## 1. Install

Needs Python 3.9+.

```bash
cd reddit-pick-alerts
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Create a Telegram bot and get your chat id

1. In Telegram, message **@BotFather**, send `/newbot`, and follow the prompts.
   It gives you a **bot token** like `123456789:ABCdef...`.
2. Open a chat with your new bot and **send it any message** (e.g. "hi"). A bot
   can't message you until you've talked to it first.
3. Find your **chat id**: message **@userinfobot**, which replies with your
   numeric id. (Alternative: open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser after
   messaging your bot, and read `message.chat.id`.)

## 3. Configure

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

- Edit **config.yaml**: set the `usernames` list (e.g. `Suspicious-Cow-1909`),
  and personalise `user_agent`.
- Edit **.env**: paste your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Secrets live only in `.env` (git-ignored). Nothing sensitive goes in the code
or `config.yaml`.

## 4. Test Telegram

```bash
python -m tools.send_test_alert
```

You should get a sample alert in Telegram within a second or two. If it fails,
re-check the token, that you messaged the bot first, and the chat id.

## 5. Run

```bash
python main.py                 # runs forever
python main.py --once          # one poll cycle, then exit (handy for a first check)
```

The first run baselines existing comments silently; new picks after that
trigger alerts.

## 6. Run the tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Adding another tipster

Add one line under `usernames:` in `config.yaml` and restart. Their existing
comments are baselined (no backfill spam); only new picks alert.

---

## Deploying 24/7

Tips arrive while you're asleep, and a laptop that sleeps will miss them, so run
this on an **always-on** machine.

### Easiest, free, no server to maintain: GitHub Actions (recommended)

GitHub will run the poll for you on a timer — no VM, no card, nothing to keep
alive. A workflow is already included at `.github/workflows/poll.yml`.

**Trade-off to know up front:** GitHub's scheduler usually lags by **5–15
minutes** (sometimes more), so alerts land within roughly that window instead of
~1 minute. For a pick posted while you sleep that's still long before you'd
notice it yourself. If you need ~1-minute latency, use a VM/Pi instead (below).

Steps:

1. **Create a free GitHub account**, then a **new repository** (make it
   **Public** — public repos get unlimited Actions minutes; a private repo would
   burn through the free monthly minutes at this frequency).
2. **Push this project** to that repo:
   ```bash
   cd reddit-pick-alerts
   git init && git add . && git commit -m "Reddit pick alerts"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
   (`.env` is git-ignored, so your secrets never get pushed.)
3. **Add your two secrets** in the repo: **Settings → Secrets and variables →
   Actions → New repository secret**. Add `TELEGRAM_BOT_TOKEN` and
   `TELEGRAM_CHAT_ID`. These stay private even in a public repo.
4. **Edit `config.yaml`** in the repo if you want a different username, and
   commit it.
5. **Enable + first run:** open the **Actions** tab, enable workflows if asked,
   pick the **poll** workflow, and click **Run workflow** once. This first run
   *baselines* existing comments (no alerts) and saves state. After that it runs
   itself every ~5 minutes and alerts on new picks.

Notes:
- Scheduled workflows get auto-disabled after **60 days of no repo activity** —
  the state commits usually keep it active, but if alerts ever stop, open the
  Actions tab and re-enable it (or push any commit).
- State (`state.json`) is committed back after each run so restarts never
  duplicate alerts.
- **Run only one** copy — either GitHub Actions *or* a long-running process
  below, not both, or they'll double-alert.

### Which host? (for ~1-minute latency instead)

- **A home device left on** (Raspberry Pi, an old laptop, a mini-PC): free if
  you have one, full control, no cloud account. You maintain it and your home
  internet/power. **Recommended if you have the hardware.**
- **Oracle Cloud "Always Free" VM**: a genuinely always-on free tier VM — a
  good cloud option. Sign-up needs a card for verification.
- **A cheap VPS** (Hetzner / DigitalOcean / Vultr, ~$4–5/month): simplest
  reliable cloud choice, no free-tier limits to babysit.
- **Avoid "free" PaaS tiers that sleep on idle** (some free app platforms spin
  down inactive apps). A sleeping host defeats the whole point — it must stay
  awake 24/7.

The workload is tiny (one small HTTP request a minute), so the cheapest
always-on option is plenty.

### Option A — systemd (Linux VM or Pi)

```bash
sudo mkdir -p /opt/reddit-pick-alerts
sudo cp -r . /opt/reddit-pick-alerts
cd /opt/reddit-pick-alerts
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# create config.yaml and .env here (chmod 600 .env)

sudo cp deploy/reddit-pick-alerts.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reddit-pick-alerts
journalctl -u reddit-pick-alerts -f        # watch the logs
```

Edit paths in the unit file if you installed elsewhere. `Restart=always` brings
it back after crashes or reboots.

### Option B — Docker

```bash
docker build -t reddit-pick-alerts .
# Put config.yaml and state.json in ./data, secrets in .env
mkdir -p data && cp config.example.yaml data/config.yaml   # then edit it
#   set  state_file: /data/state.json  inside data/config.yaml

docker run -d --name pick-alerts --restart unless-stopped \
  --env-file .env \
  -v "$PWD/data:/data" \
  reddit-pick-alerts
```

State persists in the mounted `./data` volume, so restarts don't re-alert.

---

## Notes & limits

- **RSS only.** No HTML scraping, no Reddit login. A descriptive `User-Agent`
  is required or Reddit returns 403/429 — personalise it in `config.yaml`.
- The feed exposes roughly the user's most recent comments, which is plenty for
  catching a fresh daily pick within a minute.
- This tool **only notifies you**. Reviewing the pick and placing any bet is
  entirely on you.
