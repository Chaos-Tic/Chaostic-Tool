# Henon export — feed the attack-path engine

[Henon](https://github.com/Chaos-Tic) is a separate offensive attack-path
engine: it ingests reconnaissance and builds an exploitation graph. ChaosticTool
is **step 1** (recon); Henon is **step 2** (analysis). The two tools stay fully
decoupled — **no build dependency, no shared library, no network call** — and
exchange exactly one thing: a versioned JSON file on disk.

```text
ChaosticTool  ──recon.json──▶  Henon
  (recon)                       (exploitation graph + attack paths)
```

ChaosticTool emits the file; Henon reads it with:

```bash
henon --engagement engagement.toml ingest chaostictool recon.json
henon -e engagement.toml infer
henon -e engagement.toml path --profile stealth
```

The emitted shape is the authoritative contract, maintained in the Henon
repository (`docs/CONTRACT-CHAOSTICTOOL.md`, `docs/CONTRACT-CLOUD.md`):

```jsonc
{
  "schema_version": 1,          // the only required field
  "assets":          [ … ],     // domains / subdomains / IPs
  "services":        [ … ],     // listening host:port + service
  "web_endpoints":   [ … ],     // concrete HTTP(S) entry points
  "cloud_resources": [ … ]      // IAM roles, buckets, metadata, …
}
```

Every collection is optional, unknown fields are tolerated, and a malformed
record is skipped individually — so the file keeps working as either tool
evolves, as long as `schema_version` matches.

## How to export

The export never launches a scan and **never needs root**: it maps the results
ChaosticTool already saved for a target (`<data_home>/targets/<name>/`), the same
tree the mission report reads.

**From the CLI, non-interactively** (scriptable):

```bash
chaostictool --export-henon example.com
chaostictool --export-henon https://example.com:8443 -o /tmp/recon.json
```

It writes `recon.json` into the target's results folder (or the path given with
`-o`) and prints a one-line summary of what was mapped.

**From the interactive TUI**: open **Results & Session** (menu entry `11`) and
press `h` (*export for Henon*). The file lands next to the other results.

## What maps to what

| ChaosticTool recon                                   | Contract collection |
|------------------------------------------------------|---------------------|
| base target, `subfinder`/`amass`, `dig` A records, subdomain scope | `assets` (`domain` / `subdomain` / `ip`) |
| `nmap` / `rustscan` / `naabu` / `masscan` open ports | `services` (host, port, proto, service, product, version) |
| `httpx` probes, `gau` / `waybackurls` / `katana` URLs | `web_endpoints` |
| `nuclei` findings (CVE ids, template tags)           | `web_endpoints[].cve` / `interesting` |
| an operator-provided `cloud*.json` (CONTRACT-CLOUD shape) placed in the target tree | `cloud_resources` |

ChaosticTool has no built-in cloud enumerator yet; to populate
`cloud_resources`, drop a small projection of your cloud scan
(ScoutSuite/Prowler/…) following the Henon cloud contract into the target's
results folder as a `cloud*.json` file, and it is merged into the export.

## Secrets are never exported

`web_endpoints` URLs are **sanitised before storage**: embedded credentials
(userinfo), query *values* and fragments are dropped. Only the query parameter
*names* survive (Henon uses them to drive its SSRF inference). A secret captured
in a crawled URL therefore never reaches the exchange file.

## Engine

The mapping lives in [`core/henon_export.py`](../core/henon_export.py): a pure,
dependency-free module (stdlib only), with tolerant parsers for the text
ChaosticTool's tools actually produce. Its contract conformance is covered by
[`tests/test_henon_export.py`](../tests/test_henon_export.py).
