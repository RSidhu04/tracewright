# Security model

Tracewright is a single-workspace, production-style demonstration. All run/baseline/comparison API calls require a shared bearer token. Treat that token as full read/write access. It is not SSO, RBAC, or tenant isolation. The dashboard stores its token only in page memory and inserts evidence as text, not HTML. Use TLS for remote access; local Compose binds to loopback only.

Redaction covers sensitive dictionary-key patterns, email addresses, bearer strings, `sk-` keys, and configured exact secret values. It occurs at trace emission and before persistence. Assertions run on raw values in memory. Exception messages and validation inputs are omitted from responses. These rules can miss arbitrary PII/credentials and over-redact useful evidence. Review exported artifacts. Do not place secrets in identifiers, suite metadata, or source fixtures. Database administrators and filesystem owners can access stored data.

The CLI starts a fresh process per trial and enforces a wall-clock timeout. POSIX timeout cleanup kills the process group. This is not a malicious-code sandbox: agents inherit process permissions/environment and can read files, access the network, exhaust memory, or deliberately escape. stdout/stderr suppression is protocol hygiene, not a confidentiality guarantee against hostile agents. Run only trusted agents; use hardened external sandboxes for untrusted SWE-bench patches.

The web API never imports or executes uploaded code. Its body-size and record limits do not replace edge rate limits or total-storage quotas. Real deployment requires TLS, upstream request timeouts/rate limits, monitored backups, credential rotation, and an access-control review. No vulnerability audit or penetration test is claimed.

Report sensitive vulnerabilities privately to the repository owner, not in a public issue with real credentials.
