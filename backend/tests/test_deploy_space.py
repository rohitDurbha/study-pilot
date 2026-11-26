"""Tests for the Hugging Face Space deploy script with the Hub and network faked."""

import deploy_space


class FakeApi:
    def __init__(self):
        self.calls = []
        self.uploaded = None

    def whoami(self):
        return {"name": "RohitD"}

    def create_repo(self, repo_id, **kwargs):
        self.calls.append(("create_repo", repo_id, kwargs))

    def add_space_secret(self, repo_id, key, value):
        self.calls.append(("secret", key))

    def add_space_variable(self, repo_id, key, value):
        self.calls.append(("variable", key, value))

    def upload_folder(self, repo_id, folder_path, **kwargs):
        from pathlib import Path

        self.uploaded = sorted(p.name for p in Path(folder_path).iterdir())
        self.card = (Path(folder_path) / "README.md").read_text(encoding="utf-8")


def test_space_host_follows_the_hugging_face_naming():
    assert deploy_space.space_host("Some_User/study.pilot") == "some-user-study-pilot.hf.space"


def test_deploy_refuses_without_the_needed_secrets(capsys):
    assert deploy_space.deploy({}, api=FakeApi()) == 1
    out = capsys.readouterr().out
    assert "HF_TOKEN" in out and "GROQ_API_KEY or GEMINI_API_KEY" in out


def test_deploy_copies_keys_and_uploads_the_backend_without_local_files(tmp_path):
    api = FakeApi()
    out_file = tmp_path / "out.txt"
    env = {
        "HF_TOKEN": "hf_x",
        "GROQ_API_KEY": "gsk_x",
        "FRONTEND_ORIGIN": "https://study-pilot.vercel.app",
        "GITHUB_OUTPUT": str(out_file),
    }

    assert deploy_space.deploy(env, api=api) == 0

    assert ("create_repo", "RohitD/study-pilot", {"repo_type": "space", "space_sdk": "docker", "exist_ok": True}) in api.calls
    assert ("secret", "GROQ_API_KEY") in api.calls
    assert ("secret", "GEMINI_API_KEY") not in api.calls
    assert ("variable", "FRONTEND_ORIGIN", "https://study-pilot.vercel.app") in api.calls
    assert not any(c[0] == "variable" and c[1] == "GEMINI_MODEL" for c in api.calls)
    assert {"Dockerfile", "main.py", "requirements.txt", "routes", "README.md"} <= set(api.uploaded)
    assert not {"tests", "deploy_space.py", ".env", "studybuddy.db"} & set(api.uploaded)
    assert "sdk: docker" in api.card and "app_port: 7860" in api.card
    assert "url=https://rohitd-study-pilot.hf.space" in out_file.read_text()


def test_wait_stops_on_a_build_error():
    result = deploy_space.wait(
        {"HF_SPACE_REPO_ID": "a/b"},
        sleep=lambda s: None,
        request=lambda *a, **k: (None, {}, None),
        stage_of=lambda rid: "BUILD_ERROR",
    )
    assert result == 1


def test_wait_returns_once_the_space_runs_and_answers():
    stages = iter(["BUILDING", "RUNNING"])
    statuses = iter([None, 200])
    result = deploy_space.wait(
        {"HF_SPACE_REPO_ID": "a/b"},
        sleep=lambda s: None,
        request=lambda *a, **k: (next(statuses), {}, None),
        stage_of=lambda rid: next(stages),
    )
    assert result == 0


def fake_backend(health, cors_origin="https://site.vercel.app"):
    def request(url, method="GET", headers=None, timeout=60):
        if url.endswith("/health"):
            return 200, {}, health
        if url.endswith("/api/documents"):
            return 200, {}, []
        if method == "OPTIONS":
            return 200, {"Access-Control-Allow-Origin": cors_origin}, None
        return 404, {}, None

    return request


def test_check_passes_on_a_healthy_backend(capsys):
    env = {"HF_SPACE_REPO_ID": "a/b", "FRONTEND_ORIGIN": "https://site.vercel.app"}
    assert deploy_space.check(env, request=fake_backend({"status": "ok", "llm_providers": ["groq"]})) == 0


def test_check_uses_backend_url_instead_of_the_space(capsys):
    seen = []
    inner = fake_backend({"status": "ok", "llm_providers": ["groq"]}, cors_origin="http://localhost:3000")

    def request(url, method="GET", headers=None, timeout=60):
        seen.append(url)
        return inner(url, method=method, headers=headers, timeout=timeout)

    env = {"BACKEND_URL": "http://localhost:7860/", "FRONTEND_ORIGIN": "http://localhost:3000"}
    assert deploy_space.check(env, request=request) == 0
    assert seen and all(url.startswith("http://localhost:7860/") for url in seen)
    assert "//health" not in "".join(seen)


def test_check_fails_without_providers_or_with_the_wrong_cors_origin(capsys):
    env = {"HF_SPACE_REPO_ID": "a/b", "FRONTEND_ORIGIN": "https://site.vercel.app"}
    request = fake_backend({"status": "ok", "llm_providers": []}, cors_origin="http://localhost:3000")

    assert deploy_space.check(env, request=request) == 1
    out = capsys.readouterr().out
    assert "provider" in out and "CORS" in out


class FakeVariable:
    def __init__(self, value):
        self.value = value


class OriginApi(FakeApi):
    def __init__(self, current=None):
        super().__init__()
        self.current = current

    def get_space_variables(self, repo_id):
        return {} if self.current is None else {"FRONTEND_ORIGIN": FakeVariable(self.current)}


def test_set_origin_writes_the_site_and_the_local_dev_server(tmp_path):
    api = OriginApi()
    out_file = tmp_path / "out.txt"
    env = {"HF_TOKEN": "hf_x", "SITE_URL": "https://study-pilot.vercel.app/", "GITHUB_OUTPUT": str(out_file)}

    assert deploy_space.set_origin(env, api=api) == 0

    assert ("variable", "FRONTEND_ORIGIN", "https://study-pilot.vercel.app,http://localhost:3000") in api.calls
    assert "changed=true" in out_file.read_text()


def test_set_origin_leaves_a_correct_value_alone_so_the_space_does_not_restart(tmp_path):
    api = OriginApi(current="https://study-pilot.vercel.app,http://localhost:3000")
    out_file = tmp_path / "out.txt"
    env = {"HF_TOKEN": "hf_x", "SITE_URL": "https://study-pilot.vercel.app", "GITHUB_OUTPUT": str(out_file)}

    assert deploy_space.set_origin(env, api=api) == 0

    assert not any(c[0] == "variable" for c in api.calls)
    assert "changed=false" in out_file.read_text()


def test_set_origin_needs_a_site_url():
    assert deploy_space.set_origin({"HF_TOKEN": "hf_x"}, api=OriginApi()) == 1
