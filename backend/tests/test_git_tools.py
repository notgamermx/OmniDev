import subprocess

import pytest

from app.services.tool_registry import GitCommitHandler, GitDiffHandler, GitStatusHandler


@pytest.mark.asyncio
async def test_git_tools_handle_literal_paths_and_commit_messages(tmp_path):
    repo = tmp_path / 'repo with spaces'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'test@example.com'], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
    (repo / 'file.txt').write_text('hello')
    marker = tmp_path / 'injected'
    message = f'Literal $(touch {marker})'
    context = {'project_root': repo}
    status = await GitStatusHandler().execute({}, context)
    assert status['untracked'] == ['file.txt']
    result = await GitCommitHandler().execute({'message': message}, context)
    assert result['success']
    assert not marker.exists()
    assert subprocess.check_output(['git', '-C', str(repo), 'log', '-1', '--format=%s'], text=True).strip() == message
    (repo / 'file.txt').write_text('changed')
    assert 'changed' in (await GitDiffHandler().execute({}, context))['diff']


@pytest.mark.asyncio
async def test_git_tools_reject_paths_outside_project(tmp_path):
    with pytest.raises(ValueError):
        await GitStatusHandler().execute({'path': '..'}, {'project_root': tmp_path})
