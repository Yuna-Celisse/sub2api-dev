#!/usr/bin/env python3
"""Create root-readable secrets once; never print credentials."""
import json
import os
from pathlib import Path
import secrets

os.umask(0o077)
base = Path('/opt/sub2api')
base.mkdir(exist_ok=True)
env = base / '.env'
credentials_file = Path('/root/sub2api-admin.json')
if env.exists() or credentials_file.exists():
    assert env.exists() and credentials_file.exists(), 'Incomplete private configuration; inspect before continuing'
    print('Existing private configuration preserved')
else:
    email = 'admin-' + secrets.token_hex(3) + '@yunacelisse.space'
    password = secrets.token_urlsafe(30)
    values = {
        'POSTGRES_PASSWORD': secrets.token_hex(32),
        'REDIS_PASSWORD': secrets.token_hex(32),
        'ADMIN_EMAIL': email,
        'ADMIN_PASSWORD': password,
        'JWT_SECRET': secrets.token_hex(32),
        'TOTP_ENCRYPTION_KEY': secrets.token_hex(32),
        'SERVER_FRONTEND_URL': 'https://apihk.yunacelisse.space',
    }
    env.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
    env.chmod(0o600)
    credentials_file.write_text(json.dumps({'url': values['SERVER_FRONTEND_URL'], 'email': email, 'password': password}, indent=2) + '\n')
    credentials_file.chmod(0o600)
    print('Private database, Redis, JWT, encryption and administrator credentials created')
