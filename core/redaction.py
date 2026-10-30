"""UI-independent helpers for masking secrets in commands and streamed output."""
from __future__ import annotations

from collections.abc import Iterable

SECRET_FIELDS = frozenset({"passwd", "cookie", "api_key"})


def secrets_for(values: dict[str, str], field_names: Iterable[str]) -> list[str]:
    """Return non-empty secret values for the named fields."""
    return [values[name] for name in field_names
            if name in SECRET_FIELDS and values.get(name)]


def redact(text: str, secrets: Iterable[str], replacement: str = "[redacted]") -> str:
    """Replace secrets longest-first so overlapping values remain masked."""
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            text = text.replace(secret, replacement)
    return text


class StreamRedactor:
    """Mask byte sequences even when a secret is split across output chunks."""

    def __init__(self, secrets: Iterable[str] = (), replacement: bytes = b"[masque]") -> None:
        self.secrets = sorted({secret.encode("utf-8") for secret in secrets if secret},
                              key=len, reverse=True)
        self.replacement = replacement
        self.buffer = b""
        self.keep = max((len(secret) for secret in self.secrets), default=1) - 1

    def add(self, secret: str) -> None:
        """Register a secret before a process can echo newly submitted input."""
        encoded = secret.encode("utf-8")
        if not encoded or encoded in self.secrets:
            return
        self.secrets.append(encoded)
        self.secrets.sort(key=len, reverse=True)
        self.keep = max(self.keep, len(encoded) - 1)

    def feed(self, data: bytes, final: bool = False) -> bytes:
        if not self.secrets and not self.buffer:
            return data
        self.buffer += data
        cutoff = len(self.buffer) if final else max(0, len(self.buffer) - self.keep)
        output = bytearray()
        index = 0
        while index < cutoff:
            match = next((secret for secret in self.secrets
                          if self.buffer.startswith(secret, index)), None)
            if match:
                output.extend(self.replacement)
                index += len(match)
            else:
                output.append(self.buffer[index])
                index += 1
        self.buffer = self.buffer[index:]
        return bytes(output)
