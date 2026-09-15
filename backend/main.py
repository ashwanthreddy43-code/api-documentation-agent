from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json
import hashlib
import re
import ast
import time
import yaml


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent.parent
DEFAULT_REPO = BASE / "sample_backend"
STATE = BASE / ".agent_state.json"
GENERATED = DEFAULT_REPO / "openapi.generated.json"


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="API Documentation Agent",
    version="1.0.0"
)


# ============================================================
# FILE HELPERS
# ============================================================

def load_json_or_yaml(path: Path):
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")

    if path.suffix.lower() in [".yaml", ".yml"]:
        return yaml.safe_load(raw) or {}

    return json.loads(raw)


# ============================================================
# ROUTE HELPERS
# ============================================================

def route_key(method, path):
    return f"{method.upper()} {path}"


def normalize_path(path):
    # Flask style:
    # /users/<user_id>
    #
    # becomes:
    # /users/{user_id}

    return re.sub(
        r"<([^>]+)>",
        r"{\1}",
        path
    )


# ============================================================
# RESPONSE ANALYSIS
# ============================================================

def infer_value_type(value):
    """
    Convert a Python AST value into a simple OpenAPI type.
    """

    if isinstance(value, ast.Constant):

        if isinstance(value.value, bool):
            return "boolean"

        if isinstance(value.value, int):
            return "integer"

        if isinstance(value.value, float):
            return "number"

        if isinstance(value.value, str):
            return "string"

        if value.value is None:
            return "null"

    if isinstance(value, ast.List):
        return "array"

    if isinstance(value, ast.Dict):
        return "object"

    return "string"


def infer_object_schema(node):
    """
    Convert a dictionary return value into an OpenAPI object schema.
    """

    properties = {}

    if not isinstance(node, ast.Dict):
        return {
            "type": "object"
        }

    for key, value in zip(node.keys, node.values):

        if isinstance(key, ast.Constant):
            field_name = str(key.value)

            properties[field_name] = {
                "type": infer_value_type(value)
            }

    return {
        "type": "object",
        "properties": properties
    }


def infer_return_schema(function_node):
    """
    Inspect the function's return statement and create
    a lightweight OpenAPI response schema.
    """

    for node in ast.walk(function_node):

        if not isinstance(node, ast.Return):
            continue

        value = node.value

        if value is None:
            return {
                "type": "object"
            }

        # return {"id": 1, "name": "Ash"}
        if isinstance(value, ast.Dict):

            return infer_object_schema(value)

        # return [{"id": 1, "name": "Ash"}]
        if isinstance(value, ast.List):

            if value.elts:
                first = value.elts[0]

                if isinstance(first, ast.Dict):

                    return {
                        "type": "array",
                        "items": infer_object_schema(first)
                    }

            return {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }

        return {
            "type": infer_value_type(value)
        }

    return {
        "type": "object"
    }


# ============================================================
# DECORATOR ANALYSIS
# ============================================================

def decorators_from_function(node):

    routes = []

    for dec in node.decorator_list:

        call = dec if isinstance(dec, ast.Call) else None

        if not call:
            continue

        func = call.func

        name = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, "id", "")
        )

        allowed = {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head",
            "api_route",
            "route"
        }

        if name not in allowed:
            continue

        if not call.args:
            continue

        try:
            path = ast.literal_eval(call.args[0])
        except Exception:
            continue

        methods = []

        if name in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head"
        }:

            methods = [name.upper()]

        else:

            for kw in call.keywords:

                if kw.arg == "methods":

                    try:
                        methods = [
                            str(x).upper()
                            for x in ast.literal_eval(kw.value)
                        ]
                    except Exception:
                        pass

            if not methods:
                methods = ["GET"]

        response_schema = infer_return_schema(node)

        for method in methods:

            routes.append(
                {
                    "method": method,
                    "path": normalize_path(str(path)),
                    "function": node.name,
                    "file": "",
                    "line": node.lineno,
                    "confidence": "high",
                    "response_schema": response_schema
                }
            )

    return routes


# ============================================================
# PYTHON ROUTE EXTRACTION
# ============================================================

def extract_python_routes(repo: Path):

    results = []

    ignored = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__"
    }

    for p in repo.rglob("*.py"):

        if any(part in ignored for part in p.parts):
            continue

        try:

            source = p.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source,
                filename=str(p)
            )

        except Exception:
            continue

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ):

                found = decorators_from_function(node)

                for route in found:

                    route["file"] = str(
                        p.relative_to(repo)
                    ).replace("\\", "/")

                    results.append(route)

    return sorted(
        results,
        key=lambda x: (
            x["path"],
            x["method"]
        )
    )


# ============================================================
# REPOSITORY FINGERPRINT
# ============================================================

def fingerprint(repo: Path):

    h = hashlib.sha256()

    ignored = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__"
    }

    for p in sorted(repo.rglob("*")):

        if (
            p.is_file()
            and not any(
                part in ignored
                for part in p.parts
            )
        ):

            h.update(
                str(
                    p.relative_to(repo)
                ).encode()
            )

            h.update(
                p.read_bytes()
            )

    return h.hexdigest()


# ============================================================
# DOCUMENTED ROUTES
# ============================================================

def documented_routes(spec):

    out = {}

    for path, item in (
        spec.get("paths") or {}
    ).items():

        for method, operation in item.items():

            if method.lower() in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "trace"
            }:

                out[
                    route_key(method, path)
                ] = operation

    return out


# ============================================================
# SCHEMA NORMALIZATION
# ============================================================

def normalize_schema(schema):

    if not isinstance(schema, dict):
        return {}

    result = {
        "type": schema.get("type")
    }

    if schema.get("type") == "object":

        result["properties"] = {}

        for name, value in (
            schema.get("properties") or {}
        ).items():

            result["properties"][name] = {
                "type": value.get("type")
            }

    if schema.get("type") == "array":

        items = schema.get("items") or {}

        result["items"] = normalize_schema(items)

    return result


# ============================================================
# GET DOCUMENTED RESPONSE SCHEMA
# ============================================================

def get_documented_response_schema(operation):

    if not isinstance(operation, dict):
        return {}

    responses = operation.get(
        "responses",
        {}
    )

    response_200 = responses.get("200")

    if not isinstance(response_200, dict):
        return {}

    content = response_200.get(
        "content",
        {}
    )

    application_json = content.get(
        "application/json",
        {}
    )

    schema = application_json.get(
        "schema",
        {}
    )

    return normalize_schema(schema)


# ============================================================
# CHANGE COMPARISON
# ============================================================

def compare_routes(routes, spec):

    docs = documented_routes(spec)

    code_keys = {
        route_key(
            r["method"],
            r["path"]
        )
        for r in routes
    }

    added = []

    removed = []

    modified = []

    unchanged = 0

    for route in routes:

        key = route_key(
            route["method"],
            route["path"]
        )

        if key not in docs:

            added.append(route)

            continue

        operation = docs[key]

        old_schema = (
            get_documented_response_schema(
                operation
            )
        )

        new_schema = normalize_schema(
            route.get(
                "response_schema",
                {}
            )
        )

        if old_schema != new_schema:

            modified.append(
                {
                    "method": route["method"],
                    "path": route["path"],
                    "function": route["function"],
                    "file": route["file"],
                    "line": route["line"],
                    "old_response_schema": old_schema,
                    "new_response_schema": new_schema,
                    "change": "Response payload structure changed"
                }
            )

        else:

            unchanged += 1

    for key in docs:

        if key not in code_keys:

            method, path = key.split(
                " ",
                1
            )

            removed.append(
                {
                    "method": method,
                    "path": path
                }
            )

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged
    }


# ============================================================
# OPENAPI OPERATION GENERATOR
# ============================================================

def make_operation(route):

    params = []

    for name in re.findall(
        r"{([^}]+)}",
        route["path"]
    ):

        params.append(
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": {
                    "type": "string"
                }
            }
        )

    response_schema = route.get(
        "response_schema",
        {
            "type": "object"
        }
    )

    return {
        "summary": f"{route['method']} {route['path']}",
        "description": (
            f"Auto-generated from "
            f"{route['file']}:{route['line']} "
            f"({route['function']})."
        ),
        "operationId": (
            f"{route['function']}_"
            f"{route['method'].lower()}"
        ),
        "parameters": params,
        "responses": {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": response_schema
                    }
                }
            }
        }
    }


# ============================================================
# OPENAPI GENERATION
# ============================================================

def generate_spec(routes, existing):

    if existing:

        spec = existing

    else:

        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "Auto-generated API",
                "version": "1.0.0"
            },
            "paths": {}
        }

    spec.setdefault(
        "openapi",
        "3.0.3"
    )

    spec.setdefault(
        "info",
        {
            "title": "Auto-generated API",
            "version": "1.0.0"
        }
    )

    spec.setdefault(
        "paths",
        {}
    )

    for route in routes:

        path = route["path"]

        method = route["method"].lower()

        spec["paths"].setdefault(
            path,
            {}
        )

        spec["paths"][path][method] = (
            make_operation(route)
        )

    # Remove routes that no longer exist.

    live = {
        route_key(
            r["method"],
            r["path"]
        )
        for r in routes
    }

    for path in list(spec["paths"]):

        for method in list(
            spec["paths"][path]
        ):

            if method.lower() in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "trace"
            }:

                if route_key(
                    method,
                    path
                ) not in live:

                    del spec["paths"][path][method]

        if not spec["paths"][path]:

            del spec["paths"][path]

    return spec


# ============================================================
# VALIDATION
# ============================================================

def validate_spec(spec):

    errors = []

    if spec.get("openapi") != "3.0.3":

        errors.append(
            "openapi must be 3.0.3 in this demo"
        )

    if not isinstance(
        spec.get("info"),
        dict
    ):

        errors.append(
            "info object missing"
        )

    if not isinstance(
        spec.get("paths"),
        dict
    ):

        errors.append(
            "paths object missing"
        )

    return {
        "valid": not errors,
        "errors": errors
    }


# ============================================================
# AUDIT LOG
# ============================================================

def audit(event, details):

    data = []

    if STATE.exists():

        try:

            data = json.loads(
                STATE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            data = []

    data.insert(
        0,
        {
            "time": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "event": event,
            "details": details
        }
    )

    STATE.write_text(
        json.dumps(
            data[:50],
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# REQUEST MODEL
# ============================================================

class RepoRequest(BaseModel):

    path: str | None = None


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def home():

    return FileResponse(
        BASE / "frontend" / "index.html"
    )


@app.get("/app.js")
def js():

    return FileResponse(
        BASE / "frontend" / "app.js"
    )


@app.get("/styles.css")
def css():

    return FileResponse(
        BASE / "frontend" / "styles.css"
    )


# ============================================================
# STATUS
# ============================================================

@app.get("/api/status")
def status():

    return {
        "repository": DEFAULT_REPO.name,
        "fingerprint": fingerprint(
            DEFAULT_REPO
        ),
        "generated_exists": GENERATED.exists()
    }


# ============================================================
# SCAN
# ============================================================

@app.post("/api/scan")
def scan():

    routes = extract_python_routes(
        DEFAULT_REPO
    )

    fp = fingerprint(
        DEFAULT_REPO
    )

    audit(
        "Repository scanned",
        {
            "routes": len(routes),
            "fingerprint": fp
        }
    )

    return {
        "routes": routes,
        "fingerprint": fp,
        "count": len(routes)
    }


# ============================================================
# COMPARE
# ============================================================

@app.post("/api/compare")
def compare():

    routes = extract_python_routes(
        DEFAULT_REPO
    )

    spec_path = (
        DEFAULT_REPO / "openapi.json"
    )

    existing = load_json_or_yaml(
        spec_path
    )

    result = compare_routes(
        routes,
        existing
    )

    audit(
        "Compared code with OpenAPI",
        result
    )

    return {
        "comparison": result,
        "existing_spec": existing
    }


# ============================================================
# GENERATE
# ============================================================

@app.post("/api/generate")
def generate():

    routes = extract_python_routes(
        DEFAULT_REPO
    )

    existing = load_json_or_yaml(
        DEFAULT_REPO / "openapi.json"
    )

    spec = generate_spec(
        routes,
        existing
    )

    validation = validate_spec(
        spec
    )

    if not validation["valid"]:

        raise HTTPException(
            status_code=400,
            detail=validation
        )

    GENERATED.write_text(
        json.dumps(
            spec,
            indent=2
        ),
        encoding="utf-8"
    )

    # Also save as the current documentation baseline.
    (
        DEFAULT_REPO / "openapi.json"
    ).write_text(
        json.dumps(
            spec,
            indent=2
        ),
        encoding="utf-8"
    )

    audit(
        "OpenAPI generated and validated",
        {
            "paths": len(
                spec["paths"]
            ),
            "valid": True
        }
    )

    return {
        "spec": spec,
        "validation": validation
    }


# ============================================================
# AUDIT
# ============================================================

@app.get("/api/audit")
def get_audit():

    if not STATE.exists():
        return []

    try:

        return json.loads(
            STATE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return []


# ============================================================
# WEBHOOK
# ============================================================

@app.post("/api/webhook")
def webhook(payload: dict):

    audit(
        "Repository push event received",
        {
            "event": payload.get(
                "head_commit",
                {}
            ).get(
                "message",
                "push"
            )
        }
    )

    return {
        "accepted": True,
        "next": (
            "scan -> compare -> "
            "generate -> validate -> deploy"
        )
    }


# ============================================================
# SWAGGER UI
# ============================================================

@app.get("/docs-ui")
def docs_ui():

    return FileResponse(
        BASE / "frontend" / "swagger.html"
    )


# ============================================================
# GENERATED OPENAPI
# ============================================================

@app.get("/sample-openapi")
def sample_openapi():

    if not GENERATED.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "OpenAPI specification "
                "not generated yet"
            )
        )

    return FileResponse(
        GENERATED,
        media_type="application/json"
    )
    