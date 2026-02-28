# Viewing the Shiok Lah! Graph in LangGraph Studio

## What the graph looks like

```
START
  └─► load_state
        └─► preflight
              ├─► (error / game_over) ─► persist ─► END
              └─► gate
                    ├─► character_node ─► voice_node  ─┐
                    │                  └─► win_check   ─┤─► persist ─► END
                    └─► suspicion_node ─► apply_suspicion ─┘
```

Nodes in parallel from `gate`: `character_node` and `suspicion_node` run concurrently (no cross-branch edges).

---

## Prerequisites

| Tool | Status |
|------|--------|
| Python 3.12 | Already present |
| uv | Already present (`pyproject.toml` + `.venv` exist) |
| langgraph-cli | Already in dev deps — installed in `.venv` |
| LangSmith account | Free at https://smith.langchain.com |

---

## Step-by-step

### 1  Confirm `langgraph.json` is present in `backend/`

```json
{
  "graphs": {
    "shiok_lah_conversation": "./graph/conversation_graph.py:compile_conversation_graph"
  },
  "env": ".env",
  "dependencies": [
    "langchain-mistralai>=1.1.0",
    "langchain-core>=0.3.0",
    "langgraph>=0.2.0",
    "sqlalchemy>=2.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "elevenlabs>=1.0.0",
    "mistralai>=1.0.0",
    "fastapi[standard]>=0.115.0",
    "uvicorn[standard]>=0.30.0"
  ]
}
```

- Packages are listed explicitly (not `"."`) to avoid `pip install .` failing due to `[tool.uv] package = false`.
- `env` → `.env` loads `MISTRAL_API_KEY`, `ELEVENLABS_API_KEY`, `DB_PATH`.

---

### 2  Start the dev server using the venv binary directly

```bash
cd /path/to/Shiok-Lah./backend
.venv/bin/langgraph dev
```

> **Why `.venv/bin/langgraph dev` and not `langgraph dev` or `uv run langgraph dev`?**
> Both of those still cause langgraph-cli to create its own managed pip environment from the `dependencies` list, which doesn't have the `backend/` source on `sys.path`. Calling `.venv/bin/langgraph dev` directly forces it to use the existing `.venv` Python where everything is already installed and the working directory is already on the path.

Expected output:

```
Ready!
- API: http://localhost:2024
- Docs: http://localhost:2024/docs
- LangGraph Studio Web UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

The server hot-reloads when you edit any graph file.

---

### 3  Open Studio in the browser

Copy the Studio URL printed above:

```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

Log in with your LangSmith account (free).

---

### 4  Select the graph

In the Studio dropdown at the top-left select **`shiok_lah_conversation`**.

---

### 5  Send a test invocation

Paste this into the **Input** panel and click **Run**:

```json
{
  "session_id": "studio-test-01",
  "character_id": "uncle_ravi",
  "user_message": null
}
```

- `user_message: null` simulates a **click** (opener greeting from the NPC).
- Set `user_message` to a string to simulate a **player message**.

---

### 6  Explore the trace

Each node (`load_state`, `preflight`, `gate`, `character_node`, `suspicion_node`, `voice_node`, `win_check`, `apply_suspicion`, `persist`) appears as a step in the left panel with its input/output state snapshot.

---

## Useful variants

**Simulate a message turn:**
```json
{
  "session_id": "studio-test-01",
  "character_id": "uncle_ravi",
  "user_message": "Eh, I heard there's something special about today's laksa?"
}
```

**Force early error path (missing session):**
```json
{
  "session_id": "does-not-exist",
  "character_id": "uncle_ravi",
  "user_message": null
}
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'langchain_mistralai'` | Use `.venv/bin/langgraph dev` — not `langgraph dev` or `uv run langgraph dev` |
| `No dependencies found in config` | `dependencies` must be a non-empty list in `langgraph.json` — do not remove the field |
| `ModuleNotFoundError: No module named 'graph'` | Run from inside `backend/`, not the repo root |
| `MISTRAL_API_KEY not set` | Check `backend/.env` has the key set |
| Port 2024 in use | `.venv/bin/langgraph dev --port 2025` |
| Studio shows "Cannot connect" | Ensure the dev server is still running |
| `db/models.py` init fails | SQLite file is auto-created on first run — safe to ignore |

---

## macOS Desktop App (alternative)

Download **LangGraph Studio.app** from https://github.com/langchain-ai/langgraph-studio/releases, open it, and point it at the `backend/` folder (the folder containing `langgraph.json`). It bundles the server internally — no `langgraph dev` needed.
