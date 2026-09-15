"""CLI helper for CI/CD: extracts sample_backend routes and writes OpenAPI."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.main import extract_python_routes, generate_spec, validate_spec

repo = Path(__file__).resolve().parents[1] / "sample_backend"
existing = json.loads((repo / "openapi.json").read_text(encoding="utf-8"))
routes = extract_python_routes(repo)
spec = generate_spec(routes, existing)
check = validate_spec(spec)
if not check["valid"]:
    print(check["errors"])
    raise SystemExit(1)
(repo / "openapi.generated.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
print("Generated and validated OpenAPI successfully.")
