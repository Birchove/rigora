"""Guard rail: wizard tests must never touch the developer's real `.env`.

An earlier revision resolved the target path inside the request handler, so a
patched module attribute was bypassed and a test overwrote real credentials.
The panel now takes the path by injection; this fixture fails loudly if any
test regresses to writing the repository file.
"""

import pytest

from research_mentor.setup_wizard.env_file import env_path


@pytest.fixture(autouse=True)
def protect_real_env_file():
    target = env_path()
    before = target.read_bytes() if target.is_file() else None

    yield

    after = target.read_bytes() if target.is_file() else None
    if before != after:
        if before is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(before)
        pytest.fail(
            f"测试修改了真实的 {target}。面板必须使用注入的 env_file 路径。"
        )
