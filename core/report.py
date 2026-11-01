"""Mission report engine shared by the CLI and the desktop application.

Pure data in, text or bytes out: no Rich, no Qt, no third-party module. Both
front-ends feed the same ``MissionReport`` and get byte-identical Markdown,
plain-text, PDF and structured JSON renderings for the same data. The PDF is written by a small
built-in writer (Courier, paginated); the project keeps its runtime
dependency-free, so no PDF library is required.

Commands and logs reach this module already redacted by the run layer
(``core.redaction`` / ``RunSession``); nothing here re-reads secrets.
"""
from __future__ import annotations

import json
import re
import shlex
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.version import VERSION

FORMATS = ("md", "txt", "pdf", "json")
EXCERPT_LINES = 40
EXCERPT_WIDTH = 160
MAX_LISTED_SUBDOMAINS = 50

# Status keys as stored by the desktop ``run.json`` records, plus ``recorded``
# for CLI result files (the CLI keeps outputs, not exit codes).
STATUS_ORDER = ("success", "failed", "cancelled", "interrupted", "running", "recorded", "unknown")
STATUS_LABELS = {"success": "Completed", "failed": "Failed", "cancelled": "Stopped",
                 "interrupted": "Interrupted", "running": "Running", "recorded": "Recorded",
                 "unknown": "Unknown"}
ATTENTION = ("failed", "interrupted", "cancelled")


@dataclass
class ReportRun:
    tool: str
    preset: str = ""
    command: str = ""      # already redacted, display form
    status: str = "unknown"
    started: str = ""      # ISO 8601
    finished: str = ""
    exit_code: int | None = None
    detail: str = ""
    log_path: str = ""
    excerpt: list[str] = field(default_factory=list)
    excerpt_more: int = 0  # lines not shown
    group: str = ""        # phase (CLI category) or flow name
    host: str = ""         # scope host when it differs from the base target

    def duration(self) -> str:
        a, b = _parse_time(self.started), _parse_time(self.finished)
        if a is None or b is None or b < a:
            return ""
        return format_duration((b - a).total_seconds())


@dataclass
class MissionReport:
    target: str                     # label shown in the title
    host: str = ""
    url: str = ""
    port: str = ""
    include_subdomains: bool = False
    subdomains: list[str] = field(default_factory=list)
    runs: list[ReportRun] = field(default_factory=list)
    generated: str = ""             # ISO 8601 UTC; filled at build time when empty
    version: str = VERSION
    source: str = ""                # where the data came from (results root / data root)

    def __post_init__(self):
        if not self.generated:
            self.generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for run in self.runs:
            key = run.status if run.status in STATUS_LABELS else "unknown"
            counts[key] = counts.get(key, 0) + 1
        return {k: counts[k] for k in STATUS_ORDER if k in counts}

    def scope_text(self) -> str:
        base = self.host or self.url or self.target or "undefined"
        if self.include_subdomains and self.subdomains:
            return f"{base} + {len(self.subdomains)} subdomain(s)"
        return f"{base} (base host only)"


# --------------------------------------------------------------------------- builders

def from_gui_history(target: dict | None, records: list[dict], excerpt_lines: int = EXCERPT_LINES,
                     source: str = "") -> MissionReport:
    """Report for one desktop target from ``Store.history()`` records.

    ``target`` is a desktop target dict (id/label/host/url/port/subdomains…);
    ``None`` selects the local operations (records without a target).
    """
    key = _gui_target_key(target)
    runs = []
    for rec in sorted((r for r in records if isinstance(r, dict)),
                      key=lambda r: (str(r.get("started", "")), str(r.get("id", "")))):
        rec_target = rec.get("flow_target") or rec.get("target") or {}
        if _gui_target_key(rec_target) != key:
            continue
        command = rec.get("command", "")
        if isinstance(command, (list, tuple)):
            command = shlex.join(str(a) for a in command)
        log = Path(rec["directory"]) / "output.txt" if rec.get("directory") else None
        excerpt, more = _excerpt(log, excerpt_lines) if log else ([], 0)
        host = (rec.get("target") or {}).get("host", "")
        runs.append(ReportRun(
            tool=str(rec.get("tool", "")), preset=str(rec.get("preset", "")), command=str(command),
            status=str(rec.get("status", "unknown")), started=str(rec.get("started", "")),
            finished=str(rec.get("finished", "")), exit_code=rec.get("exit_code"),
            detail=str(rec.get("detail", "") or ""), log_path=str(log) if log else "",
            excerpt=excerpt, excerpt_more=more, group=str(rec.get("flow_name", "") or ""),
            host=host if host and host != (target or {}).get("host", host) else ""))
    t = target or {}
    return MissionReport(
        target=t.get("label") or t.get("host") or "This computer",
        host=t.get("host", ""), url=t.get("url", ""), port=str(t.get("port", "") or ""),
        include_subdomains=bool(t.get("include_subdomains")), subdomains=list(t.get("subdomains", [])),
        runs=runs, source=source)


def from_cli_results(target_dir: Path, target: dict, scope: dict | None = None,
                     excerpt_lines: int = EXCERPT_LINES) -> MissionReport:
    """Report for the CLI results tree ``<data_home>/targets/<name>/<category>/*``.

    ``target`` is ``core.target.TARGET`` (host/url/port); ``scope`` is
    ``core.target.SCOPE``. Each saved file becomes one ``recorded`` run.
    """
    target_dir = Path(target_dir)
    scope = scope or {}
    safe = target_dir.name
    runs = []
    for cat in sorted(p for p in target_dir.iterdir() if p.is_dir()):
        for f in sorted(p for p in cat.glob("*") if p.is_file()):
            tool, host = _split_cli_name(f.stem, safe)
            try:
                stat = f.stat()
            except OSError:
                continue
            excerpt, more = _excerpt(f, excerpt_lines)
            runs.append(ReportRun(
                tool=tool, status="recorded",
                started=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                detail=f"{f.name} · {stat.st_size} bytes", log_path=str(f), excerpt=excerpt,
                excerpt_more=more, group=cat.name, host=host))
    subs = [s for s in scope.get("subdomains", []) if isinstance(s, str)]
    return MissionReport(
        target=target.get("host") or target.get("url") or safe, host=target.get("host", ""),
        url=target.get("url", ""), port=str(target.get("port", "") or ""),
        include_subdomains=bool(scope.get("include_subdomains")) and bool(subs), subdomains=subs,
        runs=runs, source=str(target_dir))


def _gui_target_key(target) -> str:
    target = target or {}
    return target.get("id") or target.get("url") or target.get("host") or "__local__"


def _split_cli_name(stem: str, safe_target: str) -> tuple[str, str]:
    """``<base>_<target>`` → (base, ""); ``<base>_<target>__<host>`` → (base, host)."""
    host = ""
    if "__" in stem:
        stem, host = stem.rsplit("__", 1)
    suffix = "_" + safe_target
    if stem.endswith(suffix) and len(stem) > len(suffix):
        stem = stem[:-len(suffix)]
    return stem or "result", host


def _excerpt(path: Path | None, limit: int) -> tuple[list[str], int]:
    if path is None or limit <= 0:
        return [], 0
    try:
        data = path.read_bytes()
    except OSError:
        return [], 0
    if b"\0" in data[:2048]:
        return ["[binary file, not shown]"], 0
    lines = data.decode("utf-8", errors="replace").splitlines()
    shown = [l[:EXCERPT_WIDTH] + ("…" if len(l) > EXCERPT_WIDTH else "") for l in lines[:limit]]
    return shown, max(0, len(lines) - limit)


def _parse_time(value: str):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def format_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.1f} s" if seconds < 10 else f"{int(round(seconds))} s"
    minutes, sec = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min {sec:02d} s"


def _stamp(value: str) -> str:
    dt = _parse_time(value)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if dt else (value or "—")


# --------------------------------------------------------------------------- document

def _blocks(report: MissionReport) -> list[tuple]:
    """Format-neutral document: (kind, payload) with kinds h1/h2/h3/p/kv/code/bullets."""
    doc: list[tuple] = [("h1", f"Mission report — {report.target}")]
    head = [("Target", report.target), ("Host", report.host or "—"), ("URL", report.url or "—"),
            ("Port", report.port or "—"), ("Scope", report.scope_text()),
            ("Generated", _stamp(report.generated)), ("Generator", f"ChaosticTool {report.version}"),
            ("Operations", str(len(report.runs)))]
    if report.source:
        head.append(("Data source", report.source))
    doc.append(("kv", head))
    if report.include_subdomains and report.subdomains:
        listed = report.subdomains[:MAX_LISTED_SUBDOMAINS]
        doc.append(("h3", "Subdomains in scope"))
        doc.append(("bullets", listed + ([f"… {len(report.subdomains) - len(listed)} more"]
                                         if len(report.subdomains) > len(listed) else [])))

    doc.append(("h2", "Summary"))
    counts = report.status_counts()
    kv = [(STATUS_LABELS[k], str(v)) for k, v in counts.items()] or [("Operations", "none recorded")]
    times = [t for t in (_parse_time(r.started) for r in report.runs) if t]
    ends = [t for t in (_parse_time(r.finished or r.started) for r in report.runs) if t]
    if times:
        kv.append(("First activity", _stamp(min(times).isoformat())))
        kv.append(("Last activity", _stamp(max(ends or times).isoformat())))
    tools = sorted({r.tool for r in report.runs if r.tool})
    if tools:
        kv.append(("Tools", ", ".join(tools)))
    groups = sorted({r.group for r in report.runs if r.group})
    if groups:
        kv.append(("Phases / flows", ", ".join(groups)))
    doc.append(("kv", kv))

    doc.append(("h2", "Operations"))
    if not report.runs:
        doc.append(("p", "No operation recorded for this target yet."))
    grouped: dict[str, list[ReportRun]] = {}
    for run in report.runs:
        grouped.setdefault(run.group, []).append(run)
    for group, runs in grouped.items():
        if group or len(grouped) > 1:
            doc.append(("h3", group or "Standalone operations"))
        for i, run in enumerate(runs, 1):
            title = run.tool + (f" — {run.preset}" if run.preset else "")
            if run.host:
                title += f" @ {run.host}"
            doc.append(("h3" if not group and len(grouped) == 1 else "h4", title))
            rows = [("Status", STATUS_LABELS.get(run.status, run.status or "unknown"))]
            if run.started:
                rows.append(("Started", _stamp(run.started)))
            if run.finished:
                rows.append(("Finished", _stamp(run.finished)))
            if (d := run.duration()):
                rows.append(("Duration", d))
            if run.exit_code is not None:
                rows.append(("Exit code", str(run.exit_code)))
            if run.command:
                rows.append(("Command", run.command))
            if run.log_path:
                rows.append(("Raw log", run.log_path))
            doc.append(("kv", rows))
            if run.detail:
                doc.append(("p", run.detail))
            if run.excerpt:
                tail = [f"… {run.excerpt_more} more line(s) in the raw log"] if run.excerpt_more else []
                doc.append(("code", run.excerpt + tail))
            elif run.log_path:
                doc.append(("p", "No output captured."))

    doc.append(("h2", "Findings"))
    attention = [r for r in report.runs if r.status in ATTENTION]
    if attention:
        doc.append(("p", "Operations requiring attention:"))
        doc.append(("bullets", [f"{r.tool}" + (f" — {r.preset}" if r.preset else "") +
                                f": {STATUS_LABELS.get(r.status, r.status)}" +
                                (f" ({r.detail})" if r.detail else "") for r in attention]))
    else:
        doc.append(("p", "No failed, stopped or interrupted operation."))
    doc.append(("p", "This report records what was run, when, and its outcome. Vulnerability "
                     "assessment is derived from the raw logs referenced above; no automatic "
                     "severity classification is made."))
    doc.append(("h2", "Scope statement"))
    doc.append(("p", f"Testing stayed within the declared scope: {report.scope_text()}. "
                     "No host outside this scope was targeted by the operations listed."))
    return doc


# --------------------------------------------------------------------------- renderers

def render_markdown(report: MissionReport) -> str:
    out: list[str] = []
    for kind, payload in _blocks(report):
        if kind in ("h1", "h2", "h3", "h4"):
            out += ["", "#" * int(kind[1]) + " " + payload, ""]
        elif kind == "p":
            out += [payload, ""]
        elif kind == "kv":
            out += [f"- **{k}:** {_md_inline(v)}" for k, v in payload] + [""]
        elif kind == "bullets":
            out += [f"- {_md_inline(v)}" for v in payload] + [""]
        elif kind == "code":
            out += ["```text"] + [l.replace("```", "'''") for l in payload] + ["```", ""]
    return "\n".join(out).strip("\n") + "\n"


def _md_inline(value: str) -> str:
    return f"`{value}`" if re.search(r"[\\/_*]", value) and " " not in value.strip() else value


def render_text(report: MissionReport, width: int = 80) -> str:
    out: list[str] = []
    for kind, payload in _blocks(report):
        if kind == "h1":
            out += ["=" * width, payload.upper(), "=" * width, ""]
        elif kind == "h2":
            out += [payload.upper(), "-" * len(payload), ""]
        elif kind in ("h3", "h4"):
            out += [("" if kind == "h3" else "  ") + payload, ""]
        elif kind == "p":
            out += _wrap(payload, width) + [""]
        elif kind == "kv":
            pad = max(len(k) for k, _ in payload) + 2
            for k, v in payload:
                lines = _wrap(v, width - pad) or [""]
                out.append(f"{k + ':':<{pad}}{lines[0]}")
                out += [" " * pad + l for l in lines[1:]]
            out.append("")
        elif kind == "bullets":
            for v in payload:
                lines = _wrap(v, width - 4) or [""]
                out.append("  * " + lines[0])
                out += ["    " + l for l in lines[1:]]
            out.append("")
        elif kind == "code":
            out += ["    " + l for l in payload] + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    lines: list[str] = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, width=max(20, width), break_long_words=True,
                               break_on_hyphens=False) or [""]
    return lines


# --------------------------------------------------------------------------- PDF writer

_PAGE_W, _PAGE_H, _MARGIN = 595, 842, 50          # A4, points
_STYLES = {"h1": ("F2", 16, 22), "h2": ("F2", 12.5, 18), "h3": ("F2", 10.5, 15), "h4": ("F2", 9.5, 13),
           "p": ("F1", 9, 12), "kv": ("F1", 9, 12), "bullets": ("F1", 9, 12), "code": ("F1", 7.8, 10)}


def render_pdf(report: MissionReport) -> bytes:
    """Typeset the report with the built-in writer: Courier, A4, paginated."""
    lines: list[tuple[str, float, float, str, float]] = []  # font, size, leading, text, x-offset
    gap = lambda n: lines.append(("F1", 9, n, "", 0))

    def emit(style, text, indent=0.0):
        font, size, lead = _STYLES[style]
        cols = int((_PAGE_W - 2 * _MARGIN - indent) / (size * 0.6))
        for l in _wrap(text, cols) or [""]:
            lines.append((font, size, lead, l, indent))

    for kind, payload in _blocks(report):
        if kind == "h1":
            emit("h1", payload); gap(6)
        elif kind == "h2":
            gap(10); emit("h2", payload); gap(4)
        elif kind in ("h3", "h4"):
            gap(5); emit(kind, payload); gap(2)
        elif kind == "p":
            emit("p", payload); gap(5)
        elif kind == "kv":
            pad = max(len(k) for k, _ in payload) + 2
            for k, v in payload:
                emit("kv", f"{k + ':':<{pad}}{v}")
            gap(5)
        elif kind == "bullets":
            for v in payload:
                emit("bullets", "* " + v, 10)
            gap(5)
        elif kind == "code":
            for l in payload:
                emit("code", l, 12)
            gap(5)

    pages: list[list[tuple]] = [[]]
    y = _PAGE_H - _MARGIN
    for item in lines:
        lead = item[2]
        if y - lead < _MARGIN + 20 and pages[-1]:
            pages.append([]); y = _PAGE_H - _MARGIN
        y -= lead
        pages[-1].append((item, y))
    footer = f"ChaosticTool {report.version} · {report.target}"
    return _pdf_document([_page_stream(items, footer, i + 1, len(pages)) for i, items in enumerate(pages)])


def _pdf_text(text: str) -> bytes:
    data = text.encode("cp1252", errors="replace")
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _page_stream(items, footer: str, number: int, total: int) -> bytes:
    parts = [b"BT"]
    for (font, size, _lead, text, indent), y in items:
        if text:
            parts.append(b"/%s %s Tf 1 0 0 1 %s %.1f Tm (%s) Tj" % (
                font.encode(), _num(size), _num(_MARGIN + indent), y, _pdf_text(text)))
    parts.append(b"/F1 7.5 Tf 1 0 0 1 %s 28 Tm (%s) Tj" % (_num(_MARGIN), _pdf_text(footer)))
    page_label = f"Page {number} / {total}"
    x = _PAGE_W - _MARGIN - len(page_label) * 7.5 * 0.6
    parts.append(b"1 0 0 1 %.1f 28 Tm (%s) Tj" % (x, _pdf_text(page_label)))
    parts.append(b"ET")
    return b"\n".join(parts)


def _num(value) -> bytes:
    return (f"{value:.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)).encode()


def _pdf_document(streams: list[bytes]) -> bytes:
    """Assemble a PDF 1.4 file: catalog, pages, Courier fonts, one Flate stream per page."""
    objects: list[bytes] = []  # index + 1 = object number
    add = lambda body: (objects.append(body), len(objects))[1]
    catalog = add(b"")  # placeholder, filled once the page tree id is known
    pages_id = add(b"")
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>")
    page_ids = []
    for stream in streams:
        data = zlib.compress(stream)
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream")
        page_ids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
                            b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>"
                            % (pages_id, _PAGE_W, _PAGE_H, content, f1, f2)))
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % i for i in page_ids), len(page_ids))
    info = add(b"<< /Producer (ChaosticTool %s) /Title (Mission report) >>" % _pdf_text(VERSION))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, catalog, info, xref))
    return bytes(out)


# --------------------------------------------------------------------------- JSON

JSON_SCHEMA_VERSION = 1


def to_dict(report: MissionReport) -> dict:
    """Machine-readable form of the report: header, summary, every run, findings."""
    runs = []
    for run in report.runs:
        data = asdict(run)
        data["status_label"] = STATUS_LABELS.get(run.status, run.status)
        data["duration"] = run.duration()
        runs.append(data)
    return {
        "schema": "chaostictool.mission-report", "schema_version": JSON_SCHEMA_VERSION,
        "generator": {"name": "ChaosticTool", "version": report.version},
        "generated": report.generated,
        "target": {"label": report.target, "host": report.host, "url": report.url, "port": report.port,
                   "include_subdomains": report.include_subdomains, "subdomains": list(report.subdomains),
                   "scope": report.scope_text()},
        "source": report.source,
        "summary": {"operations": len(report.runs), "status_counts": report.status_counts(),
                    "tools": sorted({r.tool for r in report.runs if r.tool}),
                    "groups": sorted({r.group for r in report.runs if r.group})},
        "operations": runs,
        "findings": {"attention": [{"tool": r.tool, "preset": r.preset, "status": r.status, "detail": r.detail}
                                   for r in report.runs if r.status in ATTENTION],
                     "scope_statement": f"Testing stayed within the declared scope: {report.scope_text()}."},
    }


def render_json(report: MissionReport) -> str:
    return json.dumps(to_dict(report), ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------------------- files

RENDERERS = {"md": render_markdown, "txt": render_text, "pdf": render_pdf, "json": render_json}


def render(report: MissionReport, fmt: str) -> str | bytes:
    fmt = fmt.lower().lstrip(".")
    if fmt not in RENDERERS:
        raise ValueError(f"Unsupported report format: {fmt} (expected one of {', '.join(FORMATS)})")
    return RENDERERS[fmt](report)


def default_filename(report: MissionReport, fmt: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", report.host or report.target or "local").strip("._") or "local"
    stamp = (_parse_time(report.generated) or datetime.now(timezone.utc)).strftime("%Y-%m-%d_%H-%M")
    return f"mission-report_{slug}_{stamp}.{fmt.lower().lstrip('.')}"


def write_report(report: MissionReport, path: Path | str, fmt: str | None = None) -> Path:
    """Write the report to ``path``; the format follows ``fmt`` or the file extension."""
    path = Path(path)
    fmt = (fmt or path.suffix.lstrip(".") or "md").lower()
    if not path.suffix:
        path = path.with_suffix("." + fmt)
    content = render(report, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path
