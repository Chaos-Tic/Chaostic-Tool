"""Shared execution-pipeline mechanics for the CLI and desktop presenters.

Both adapters -- ``core.executor`` (the Rich/TUI capture) and ``desktop.process``
(the Qt ``Runner``) -- wrap ``core.runner.Runner`` and turn the child's raw byte
stream into masked, journaled, displayable output with identical redaction
semantics:

* a secret split across read chunks is still masked (byte-level, before any
  decoding, so a multibyte split is handled too);
* the ``keep``-byte tail the redactor holds back is flushed exactly once at the
  end, so a secret completing in the final chunk is not leaked or dropped;
* a secret submitted interactively is registered before the child can echo it;
* redaction always precedes every sink (disk journal and live display).

``RunSession`` owns that byte-level discipline: the ``StreamRedactor``, a lock
that orders redaction against the sink and against a secret registered from
another thread, a single final flush, and one incremental UTF-8 ``replace``
decoder. The presenters keep their own ``Runner`` lifecycle, journal shape (the
CLI journals decoded text; the desktop journals raw redacted bytes) and display
bounding, and plug those in through the output sink. The ``final`` flag lets a
sink finalise its decoder on the flush call.
"""
from __future__ import annotations

import codecs
import threading
from collections.abc import Callable, Iterable

from core.redaction import StreamRedactor

# Called with already-redacted bytes; ``final`` marks the single closing flush.
OutputSink = Callable[[bytes, bool], None]


class RunSession:
    """Redaction, single final flush and incremental decoding for one run."""

    def __init__(self, redactions: Iterable[str] = (),
                 sink: OutputSink | None = None) -> None:
        self.redactor = StreamRedactor(redactions)
        self.sink = sink
        # Serialises the redactor and the sink against a concurrent tail reader
        # and against a secret registered on another thread (the Qt case).
        self.lock = threading.Lock()
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._flushed = False

    def feed(self, data: bytes) -> None:
        """Mask one chunk and route it to the sink, holding the lock across both
        so no reader or ``add_secret`` can interleave a half-written chunk."""
        with self.lock:
            redacted = self.redactor.feed(data)
            if self.sink is not None:
                self.sink(redacted, False)

    def flush(self) -> None:
        """Release the redactor's retained tail to the sink exactly once."""
        with self.lock:
            if self._flushed:
                return
            self._flushed = True
            redacted = self.redactor.feed(b"", final=True)
            if self.sink is not None:
                self.sink(redacted, True)

    def add_secret(self, secret: str) -> None:
        """Register a secret under the lock so an immediate echo on another
        thread is masked: the registration happens-before the next ``feed``."""
        with self.lock:
            self.redactor.add(secret)

    def decode(self, data: bytes, final: bool = False) -> str:
        """Incrementally decode bytes as UTF-8, replacing invalid sequences.

        A multibyte code point split across calls is carried to the next one.
        The CLI decodes the redacted stream before journaling it; the desktop
        decodes the already-persisted log for display only."""
        return self._decoder.decode(data, final=final)

    def reset_decoder(self) -> None:
        """Drop any pending partial code point (used at a display seam)."""
        self._decoder.reset()
