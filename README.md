# API Documentation Agent 🚀

A hackathon-ready starter for Problem 2 — API Documentation Agent.

## What it demonstrates
1. Load a backend repository folder.
2. Detect API routes from Python FastAPI/Flask-style source.
3. Read an existing OpenAPI JSON/YAML file.
4. Compare code routes with documented routes.
5. Use a rule-based "agent" pipeline to generate an updated OpenAPI document.
6. Validate the generated document.
7. Serve a Swagger UI documentation page locally.
8. Show an audit log and before/after changes in the dashboard.

## Requirements
- Python 3.10+
- No Node.js required for the first demo.

## Run
Windows:
    start.bat

Or:
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn backend.main:app --reload

Open:
    http://127.0.0.1:8000

## Demo
The included `sample_backend` is intentionally simple.

1. Open the dashboard.
2. Click "Scan Repository".
3. You should see the routes currently present in code.
4. Click "Compare & Generate".
5. The agent updates `sample_backend/openapi.generated.json`.
6. Open "Swagger Docs".
7. Edit `sample_backend/app.py` and add a new route.
8. Scan again and compare again.

## Important hackathon mapping
- Git repository integration: repository folder + Git metadata detection, with a webhook-ready endpoint.
- Change detection: file fingerprinting / scan comparison.
- API route extraction: AST-based Python route extraction.
- Existing OpenAPI reading: JSON and YAML support.
- API change comparison: added/removed/modified route detection.
- Automatic OpenAPI update: generated OpenAPI 3 document.
- OpenAPI validation: structural validation of required fields and paths.
- Documentation generation: Swagger UI.
- Automated deployment/local preview: local Swagger preview; CI workflow included as a starting point.

## Next upgrades for final submission
- GitHub webhook + commit SHA tracking.
- JavaScript/TypeScript route extraction.
- Request/response schema inference from Pydantic/Zod/TypeScript types.
- LLM agent for ambiguous route/schema interpretation.
- Human approval for low-confidence changes.
- GitHub Pages deployment.
