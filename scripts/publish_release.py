"""Publish a complete asset set, restoring the previous set on upload failure.

The caller must serialize this job per tag with cancel-in-progress disabled.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def lookup(endpoint, *, missing=False):
    # Only an explicit HTTP 404 permits creation; keep all other diagnostics.
    for attempt in range(3):
        result = subprocess.run(['gh', 'api', '--include', endpoint], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout.split('\n\n', 1)[1])
        print(result.stderr, end='', file=sys.stderr)
        status = result.stdout.splitlines()[0] if result.stdout else ''
        if missing and status.split()[1:2] == ['404']:
            return None
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise RuntimeError(f'GitHub lookup failed: {endpoint}')


def fresh(repo, tag):
    ref = lookup(f'{repo}/git/ref/tags/{quote(tag, safe="")}')['object']
    while ref['type'] == 'tag':
        ref = lookup(f'{repo}/git/tags/{ref["sha"]}')['object']
    if ref['sha'] != os.environ['GITHUB_SHA']:
        raise RuntimeError('Release tag no longer points to this build')
    run = lookup(f'{repo}/actions/runs/{os.environ["GITHUB_RUN_ID"]}')
    # Runs are newest first; the first page detects newer runs even if this
    # run is old enough to have fallen off the page.
    page = lookup(f'{repo}/actions/workflows/{run["workflow_id"]}/runs'
                  f'?branch={quote(tag, safe="")}&per_page=100')
    if any(r['run_number'] > run['run_number'] for r in page['workflow_runs']):
        raise RuntimeError('A newer run exists for this tag')


def managed(name):
    return (name in {'OmniDev-Windows-x64.msi', 'OmniDev-Windows-CLI.zip', 'SHA256SUMS'}
            or name.lower().startswith('omnidev') and name.endswith(('.whl', '.deb')))


def publish(directory):
    repo = f'repos/{os.environ["GH_REPO"]}'
    tag = os.environ['RELEASE_TAG']
    files = sorted(directory.iterdir())
    fresh(repo, tag)
    release = lookup(f'{repo}/releases/tags/{quote(tag, safe="")}', missing=True)
    if release is None:
        gh('release', 'create', tag, '--draft', '--verify-tag', '--title',
           f'OmniDev {tag}', '--generate-notes')
        release = lookup(f'{repo}/releases/tags/{quote(tag, safe="")}')
    original_draft = release['draft']
    old = [a for a in release['assets'] if managed(a['name'])]
    with tempfile.TemporaryDirectory() as temporary:
        backup = Path(temporary)
        # Download before clobbering anything; a backup failure leaves the release intact.
        for asset in old:
            if Path(asset['name']).name != asset['name']:
                raise RuntimeError('Unsafe asset filename')
            gh('release', 'download', tag, '--pattern', asset['name'], '--dir', str(backup))
        fresh(repo, tag)
        # GitHub has no atomic multi-asset swap. Hide the release during replacement.
        gh('release', 'edit', tag, '--draft=true')
        try:
            current = {f.name for f in files}
            for asset in old:
                if asset['name'] not in current:
                    gh('release', 'delete-asset', tag, asset['name'], '--yes')
            gh('release', 'upload', tag, *map(str, files), '--clobber')
            fresh(repo, tag)
        except BaseException:
            try:
                attached = lookup(f'{repo}/releases/tags/{quote(tag, safe="")}')['assets']
                for asset in attached:
                    if managed(asset['name']):
                        gh('release', 'delete-asset', tag, asset['name'], '--yes')
                originals = sorted(backup.iterdir())
                if originals:
                    gh('release', 'upload', tag, *map(str, originals))
                if not original_draft:
                    gh('release', 'edit', tag, '--draft=false')
            except BaseException as error:
                raise RuntimeError('Rollback failed; release remains draft for recovery') from error
            raise
        gh('release', 'edit', tag, '--draft=false')


if __name__ == '__main__':
    publish(Path('release'))
