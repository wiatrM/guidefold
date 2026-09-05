#!/usr/bin/env python3
"""Prepare local secrets/snapshot and deploy the native service through Compose.

Python runs only on the operator's machine; the API, migration and publisher
containers execute a static Go binary. Existing secrets and DB volume survive.
"""
from pathlib import Path
import argparse
import json
import os
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def prepare(args):
    from tools.serve_spike.repository import build, canonical
    from tools.serve_spike.server import load_cli_snapshot
    local = ROOT / '.guidefold/compose'
    directory = local / 'secrets'
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    for name in ('postgres_password', 'app_password', 'api_token'):
        path = directory / name
        if not path.exists():
            path.write_text(secrets.token_urlsafe(40) + '\n')
        # Private parent protects host access. Compose file secrets are readable
        # by the unprivileged container UID without platform-specific chown.
        path.chmod(0o444)
    cli, sha = load_cli_snapshot(ROOT / 'skills/guidefold/scripts/guidefold')
    bundle = build(Path(args.repo_root), args.repo_id, args.revision, cli, sha)
    (local / 'snapshot.json').write_bytes(canonical(bundle) + b'\n')
    print(json.dumps({'prepared': True, 'repo_id': args.repo_id,
                      'revision': bundle['snapshot']['revision'],
                      'cards': len(bundle['snapshot']['cards'])}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'deploy'))
    parser.add_argument('--repo-root', default=str(ROOT / 'examples/monorepo'))
    parser.add_argument('--repo-id', default=os.environ.get('GUIDEFOLD_REPO', 'meridian'))
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    prepare(args)
    if args.command == 'deploy':
        env = dict(os.environ, GUIDEFOLD_REPO=args.repo_id)
        for command in (['build', 'api'], ['--profile', 'tools', 'run', '--rm', 'publish'],
                        ['up', '-d', '--wait', 'api']):
            subprocess.run(['docker', 'compose', *command], cwd=ROOT, env=env, check=True)
        print('SEARCH/USE ready at http://127.0.0.1:' + os.environ.get('GUIDEFOLD_PORT', '8765'))
        print('Token file: ' + str(ROOT / '.guidefold/compose/secrets/api_token'))


if __name__ == '__main__':
    main()
