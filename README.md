# ClawShield

Intent-aware PDF form-filling assistant built on OpenClaw + ArmorClaw with policy enforcement, structured logging, and workspace isolation.

## Prerequisites

- **Node.js** 20+ and **pnpm**
- **Python** 3.10+ with `venv`
- **OpenClaw** built at `~/openclaw-armoriq` (`pnpm install && pnpm build`)
- **ArmorClaw** installed at `~/.openclaw/extensions/armorclaw/` (with `npm install` run inside)
- API keys configured in `.env`:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_VISION_MODEL` (e.g. `qwen/qwen3-vl-235b-a22b-instruct`)
  - `ARMORIQ_API_KEY`

## One-Time Setup

### 1. Python virtual environment

```bash
cd /home/mano/Desktop/claw-shield
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Build the TypeScript plugin

```bash
cd plugin
npm install
npm run build
cd ..
```

### 3. Initialize ArmorClaw policies

```bash
bash scripts/init-policies.sh
```

### 4. Install the plugin into OpenClaw

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
cd ~/openclaw-armoriq
node openclaw.mjs plugins install -l /home/mano/Desktop/claw-shield/plugin
```

The OpenClaw config at `~/.openclaw/openclaw.json` is already wired to load the plugin and ArmorClaw.

## Running the Happy Path

You need **two terminals** running simultaneously, then a third to talk to the agent.

### Terminal 1 — Python Worker

```bash
cd /home/mano/Desktop/claw-shield
source .venv/bin/activate
uvicorn worker.server:app --host 127.0.0.1 --port 8100
```

Verify it's up:

```bash
curl http://127.0.0.1:8100/health
# {"status":"ok"}
```

### Terminal 2 — OpenClaw Gateway

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
cd ~/openclaw-armoriq
node openclaw.mjs gateway
```

> If you get `gateway start blocked: set gateway.mode=local`, the config fix is already applied.
> To bypass without editing config, use: `node openclaw.mjs gateway --allow-unconfigured`

Wait until you see:

```
ClawShield plugin loaded — worker=http://127.0.0.1:8100  workspace=...
```

### Terminal 3 — Send a message

Option A — single-shot agent run:

```bash
cd ~/openclaw-armoriq
node openclaw.mjs agent --message "Fill the test form using my student profile"
```

Option B — interactive TUI:

```bash
cd ~/openclaw-armoriq
node openclaw.mjs tui
```

Then type: `Fill the test form using my student profile`

### What happens

1. Agent parses your request into a structured **intent object**
2. `form_detect_fields` — analyzes `workspace/forms/inbox/test_form.pdf` via the vision model
3. `form_extract_profile_data` — matches `workspace/data/profile/student_profile.json` to detected fields
4. `form_fill_pdf` — overlays values onto the PDF, saves to `workspace/forms/staged/`
5. `form_save_output` — copies the filled PDF to `workspace/forms/outbox/`

### Verify

```bash
# Filled PDF in outbox:
ls workspace/forms/outbox/

# Trace logs:
cat workspace/logs/trace-*.jsonl
```

## Project Structure

```
claw-shield/
├── worker/                    # Python FastAPI service
│   ├── server.py              # HTTP endpoints wrapping utils
│   └── profile_extractor.py   # Profile-to-field matching
├── plugin/                    # TypeScript OpenClaw plugin
│   ├── openclaw.plugin.json   # Plugin manifest
│   ├── src/
│   │   ├── index.ts           # Entry point, registers all tools
│   │   ├── tools/             # form_detect_fields, form_fill_pdf, etc.
│   │   └── utils/             # workerClient, pathValidator, logger
│   └── dist/                  # Compiled output
├── workspace/                 # Agent workspace (filesystem sandbox)
│   ├── forms/inbox/           # Input PDFs
│   ├── forms/outbox/          # Filled PDFs (output)
│   ├── forms/staged/          # Intermediate artifacts
│   ├── data/profile/          # Profile JSON files
│   ├── logs/                  # Structured trace logs
│   └── SOUL.md                # Agent personality + intent rules
├── scripts/
│   └── init-policies.sh       # ArmorClaw policy setup
├── utils/                     # Original Python utilities (unchanged)
├── SOUL.md                    # Agent system prompt
├── app.py                     # Original Streamlit app (preserved)
└── .env                       # API keys
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` on port 8100 | Terminal 1 isn't running — start the worker |
| `plugin not found: clawshield` | Rebuild plugin (`cd plugin && npm run build`) and re-run `plugins install` |
| No fields detected | Check worker terminal for vision model errors; verify `OPENROUTER_VISION_MODEL` in `.env` |
| Profile values not matching | Field labels from the vision model may differ from the alias map in `worker/profile_extractor.py` — add aliases as needed |
| Config validation fails | Run `cd ~/openclaw-armoriq && node openclaw.mjs config validate` and fix reported keys |
