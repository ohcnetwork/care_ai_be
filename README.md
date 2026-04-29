# care_ai_be

OpenAI-Agents-SDK powered AI assistant plugin for [Care](https://github.com/ohcnetwork/care).

Exposes `POST /api/care_ai/encounter/<encounter_external_id>/ask/`. The endpoint
authorizes the calling user against the encounter and runs an agent with
patient-scoped read-only tools.

## Configuration

Required environment variables:

- `CARE_AI_OPENAI_API_KEY` — OpenAI API key.

Optional:

- `CARE_AI_DEFAULT_MODEL` (default: `gpt-5.4-mini`)
- `CARE_AI_ALLOWED_MODELS` (comma-separated)
- `CARE_AI_MAX_TOOL_ITERATIONS` (default: `10`)
- `CARE_AI_REQUEST_TIMEOUT_SECONDS` (default: `60`)
- `CARE_AI_SYSTEM_PROMPT` (overrides default clinical prompt)
- `CARE_AI_OBSERVATION_ROW_LIMIT` (default: `200`)
- `CARE_AI_ENCOUNTER_ROW_LIMIT` (default: `50`)

## Local development

Register in Care's `plug_config.py`:

```python
plugs = [
    Plug(
        name="care_ai",
        package_name="care_ai_be",
        version="@./../care_ai_be",  # or a git URL
    ),
]
```

For local editable install:

```bash
cd /path/to/care
.venv/bin/pip install -e /path/to/care_ai_be
```

## Deployment notes

`Runner.run_sync` blocks the worker for the full agent loop (model + tools).
Run with a worker timeout greater than `CARE_AI_REQUEST_TIMEOUT_SECONDS`
(e.g. gunicorn `--timeout 90`).
