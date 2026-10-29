# Security boundary

Run only trusted Python agents and suites in a local development environment. Agents run with the invoking user's permissions and can read files, print secrets, use the network, hang, or exhaust resources. Tracewright does not sandbox them. Use CI's job timeout as an outer bound; it is not per-case isolation.

Bind the API to loopback. It has no authentication and returns stored redacted outputs. Redaction is best effort; review artifacts before sharing, configure exact secrets with `--secret-env`, and avoid sensitive source fixtures. Inputs used as tool event data are retained after redaction. Arbitrary unrecognized credentials and personal data can remain. The database uses normal filesystem permissions, so choose a protected directory. Do not upload real databases as CI artifacts.

Do not paste real secrets into public issues. This project has no hosted security-reporting contact yet; contact your repository maintainer privately when deploying a fork.
