#!/usr/bin/env python3
"""Deploy an immutable, checksummed upstream development image with cold rollback."""
import datetime
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request

BASE = Path('/opt/sub2api')
REPO = 'Yuna-Celisse/sub2api-dev'
IMAGE = 'ghcr.io/yuna-celisse/sub2api'
DATA_DIRS = ('data', 'postgres_data', 'redis_data')


def request(url):
    headers = {'User-Agent': 'sub2api-dev-updater', 'Accept': 'application/vnd.github+json' if 'api.github.com' in url else '*/*'}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180)


def compose(*args):
    subprocess.run(['docker', 'compose', '--env-file', '.env', '--env-file', 'image.env', '-f', 'compose.yaml', *args], cwd=BASE, check=True)


def healthy():
    for _ in range(90):
        try:
            with request('http://127.0.0.1:8092/health') as res:
                if json.load(res).get('status') == 'ok':
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main():
    os.umask(0o077)
    lock = (BASE / '.update.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with request(f'https://api.github.com/repos/{REPO}/releases?per_page=30') as res:
        releases = json.load(res)
    releases = [r for r in releases if not r['draft'] and re.fullmatch(r'dev-[0-9a-f]{40}', r['tag_name'])]
    if not releases:
        raise RuntimeError('No completed development image release yet')
    release = max(releases, key=lambda r: r['published_at'])
    revision = release['tag_name'][4:]
    target = f'{IMAGE}:dev-{revision}'
    current_file = BASE / 'image.env'
    current = current_file.read_text() if current_file.exists() else ''
    if current.strip() == f'SUB2API_IMAGE={target}' and healthy():
        print('Already running upstream', revision, flush=True)
        return
    assets = {a['name']: a['browser_download_url'] for a in release['assets']}
    names = ('SHA256SUMS', 'revision.txt', 'sub2api-dev.tar.gz')
    if not all(name in assets for name in names):
        raise RuntimeError('Incomplete image release')
    downloads = BASE / 'downloads'
    downloads.mkdir(exist_ok=True)
    try:
        for name in names:
            with request(assets[name]) as res, (downloads / name).open('wb') as out:
                shutil.copyfileobj(res, out, 1024 * 1024)
        checksums = {}
        for line in (downloads / 'SHA256SUMS').read_text().splitlines():
            digest, filename = line.split(maxsplit=1)
            checksums[filename.strip().lstrip('*')] = digest
        for name in names[1:]:
            digest = hashlib.sha256()
            with (downloads / name).open('rb') as src:
                for block in iter(lambda: src.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != checksums.get(name):
                raise RuntimeError(f'Checksum mismatch: {name}')
        if (downloads / 'revision.txt').read_text().strip() != revision:
            raise RuntimeError('Release revision mismatch')
        with gzip.open(downloads / 'sub2api-dev.tar.gz', 'rb') as src:
            proc = subprocess.Popen(['docker', 'load'], stdin=subprocess.PIPE)
            try:
                shutil.copyfileobj(src, proc.stdin, 1024 * 1024)
            finally:
                proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError('Docker image import failed')
        label = subprocess.check_output(['docker', 'image', 'inspect', target, '--format', '{{index .Config.Labels "org.opencontainers.image.revision"}}'], text=True).strip()
        if label != revision:
            raise RuntimeError('Image revision label mismatch')
        # Never pull database major/minor updates as a side effect of app updates.
        for dependency in ('postgres:18-alpine', 'redis:8-alpine'):
            subprocess.run(['docker', 'image', 'inspect', dependency], stdout=subprocess.DEVNULL, check=True)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = BASE / 'backups' / f'sub2api-{timestamp}'
        backup.mkdir(parents=True)
        if current:
            compose('stop')
        with tarfile.open(backup / 'data.tar.gz', 'w:gz', compresslevel=1) as archive:
            for name in DATA_DIRS:
                archive.add(BASE / name, arcname=name)
        shutil.copy2(BASE / '.env', backup / '.env')
        (backup / 'image.env').write_text(current)
        try:
            pending = BASE / 'image.env.tmp'
            pending.write_text(f'SUB2API_IMAGE={target}\n')
            pending.replace(current_file)
            compose('up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300')
            if not healthy():
                raise RuntimeError('Updated application did not become healthy')
        except BaseException:
            compose('stop')
            failed = BASE / f'failed-data-{timestamp}'
            failed.mkdir()
            for name in DATA_DIRS:
                (BASE / name).rename(failed / name)
            with tarfile.open(backup / 'data.tar.gz') as archive:
                archive.extractall(BASE, filter='data')
            current_file.write_text(current)
            if current:
                compose('up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300')
                if not healthy():
                    raise RuntimeError('Previous application also failed startup after rollback')
            raise
        print('Healthy standard-mode deployment of upstream', revision, flush=True)
        for old in sorted((BASE / 'backups').glob('sub2api-*'))[:-7]:
            shutil.rmtree(old)
        tags = subprocess.check_output(['docker', 'image', 'ls', IMAGE, '--format', '{{.Tag}}'], text=True).splitlines()
        tags = [f'{IMAGE}:{tag}' for tag in tags if re.fullmatch(r'dev-[0-9a-f]{40}', tag)]
        if len(tags) > 3:
            details = json.loads(subprocess.check_output(['docker', 'image', 'inspect', *tags], text=True))
            keep = {item['Id'] for item in sorted(details, key=lambda x: x['Created'], reverse=True)[:3]}
            for tag, item in zip(tags, details):
                if item['Id'] not in keep and tag != target:
                    subprocess.run(['docker', 'image', 'rm', tag], check=False)
    finally:
        for name in names:
            (downloads / name).unlink(missing_ok=True)


if __name__ == '__main__':
    main()
