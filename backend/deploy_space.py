"""Push the backend to a Hugging Face Docker Space and check that it answers.

The workflow in .github/workflows/deploy-backend.yml runs

    python deploy_space.py deploy     # create the Space, copy the keys, upload the code
    python deploy_space.py wait       # poll until /health answers or the build fails
    python deploy_space.py check      # call real API routes on the live backend
    python deploy_space.py url        # print the Space URL for the frontend build
    python deploy_space.py set-origin # allow SITE_URL through CORS on the Space

It reads HF_TOKEN and the provider keys from the environment, so no key is
ever written to the repository. HF_SPACE_NAME picks the Space, either as
"name" under the token's account or as "owner/name", default "study-pilot".
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_SPACE_NAME = "study-pilot"

# Provider keys copied into the Space as secrets. At least one is needed,
# because every generation route goes through llm.py.
PROVIDER_SECRETS = ("GROQ_API_KEY", "GEMINI_API_KEY")
# Plain settings that are safe to show on the Space settings page. Each one is
# only written when it is set, so a value set by the frontend deploy (such as
# FRONTEND_ORIGIN) is not wiped by a later backend deploy.
SPACE_VARIABLES = ("FRONTEND_ORIGIN", "MAX_UPLOAD_MB", "GROQ_MODEL", "GEMINI_MODEL", "LLM_PROVIDERS")

# Files the Space does not need.
SKIP_NAMES = {
    ".env", ".venv", "__pycache__", ".pytest_cache", "tests", "deploy_space.py",
    "studybuddy.db", "chroma_db", "models", "static",
}

SPACE_CARD = """---
title: StudyPilot API
emoji: 📚
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

Flask backend for [StudyPilot](https://github.com/rohitDurbha/study-pilot), an
attention-aware study assistant. This Space is deployed automatically from the
GitHub repository, so edit the code there. Uploaded documents live in SQLite
inside the container and are lost when the Space restarts.
"""


def missing_secrets(environ) -> list[str]:
    """Names of the repository secrets a deploy cannot do without."""
    missing = []
    if not environ.get("HF_TOKEN", "").strip():
        missing.append("HF_TOKEN")
    if not any(environ.get(name, "").strip() for name in PROVIDER_SECRETS):
        missing.append(" or ".join(PROVIDER_SECRETS))
    return missing


def space_host(repo_id: str) -> str:
    """Hostname Hugging Face serves a Space on, e.g. Some_User/study.pilot -> some-user-study-pilot.hf.space."""
    owner, name = repo_id.split("/", 1)
    slug = f"{owner}-{name}".lower()
    return "".join(ch if ch.isalnum() else "-" for ch in slug) + ".hf.space"


def space_url(repo_id: str) -> str:
    return f"https://{space_host(repo_id)}"


def stage_backend(target) -> Path:
    """Copy the backend into target with a Space card as README.md."""
    target = Path(target)
    for item in BACKEND_DIR.iterdir():
        is_local_env = item.name.startswith(".env") and item.name != ".env.example"
        if item.name in SKIP_NAMES or is_local_env or item.suffix == ".db":
            continue
        dest = target / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, dest)
    (target / "README.md").write_text(SPACE_CARD, encoding="utf-8")
    return target


def write_output(name: str, value: str, environ) -> None:
    path = environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")
    print(f"{name}={value}")


def resolve_repo_id(api, environ) -> str:
    name = environ.get("HF_SPACE_NAME", "").strip() or DEFAULT_SPACE_NAME
    if "/" in name:
        return name
    return f"{api.whoami()['name']}/{name}"


def deploy(environ=None, api=None) -> int:
    environ = os.environ if environ is None else environ
    missing = missing_secrets(environ)
    if missing:
        print("Cannot deploy, these repository secrets are missing: " + ", ".join(missing))
        return 1

    if api is None:
        from huggingface_hub import HfApi

        api = HfApi(token=environ["HF_TOKEN"])
    repo_id = resolve_repo_id(api, environ)
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)

    for name in PROVIDER_SECRETS:
        value = environ.get(name, "").strip()
        if value:
            api.add_space_secret(repo_id, name, value)
    for name in SPACE_VARIABLES:
        value = environ.get(name, "").strip()
        if value:
            api.add_space_variable(repo_id, name, value)

    with tempfile.TemporaryDirectory() as tmp:
        stage_backend(tmp)
        api.upload_folder(
            repo_id=repo_id,
            repo_type="space",
            folder_path=tmp,
            commit_message=f"Deploy {environ.get('GITHUB_SHA', 'local build')[:12]}",
            delete_patterns=["*", "!.gitattributes"],
        )

    write_output("repo_id", repo_id, environ)
    write_output("url", space_url(repo_id), environ)
    return 0


def print_url(environ=None, api=None) -> int:
    """Write the Space URL to GITHUB_OUTPUT so the frontend build can use it."""
    environ = os.environ if environ is None else environ
    if not environ.get("HF_TOKEN", "").strip():
        print("Cannot work out the backend URL, the HF_TOKEN repository secret is missing.")
        return 1
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi(token=environ["HF_TOKEN"])
    write_output("url", space_url(resolve_repo_id(api, environ)), environ)
    return 0


LOCAL_ORIGIN = "http://localhost:3000"


def set_origin(environ=None, api=None) -> int:
    """Point FRONTEND_ORIGIN on the Space at the deployed frontend.

    The Vercel deploy calls this with SITE_URL, so the backend accepts the
    production site plus the local dev server. Changing a variable restarts
    the Space, so nothing is written when the value is already right.
    """
    environ = os.environ if environ is None else environ
    site = environ.get("SITE_URL", "").strip().rstrip("/")
    if not site or not environ.get("HF_TOKEN", "").strip():
        print("set-origin needs SITE_URL and the HF_TOKEN repository secret.")
        return 1
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi(token=environ["HF_TOKEN"])
    repo_id = resolve_repo_id(api, environ)
    wanted = f"{site},{LOCAL_ORIGIN}"

    current = api.get_space_variables(repo_id).get("FRONTEND_ORIGIN")
    current_value = getattr(current, "value", current)
    write_output("repo_id", repo_id, environ)
    if current_value == wanted:
        print(f"FRONTEND_ORIGIN already allows {site}")
        write_output("changed", "false", environ)
        return 0
    api.add_space_variable(repo_id, "FRONTEND_ORIGIN", wanted)
    print(f"FRONTEND_ORIGIN set to {wanted}, the Space restarts to pick it up")
    write_output("changed", "true", environ)
    return 0


def http_request(url, method="GET", headers=None, timeout=60):
    """Return (status, headers, parsed JSON or None) without raising on HTTP errors."""
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            status, resp_headers = resp.status, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), None
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None, {}, None
    try:
        return status, resp_headers, json.loads(body)
    except ValueError:
        return status, resp_headers, None


def wait(environ=None, sleep=time.sleep, clock=time.monotonic, request=http_request, stage_of=None) -> int:
    """Poll the Space until /health answers 200, the build fails, or time runs out."""
    environ = os.environ if environ is None else environ
    repo_id = environ["HF_SPACE_REPO_ID"]
    limit = float(environ.get("HF_WAIT_SECONDS", "1500"))
    url = space_url(repo_id) + "/health"

    if stage_of is None:
        from huggingface_hub import HfApi

        api = HfApi(token=environ.get("HF_TOKEN"))

        def stage_of(rid):
            return api.get_space_runtime(rid).stage

    start = clock()
    while clock() - start < limit:
        stage = stage_of(repo_id)
        if stage in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            print(f"Space {repo_id} stopped with {stage}. Open its logs on huggingface.co.")
            return 1
        status, _, _ = request(url, timeout=20)
        print(f"{int(clock() - start)}s  stage={stage}  GET /health -> {status}")
        if stage == "RUNNING" and status == 200:
            print(f"Backend is live at {space_url(repo_id)}")
            return 0
        sleep(20)
    print(f"Gave up after {int(limit)}s waiting for {url}")
    return 1


def check(environ=None, request=http_request) -> int:
    """Call real routes on the live backend and fail on anything unexpected.

    No language model is called, so the check costs no free tier quota.
    """
    environ = os.environ if environ is None else environ
    base = space_url(environ["HF_SPACE_REPO_ID"])
    problems = []

    status, _, body = request(base + "/health")
    providers = (body or {}).get("llm_providers") or []
    if status != 200 or not providers:
        problems.append(f"GET /health answered {status} with {body}, expected at least one provider")

    status, _, body = request(base + "/api/documents")
    if status != 200 or not isinstance(body, (list, dict)):
        problems.append(f"GET /api/documents answered {status} with {body}")

    origin = (environ.get("FRONTEND_ORIGIN") or "").split(",")[0].strip().rstrip("/")
    if origin:
        status, headers, _ = request(
            base + "/upload",
            method="OPTIONS",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
        allowed = {k.lower(): v for k, v in headers.items()}.get("access-control-allow-origin")
        if allowed != origin:
            problems.append(f"CORS preflight from {origin} got Access-Control-Allow-Origin {allowed!r}")

    if problems:
        print("Live check failed:\n  " + "\n  ".join(problems))
        return 1
    print(f"Live check passed at {base} with providers {', '.join(providers)}")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    commands = {"deploy": deploy, "wait": wait, "check": check, "url": print_url, "set-origin": set_origin}
    if command not in commands:
        print(__doc__)
        sys.exit(2)
    sys.exit(commands[command]())
