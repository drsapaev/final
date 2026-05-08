# LangGraph Dev-Brain Tools

This folder contains local dev-brain helpers used by `AGENTS.md`.

Current verified script:

- `scripts/agent_gate.py`

Historical `dev_brain.py` plan/dossier/handoff helpers and smoke scripts are
not present in this checkout. Do not advertise or run them unless the files are
restored and verified locally.

## Agent Gate

Run from `C:\final\ai\langgraph`:

```powershell
python scripts\agent_gate.py "<task>"
python scripts\agent_gate.py "<task>" --known-root-cause "<relative/path.py>"
```

The restored gate is deterministic and does not call a remote LLM. It accepts a
model metadata flag for downstream prompts and defaults to `gpt-5.5`:

```powershell
python scripts\agent_gate.py "<task>" --model "ChatGPT 5.5"
```

`ChatGPT 5.5`, `GPT 5.5 Pro`, `chatgpt-5.5`, and `gpt-5.5`
normalize to `gpt-5.5`.

The output contract is:

- `Result`
- `Model target`
- `First-touch files`
- `Validation targets`
- `Stop conditions`
- `Ready-to-send execution prompt`

If the gate cannot resolve a first-touch file, it exits with a non-zero status
and asks for an explicit path or `--known-root-cause`.
