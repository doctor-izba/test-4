"""Path-scoped tools; Linux shell uses a network-isolated bubblewrap sandbox."""
from pathlib import Path
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
import urllib.parse

SCHEMAS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a repository UTF-8 text file (bounded). Paths are relative to repository root.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a UTF-8 file in your owned directory. Paths are relative to repository root.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "shell", "description": "Run bash in your owned directory. Repository and OS are read-only except your directory; network is disabled. Commands are limited to 180 seconds. Dependencies are preinstalled. Do not run other API agents, inspect processes/secrets, or attempt privilege escalation.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "fetch_url", "description": "Download a public HTTPS source to your owned directory. No cookies, authentication, access-control bypass or paid APIs. Returns HTTP status, bytes, SHA256 and text preview when applicable.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "path": {"type": "string"}}, "required": ["url", "path"]}}},
]


def clean_environment(environ=None):
    environ = os.environ if environ is None else environ
    allowed = {"PATH", "LANG", "LC_ALL", "TZ", "TERM", "ELAN_HOME", "LEAN_PATH", "LEAN_NUM_THREADS", "LD_LIBRARY_PATH", "PYTHONPATH"}
    return {key: value for key, value in environ.items() if key in allowed}


def safe_public_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Only public unauthenticated HTTPS URLs are allowed")
    for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("Private/local network destinations are forbidden")
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Tools:
    def __init__(self, root, owned, redact=lambda value: value, require_sandbox=True):
        self.root = Path(root).resolve()
        self.owned = self.resolve(owned)
        self.owned.mkdir(parents=True, exist_ok=True)
        self.redact = redact
        self.require_sandbox = require_sandbox

    def resolve(self, path):
        candidate = (self.root / path).resolve()
        if not candidate.is_relative_to(self.root) or any(part in {".git", "output", ".env"} for part in candidate.relative_to(self.root).parts):
            raise ValueError("Path is outside permitted repository content")
        return candidate

    def write_path(self, path):
        candidate = self.resolve(path)
        if not candidate.is_relative_to(self.owned):
            raise ValueError("Writes must remain within your owned directory")
        return candidate

    def call(self, name, args):
        try:
            result = getattr(self, name)(**args) if name in {"read_file", "write_file", "shell", "fetch_url"} else {"error": "Unknown tool"}
        except Exception as error:
            result = {"error": type(error).__name__ + ": " + str(error)}
        return self.redact(json.dumps(result, ensure_ascii=False))[:24000]

    def read_file(self, path, offset=0, limit=16000):
        target = self.resolve(path)
        if not target.is_file() or target.stat().st_size > 5_000_000:
            raise ValueError("Not a readable text file, or file is over 5 MB")
        data = target.read_text(encoding="utf-8", errors="replace")
        offset = max(0, int(offset))
        return {"path": path, "total_characters": len(data), "content": data[offset:offset + max(1, min(int(limit), 20000))]}

    def write_file(self, path, content):
        target = self.write_path(path)
        if len(content.encode()) > 1_000_000:
            raise ValueError("Write exceeds 1 MB")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.redact(content), encoding="utf-8")
        return {"written": path, "characters": len(content)}

    def shell(self, command, timeout=90):
        timeout = max(1, min(int(timeout), 180))
        if len(command) > 20000:
            raise ValueError("Command is too long")
        # Defense in depth; OS namespace isolation enforces filesystem/network rules.
        if re.search(r"(/proc|/sys|sudo|nsenter|NUBE_API_KEY|GITHUB_TOKEN|GH_TOKEN|/dev/mem|harness/run\.py)", command, re.I):
            raise ValueError("Process/credential/privilege operations are not permitted")
        env = clean_environment()
        env.update({"HOME": str(self.owned / ".home"), "TMPDIR": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"})
        # Keep the preinstalled toolchains discoverable despite role-private HOME.
        env["ELAN_HOME"] = os.environ.get("ELAN_HOME", str(Path.home() / ".elan"))
        (self.owned / ".home").mkdir(exist_ok=True)
        executable = shutil.which("bwrap")
        if sys.platform == "linux" and executable:
            argv = [executable, "--die-with-parent", "--unshare-all", "--new-session",
                    "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
                    "--tmpfs", "/tmp", "--bind", str(self.owned), str(self.owned),
                    "--chdir", str(self.owned), "--", "/bin/bash", "--noprofile", "--norc", "-c", command]
        elif self.require_sandbox:
            raise RuntimeError("bubblewrap Linux sandbox is required; shell tool refused")
        else:
            # Unit tests only. Production caller never opts out.
            argv = [shutil.which("bash") or "bash", "--noprofile", "--norc", "-c", command]
        try:
            run = subprocess.run(argv, cwd=self.owned, env=env, text=True, errors="replace", stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=timeout)
            return {"exit_code": run.returncode, "output": self.redact(run.stdout)[-20000:]}
        except subprocess.TimeoutExpired as error:
            raw = error.stdout or b""
            if isinstance(raw, bytes):
                raw = raw.decode(errors="replace")
            return {"timeout": timeout, "output": self.redact(raw)[-20000:]}

    def fetch_url(self, url, path):
        import hashlib
        target = self.write_path(path)
        safe_public_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 RoboticsResearch/1.0", "Accept": "*/*"})
        opener = urllib.request.build_opener(CheckedRedirect())
        with opener.open(request, timeout=40) as response:
            safe_public_url(response.url)
            data = response.read(15_000_001)
            if len(data) > 15_000_000:
                raise ValueError("Source exceeds 15 MB limit")
            content_type = response.headers.get("Content-Type", "")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            result = {"path": path, "url": response.url, "http_status": response.status, "content_type": content_type,
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            if "text" in content_type or "json" in content_type:
                result["preview"] = data.decode(errors="replace")[:12000]
            return result
