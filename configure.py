#!/usr/bin/env python3
"""Provision private standard-mode groups only after the owner accepts app terms."""
import argparse
import json
import os
from pathlib import Path
import secrets

import requests

BASE_URL = 'http://127.0.0.1:8092/api/v1'


def api(session, method, path, payload=None):
    response = session.request(method, BASE_URL + path, json=payload, timeout=60)
    body = response.json()
    if response.status_code >= 400 or body.get('code') != 0:
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}, code={body.get("code")}, message={body.get("message", "")}')
    return body.get('data')


def login(credentials):
    session = requests.Session()
    session.headers['Origin'] = credentials['url']
    result = api(session, 'POST', '/auth/login', {k: credentials[k] for k in ('email', 'password')})
    session.headers['Authorization'] = 'Bearer ' + result['access_token']
    return session


def items(data):
    return data if isinstance(data, list) else data.get('items', [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    admin = json.loads(Path('/root/sub2api-admin.json').read_text())
    session = login(admin)
    status = api(session, 'GET', '/admin/compliance')
    if status['required']:
        print('Administrator login verified. Owner must review and acknowledge deployment terms in the web UI before provisioning. No acceptance was submitted.')
        return
    print('Administrator deployment acknowledgement is present')
    if not args.apply:
        return
    api(session, 'PUT', '/admin/settings', {'registration_enabled': False, 'frontend_url': admin['url'], 'site_name': 'Sub2API'})
    groups = items(api(session, 'GET', '/admin/groups?page=1&page_size=100'))
    group_ids = {}
    for platform, name in [('anthropic', 'Claude Subscription'), ('openai', 'OpenAI Subscription')]:
        group = next((g for g in groups if g['name'] == name), None)
        if group is None:
            group = api(session, 'POST', '/admin/groups', {
                'name': name,
                'description': 'Private personal subscription accounts; authorization pending owner action.',
                'platform': platform,
                'rate_multiplier': 1,
                'is_exclusive': True,
                'subscription_type': 'standard',
                'rpm_limit': 30,
            })
        group_ids[platform] = group['id']
    credentials_file = Path('/root/sub2api-user.json')
    if credentials_file.exists():
        user_credentials = json.loads(credentials_file.read_text())
    else:
        user_credentials = {
            'url': admin['url'],
            'email': 'user-' + secrets.token_hex(3) + '@yunacelisse.space',
            'password': secrets.token_urlsafe(30),
            'api_keys': {},
        }
        credentials_file.write_text(json.dumps(user_credentials, indent=2) + '\n')
    users = items(api(session, 'GET', '/admin/users?page=1&page_size=100'))
    user = next((u for u in users if u['email'] == user_credentials['email']), None)
    if user is None:
        user = api(session, 'POST', '/admin/users', {
            'email': user_credentials['email'],
            'password': user_credentials['password'],
            'username': 'Personal',
            'notes': 'Personal account; 1000 internal bookkeeping credits, no payment received.',
            'role': 'user',
            'balance': 1000,
            'concurrency': 2,
            'rpm_limit': 30,
            'allowed_groups': list(group_ids.values()),
            'restrict_public_groups': True,
        })
    user_session = login(user_credentials)
    existing = items(api(user_session, 'GET', '/keys?page=1&page_size=100'))
    for platform, group_id in group_ids.items():
        name = 'Personal ' + platform
        key = next((k for k in existing if k['name'] == name), None)
        if key is None:
            key = api(user_session, 'POST', '/keys', {'name': name, 'group_id': group_id})
        user_credentials['api_keys'][platform] = {'group_id': group_id, 'id': key['id'], 'key': key['key']}
    credentials_file.write_text(json.dumps(user_credentials, indent=2) + '\n')
    credentials_file.chmod(0o600)
    print('Registration disabled; private Claude/OpenAI groups, personal user and two API keys configured. Credentials saved privately. Subscription authorization remains owner-operated.')


if __name__ == '__main__':
    main()
