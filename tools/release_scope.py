"""Compare production's actual revision, including skipped/queued commits."""
import argparse
import json
import re
import subprocess


def classify(paths):
    api = web = migrations = False
    for path in paths:
        if path.rsplit('/', 1)[-1] in {'README.md', 'AGENTS.md'}:
            continue
        if path.startswith('apps/api/') or path in {'pyproject.toml', 'uv.lock', 'infra/api.Dockerfile', 'tools/worker_smoke.py'}:
            api = True
        if path.startswith('apps/web/') or path in {'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'infra/web.Dockerfile', 'infra/Caddyfile', 'infra/Caddyfile.production'}:
            web = True
        if path.startswith('apps/api/alembic/versions/') or path.startswith('apps/api/migrations/'):
            migrations = True
        if path == 'infra/compose.production.yaml':
            api = web = True
    return {'api': api, 'web': web, 'migrations': migrations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('target')
    args = parser.parse_args()
    if not all(re.fullmatch('[0-9a-f]{40}', sha) for sha in (args.base, args.target)):
        raise ValueError('Full production and target SHAs required')
    subprocess.run(['git', 'merge-base', '--is-ancestor', args.base, args.target], check=True)
    paths = subprocess.check_output(['git', 'diff', '--name-only', args.base, args.target], text=True).splitlines()
    scope = classify(paths)
    scope.update(base=args.base, revision=args.target)
    print(json.dumps(scope, sort_keys=True))


if __name__ == '__main__':
    main()
