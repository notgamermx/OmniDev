from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.agent_engine import AgentEngine, ExecutionContext
from app.services.verification_guard import snapshot, unchanged
from app.services.process_service import run_command


def test_verification_changes_and_deletions_detected(tmp_path):
    tests = tmp_path / 'tests'
    tests.mkdir()
    check = tests / 'test_app.py'
    check.write_text('assert False')
    baseline = snapshot(tmp_path)
    check.write_text('assert True')
    assert not unchanged(tmp_path, baseline)
    check.unlink()
    assert not unchanged(tmp_path, baseline)


@pytest.mark.asyncio
async def test_existing_tests_cannot_be_overwritten_with_dot_path(tmp_path):
    check = tmp_path / 'test_app.py'
    check.write_text('assert False')
    context = ExecutionContext(SimpleNamespace(tool_names=['write_file']), SimpleNamespace(), str(tmp_path))
    context.verification_inputs = snapshot(tmp_path)
    result = await AgentEngine()._execute_action(context, {'tool': 'write_file', 'args': {'path': './test_app.py', 'content': 'assert True'}})
    assert not result.success
    assert check.read_text() == 'assert False'


@pytest.mark.asyncio
async def test_token_budget_prevents_provider_call(monkeypatch, tmp_path):
    context = ExecutionContext(SimpleNamespace(provider='ollama', model='test', temperature=0), SimpleNamespace(), str(tmp_path))
    context.token_spent = settings.TASK_TOKEN_BUDGET
    provider = SimpleNamespace()
    async def close(): pass
    provider.close = close
    monkeypatch.setattr('app.services.agent_engine.make_provider', lambda _: provider)
    with pytest.raises(RuntimeError, match='token budget'):
        await AgentEngine()._plan_step(context)


@pytest.mark.asyncio
async def test_docker_arguments_and_cleanup(monkeypatch, tmp_path):
    (tmp_path/'test_app.py').write_text('assert True')
    seen = []
    async def fake_run(argv, cwd, timeout):
        seen.extend(argv)
        return {'exit_code':0,'timed_out':False,'output':'ok'}
    async def fake_wait(): return 0
    async def fake_exec(*args, **kwargs): return SimpleNamespace(wait=fake_wait)
    monkeypatch.setattr('app.services.process_service.shutil.which', lambda _: '/usr/bin/docker')
    monkeypatch.setattr('app.services.process_service.run_exec', fake_run)
    monkeypatch.setattr('app.services.process_service.asyncio.create_subprocess_exec', fake_exec)
    await run_command('cat ~/.ssh/id_rsa',tmp_path,5)
    assert '--network=none' in seen and '--cap-drop=ALL' in seen
    assert '--read-only' in seen and '--pull=never' in seen
    assert any('test_app.py,readonly' in part for part in seen)
    assert not any('docker.sock' in part for part in seen)


@pytest.mark.asyncio
async def test_missing_docker_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setattr('app.services.process_service.shutil.which',lambda _: None)
    with pytest.raises(RuntimeError,match='requires Docker'):
        await run_command('echo unsafe',tmp_path,1)


@pytest.mark.asyncio
async def test_real_docker_boundaries(tmp_path):
    import os
    if os.environ.get('RUN_DOCKER_TESTS') != '1':
        pytest.skip('Run the Docker integration gate with RUN_DOCKER_TESTS=1')
    root=tmp_path/'workspace';root.mkdir()
    secret=tmp_path/'secret';secret.write_text('host-only-secret')
    (root/'test_app.py').write_text('assert False')
    result=await run_command('echo sandbox-ready',root,5)
    assert result['exit_code'] == 0 and 'sandbox-ready' in result['output'], result
    result=await run_command('cat '+str(secret),root,5)
    assert result['exit_code'] != 0 and 'host-only-secret' not in result['output']
    result=await run_command('echo tampered > test_app.py',root,5)
    assert result['exit_code'] != 0
    assert (root/'test_app.py').read_text()=='assert False'
    result=await run_command("python -c 'print(\"x\"*100000)'",root,5)
    assert result['exit_code'] == 0, result
    assert len(result['output'].encode()) <= settings.COMMAND_OUTPUT_BYTES
    result=await run_command('sleep 60',root,1)
    assert result['timed_out']


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["tests/test_app.py", "pyproject.toml", "nested/app.spec.js"])
async def test_write_handler_protects_existing_verification_inputs_directly(tmp_path, name):
    from app.services.tool_registry import WriteFileHandler
    check = tmp_path / name
    check.parent.mkdir(parents=True, exist_ok=True)
    check.write_text("original")
    with pytest.raises(RuntimeError, match="read-only"):
        await WriteFileHandler().execute({"path": "./" + name, "content": "tampered"}, {"project_root": tmp_path})
    assert check.read_text() == "original"


@pytest.mark.asyncio
async def test_handler_protects_deleted_original_but_allows_new_test_edits(tmp_path):
    from app.services.tool_registry import WriteFileHandler
    original = tmp_path / "test_original.py"
    original.write_text("original")
    context = {"project_root": tmp_path, "verification_inputs": snapshot(tmp_path)}
    original.unlink()
    handler = WriteFileHandler()
    with pytest.raises(RuntimeError, match="read-only"):
        await handler.execute({"path": original.name, "content": "tampered"}, context)
    for content in ("new", "repaired"):
        await handler.execute({"path": "test_new.py", "content": content}, context)
    assert (tmp_path / "test_new.py").read_text() == "repaired"


@pytest.mark.asyncio
async def test_write_via_hard_link_alias_does_not_modify_original_test(tmp_path):
    import os
    from app.services.tool_registry import WriteFileHandler
    original = tmp_path / "test_app.py"
    original.write_text("original")
    alias = tmp_path / "notes.txt"
    os.link(original, alias)
    await WriteFileHandler().execute({"path": alias.name, "content": "tampered"}, {"project_root": tmp_path})
    assert original.read_text() == "original"
    assert alias.read_text() == "tampered"
