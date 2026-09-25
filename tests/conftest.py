"""Suite-wide guards.

No test ever reaches a real Inventor session: `create_app` and the
`rename --repair` command look up `inventor_session.connect` at call time;
here it answers "not running" unless a test installs its own fake session.

No test ever launches Inventor: `inventor_session.launch` answers None unless a
test installs its own fake launcher.

No test ever writes the owner's machine-local cache: every test gets its own
cache base through `PIHTI_DEDUP_CACHE_ROOT`, outside its workspace, and a test
that means to read the real default removes the variable itself.

No test ever writes a STEP mirror beside a real workspace: every test gets its
own not-yet-created mirror folder through `PIHTI_DEDUP_STEP_MIRROR`.
"""

import pytest

from pihti_dedup import cache_root, inventor_session, step_mirror


@pytest.fixture(autouse=True)
def no_real_inventor(monkeypatch):
    monkeypatch.setattr(inventor_session, "connect", lambda **_: None)
    monkeypatch.setattr(inventor_session, "launch", lambda **_: None)


@pytest.fixture(autouse=True)
def machine_cache_base(monkeypatch, tmp_path_factory):
    base = tmp_path_factory.mktemp("machine-cache")
    monkeypatch.setenv(cache_root.ENV_VAR, str(base))
    return base


@pytest.fixture(autouse=True)
def step_mirror_folder(monkeypatch, tmp_path_factory):
    folder = tmp_path_factory.mktemp("step-mirror") / "mirror"
    monkeypatch.setenv(step_mirror.ENV_VAR, str(folder))
    return folder
