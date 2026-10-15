"""Stdlib-only vendor verification BEFORE loading any vendor helper.

An optional out-of-package manifest digest provides a pinned trust input.
Self-consistency alone does not authenticate a publisher or isolate the OS user.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


class BootstrapIntegrityError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise BootstrapIntegrityError('Duplicate manifest key')
        result[name] = value
    return result


def _plain(path, root):
    for node in [path, *path.parents]:
        if node.exists() or node.is_symlink():
            info = node.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise BootstrapIntegrityError('Vendor reparse/symlink path rejected')
        if node == root:
            break
    if not path.resolve().is_relative_to(root.resolve()):
        raise BootstrapIntegrityError('Vendor file outside fixed package root')


def verify_vendor(root, expected_manifest_digest=None):
    root = Path(root).absolute()
    _plain(root, root)
    manifest_path = root/'MANIFEST.sha256.json'
    _plain(manifest_path, root)
    raw = manifest_path.read_bytes()
    if len(raw) > 65536:
        raise BootstrapIntegrityError('Vendor manifest exceeds bound')
    actual_digest = hashlib.sha256(raw).hexdigest()
    if expected_manifest_digest is not None:
        if not re.fullmatch('[a-f0-9]{64}', expected_manifest_digest) or actual_digest != expected_manifest_digest:
            raise BootstrapIntegrityError('External vendor manifest digest mismatch')
    manifest = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique)
    if manifest.get('schema') != 'guncelleyici-source-manifest/v1' or manifest.get('version') != '2.3.0':
        raise BootstrapIntegrityError('Vendor manifest version/schema mismatch')
    entries = manifest.get('files')
    if not isinstance(entries, dict) or len(entries) != 42:
        raise BootstrapIntegrityError('Closed vendor manifest requires exactly 42 entries')
    if len({name.casefold() for name in entries}) != len(entries):
        raise BootstrapIntegrityError('Case-insensitive vendor path collision')
    for name, expected in entries.items():
        if not isinstance(name, str) or '\\' in name or ':' in name or not name or name.startswith('/'):
            raise BootstrapIntegrityError('Invalid manifest path')
        relative = PurePosixPath(name)
        if any(part in {'.', '..'} for part in name.split('/')) or relative.is_absolute():
            raise BootstrapIntegrityError('Manifest path traversal rejected')
        if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
            raise BootstrapIntegrityError('Invalid vendor SHA256')
        path = root/name
        _plain(path, root)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise BootstrapIntegrityError('Vendor bytes do not match manifest')
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*')
              if path.is_file() and '__pycache__' not in path.parts and path.name != 'MANIFEST.sha256.json'}
    if actual != set(entries):
        raise BootstrapIntegrityError('Extra or missing vendor file')
    if (root/'VERSION').read_text().strip() != '2.3.0':
        raise BootstrapIntegrityError('Vendor VERSION mismatch')
    return {'manifest_sha256': actual_digest, 'files_verified': 42,
            'trust': 'EXTERNAL_PIN_MATCHED' if expected_manifest_digest else 'PACKAGE_SELF_CONSISTENCY_ONLY',
            'corporate_authority': 'NOT_VERIFIED'}
