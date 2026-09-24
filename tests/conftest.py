"""Suite-wide guard: no test ever reaches a real Inventor session.

`create_app` and the `rename --repair` command look up
`inventor_session.connect` at call time; here it answers "not running" unless
a test installs its own fake session.
"""

import pytest

from pihti_dedup import inventor_session


@pytest.fixture(autouse=True)
def no_real_inventor(monkeypatch):
    monkeypatch.setattr(inventor_session, "connect", lambda **_: None)
