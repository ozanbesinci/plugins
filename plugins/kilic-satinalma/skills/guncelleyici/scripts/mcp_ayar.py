"""Preserve MCP configuration; change only the managed executable path.

Python 3.11+ stdlib only. No package installation. Never calls accept_eula.
Callers must arrange a maintenance window and ensure clients are closed.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import sys
import tomllib

from islem_guvencesi import SafetyError, config_transaction, redact

NAME = "powerbi-modeling"
HEADER = re.compile(r'^\s*\[\s*mcp_servers\.(?:powerbi-modeling|"powerbi-modeling"|\x27powerbi-modeling\x27)\s*\]\s*(?:#.*)?$')


def decode(data):
    return data.decode("utf-8-sig")


def validate_codex(data):
    obj = tomllib.loads(decode(data))
    if not isinstance(obj, dict):
        raise SafetyError("TOML nesnesi gerekli.")
    return obj


def safe_executable(executable):
    path = str(executable)
    if not path or any(ord(c) < 32 for c in path):
        raise SafetyError("Sunucu yolu geçersiz.")
    return path


def update_codex(data, executable):
    executable = safe_executable(executable)
    text = decode(data)
    before = validate_codex(data)
    servers = before.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise SafetyError("mcp_servers tablosu geçersiz.")
    entry = servers.get(NAME)
    nl = "\r\n" if "\r\n" in text else "\n"
    encoded_path = json.dumps(executable, ensure_ascii=False)
    if entry is None:
        # Ambiguous quoted/inline shapes are rejected instead of being rewritten.
        if NAME in text:
            raise SafetyError("Sunucu adı farklı biçimde mevcut; otomatik ekleme yapılmadı.")
        block = f'[mcp_servers.{NAME}]{nl}command = {encoded_path}{nl}args = ["--start"]{nl}startup_timeout_sec = 60{nl}'
        out = text.rstrip("\r\n") + (nl + nl if text.strip() else "") + block
    else:
        if not isinstance(entry, dict) or entry.get("url") or entry.get("args") != ["--start"]:
            raise SafetyError("Özel/uzak MCP komutu var; mevcut ayarlar değiştirilmedi.")
        if not isinstance(entry.get("command"), str):
            raise SafetyError("Geçerli MCP command alanı yok.")
        lines = text.splitlines(keepends=True)
        heads = [i for i, line in enumerate(lines) if HEADER.fullmatch(line.rstrip("\r\n"))]
        if len(heads) != 1:
            raise SafetyError("Tek ve açık bir MCP tablosu gerekli; farklı TOML biçimi korunuyor.")
        start = heads[0]
        stop = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
        command_lines = [i for i in range(start + 1, stop) if re.match(r'^\s*command\s*=', lines[i])]
        if len(command_lines) != 1:
            raise SafetyError("command alanı güvenle eşleştirilemedi.")
        i = command_lines[0]
        # Only simple single-line values are changed. Multiline/quoted-key variants remain untouched.
        if not re.fullmatch(r'\s*command\s*=\s*(?:"(?:[^"\\\r\n]|\\.)*"|\x27[^\x27\r\n]*\x27)\s*(?:#.*)?', lines[i].rstrip("\r\n")):
            raise SafetyError("Çok satırlı/özel command alanı otomatik değiştirilmez.")
        ending = "\r\n" if lines[i].endswith("\r\n") else "\n" if lines[i].endswith("\n") else ""
        indent = re.match(r'^\s*', lines[i]).group(0)
        suffix_match = re.fullmatch(r'\s*command\s*=\s*(?:"(?:[^"\\\r\n]|\\.)*"|\x27[^\x27\r\n]*\x27)(\s*(?:#.*)?)', lines[i].rstrip("\r\n"))
        suffix = suffix_match.group(1) if suffix_match else ""
        lines[i] = indent + "command = " + encoded_path + suffix + ending
        out = "".join(lines)
    result = out.encode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8")
    after = validate_codex(result)
    expected = copy.deepcopy(before)
    expected.setdefault("mcp_servers", {})
    if entry is None:
        expected["mcp_servers"][NAME] = {"command": executable, "args": ["--start"], "startup_timeout_sec": 60}
    else:
        expected["mcp_servers"][NAME]["command"] = executable
    if after != expected:
        raise SafetyError("TOML değişikliği yönetilen command alanını aştı.")
    return result


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out: raise SafetyError("Yinelenen JSON anahtarı; dosya değiştirilmedi.")
        out[key] = value
    return out


def validate_desktop(data):
    obj = json.loads(decode(data), object_pairs_hook=_unique_object)
    if not isinstance(obj, dict):
        raise SafetyError("İstemci JSON nesnesi gerekli.")
    return obj


def update_desktop(data, executable):
    executable = safe_executable(executable)
    obj = validate_desktop(data) if data.strip() else {}
    servers = obj.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise SafetyError("mcpServers nesnesi geçersiz.")
    entry = servers.get(NAME)
    if entry is not None:
        if (not isinstance(entry, dict) or entry.get("args") != ["--start"]
                or entry.get("url") or entry.get("type", "stdio") != "stdio"):
            raise SafetyError("Özel/uzak MCP kaydı korunuyor; otomatik değişiklik yapılmadı.")
        entry["command"] = executable  # Keep env, timeouts, permissions and unknown fields.
    else:
        servers[NAME] = {"command": executable, "args": ["--start"]}
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kind", choices=("codex", "desktop"))
    ap.add_argument("--path", type=Path, required=True)
    ap.add_argument("--exe", required=True)
    ap.add_argument("--clients-closed", action="store_true")
    args = ap.parse_args()
    try:
        if not args.clients_closed:
            raise SafetyError("Ayar değişimi için ilgili istemcilerin kapalı olduğu doğrulanmalı.")
        transform, validator = (update_codex, validate_codex) if args.kind == "codex" else (update_desktop, validate_desktop)
        result = config_transaction(args.path, lambda raw: transform(raw, args.exe), validator)
        print(json.dumps(redact(result), ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": redact(str(exc))}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())