"""Shared run-session pipeline: byte-level redaction invariants and the thin
mechanics (redact-before-sink, single final flush, locked secret registration,
incremental decoding) that the CLI and desktop presenters both consume.

The redaction-invariant cases are characterization tests: they pin behaviour of
the byte pipeline that was previously anchored only indirectly, and they hold
whether the logic lives in the two adapters or in the shared core.
"""
from __future__ import annotations

import unittest

from core.redaction import StreamRedactor
from core.run_session import RunSession


class RedactionInvariantTests(unittest.TestCase):
    """Byte-level guarantees the shared pipeline must preserve exactly."""

    def test_feed_masks_longest_of_nested_secrets_regardless_of_input_order(self):
        # "abc" is a prefix of "abcdef"; the longer secret must be replaced as a
        # whole so no "def" fragment survives, however the secrets were listed.
        for secrets in (["abcdef", "abc"], ["abc", "abcdef"]):
            with self.subTest(secrets=secrets):
                redactor = StreamRedactor(secrets)
                self.assertEqual(redactor.feed(b"x abcdef y", final=True),
                                 b"x [redacted] y")

    def test_feed_masks_nested_secret_split_across_chunks(self):
        # The longest-first match must still win when the secret is delivered in
        # two feeds that straddle the start of the value.
        redactor = StreamRedactor(["abcdef", "abc"])
        output = (redactor.feed(b"x ab") + redactor.feed(b"cdef y")
                  + redactor.feed(b"", final=True))
        self.assertEqual(output, b"x [redacted] y")

    def test_short_secret_inside_keep_tail_is_masked_only_by_final_flush(self):
        # keep = len(longest) - 1 = 13, so a 3-byte secret delivered as the last
        # bytes stays buffered; only the final flush scans and masks it.
        redactor = StreamRedactor(["x" * 14, "abc"])
        self.assertEqual(redactor.feed(b"abc"), b"")
        self.assertEqual(redactor.feed(b"", final=True), b"[redacted]")

    def test_trailing_incomplete_secret_prefix_is_emitted_literally(self):
        # A tail that is only a prefix of a secret (the completion never arrived)
        # must be flushed as-is: it was never the secret.
        redactor = StreamRedactor(["abcdef"])
        self.assertEqual(redactor.feed(b"xyabc"), b"")
        self.assertEqual(redactor.feed(b"", final=True), b"xyabc")

    def test_add_grows_keep_so_a_longer_secret_stays_buffered(self):
        # Registering a longer secret must widen the held-back tail so the new
        # value cannot slip out raw across a later chunk boundary.
        redactor = StreamRedactor(["abc"])
        self.assertEqual(redactor.keep, 2)
        redactor.add("abcdefgh")
        self.assertEqual(redactor.keep, 7)
        output = redactor.feed(b"zz abcde") + redactor.feed(b"fgh zz")
        self.assertEqual(output + redactor.feed(b"", final=True), b"zz [redacted] zz")

    def test_multibyte_secret_split_mid_codepoint_is_masked(self):
        # Redaction is byte-level and runs before any decoding, so a secret whose
        # UTF-8 bytes are split mid-codepoint is still masked in full.
        secret = "clé-€-secret"
        raw = secret.encode("utf-8")
        redactor = StreamRedactor([secret])
        output = redactor.feed(b"[" + raw[:5]) + redactor.feed(raw[5:] + b"]")
        self.assertEqual(output + redactor.feed(b"", final=True), b"[[redacted]]")


class RunSessionTests(unittest.TestCase):
    """The thin shared mechanics both presenters drive."""

    def test_feed_redacts_before_the_sink_and_flush_emits_the_tail_once(self):
        chunks = []
        session = RunSession(["secret-value"],
                             lambda data, final: chunks.append((data, final)))
        session.feed(b"before secret-")   # the registered value spans this split
        session.feed(b"value after")
        session.flush()
        session.flush()                   # a second flush must be a no-op
        joined = b"".join(data for data, _ in chunks)
        self.assertEqual(joined, b"before [redacted] after")
        self.assertNotIn(b"secret-value", joined)
        self.assertEqual([final for _, final in chunks], [False, False, True])

    def test_add_secret_before_feed_masks_an_immediate_echo(self):
        chunks = []
        session = RunSession(sink=lambda data, final: chunks.append(data))
        session.add_secret("live-secret")
        session.feed(b"echo: live-sec")
        session.feed(b"ret!")
        session.flush()
        self.assertEqual(b"".join(chunks), b"echo: [redacted]!")

    def test_decode_is_incremental_and_replaces_invalid_bytes(self):
        session = RunSession()
        euro = "€".encode()                                 # 3 bytes
        self.assertEqual(session.decode(euro[:2]), "")       # held: incomplete
        self.assertEqual(session.decode(euro[2:]), "€")      # completed
        self.assertEqual(session.decode(b"\xff"), "�")  # invalid -> U+FFFD

    def test_reset_decoder_drops_a_pending_partial_code_point(self):
        session = RunSession()
        self.assertEqual(session.decode("€".encode()[:2]), "")
        session.reset_decoder()
        self.assertEqual(session.decode(b"A"), "A")  # dangling bytes are dropped

    def test_cli_and_desktop_sink_styles_produce_identical_redacted_bytes(self):
        # Mini-parity at the unit level: the CLI journals decoded text and the
        # desktop journals raw redacted bytes, but the shared pipeline must mask
        # a secret split across the same chunk boundary identically for both.
        secret = "parity-secret"
        pieces = [b"head " + secret.encode()[:6], secret.encode()[6:] + b" tail"]

        cli = RunSession([secret])
        cli_text: list[str] = []
        cli.sink = lambda data, final: cli_text.append(cli.decode(data, final=final))
        for piece in pieces:
            cli.feed(piece)
        cli.flush()

        desktop = RunSession([secret])
        desktop_bytes = bytearray()
        desktop.sink = lambda data, final: desktop_bytes.extend(data)
        for piece in pieces:
            desktop.feed(piece)
        desktop.flush()

        self.assertEqual("".join(cli_text), "head [redacted] tail")
        self.assertEqual(bytes(desktop_bytes), b"head [redacted] tail")
        self.assertEqual("".join(cli_text), bytes(desktop_bytes).decode())
        self.assertNotIn(secret, "".join(cli_text))


if __name__ == "__main__":
    unittest.main()
