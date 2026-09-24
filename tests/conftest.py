"""Suite-wide guards.

No test ever reaches a real Inventor session: `create_app` and the
`rename --repair` command look up `inventor_session.connect` at call time;
here it answers "not running" unless a test installs its own fake session.

No test ever writes the owner's machine-local cache: every test gets its own
cache base through `PIHTI_DEDUP_CACHE_ROOT`, outside its workspace, and a test
that means to read the real default removes the variable itself.
"""

import pytest

from pihti_dedup import cache_root, inventor_session


@pytest.fixture(autouse=True)
def no_real_inventor(monkeypatch):
    monkeypatch.setattr(inventor_session, "connect", lambda **_: None)


@pytest.fixture(autouse=True)
def machine_cache_base(monkeypatch, tmp_path_factory):
    base = tmp_path_factory.mktemp("machine-cache")
    monkeypatch.setenv(cache_root.ENV_VAR, str(base))
    return base
