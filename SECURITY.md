# Security Policy for SNES Super Dragon's Lair Arcade

## Reporting a Vulnerability
If you discover a security issue in this project, please **do not** open a public issue. Instead, use [GitHub's private vulnerability reporting](https://github.com/astrobleem/SNES-SuperDragonsLairArcade/security/advisories/new) or contact the maintainer directly via GitHub.

We will acknowledge receipt within 48 hours, investigate the report, and work with you to resolve the issue. All communications will be kept confidential until a fix is released.

## Supported Versions
The project follows a **rolling release** model. Security fixes are applied to the `main` branch and any released tags. Users are encouraged to keep their forks up-to-date with the upstream repository.

## Security Best Practices
- **Run the tools on trusted input only.** The scripts in `tools/` process binary data; avoid feeding untrusted files without validation.
- **Use a supported Python 3 version.** The codebase requires Python 3.10+; older versions may lack security patches.
- **Validate external resources.** When the project interacts with external files or URLs, verify checksums or signatures where possible.
- **Enable linting and static analysis.** Run `flake8`, `bandit`, and `black` before committing changes.

## Disclosure Policy
We aim to disclose security fixes publicly within 90 days of a confirmed vulnerability, unless a longer embargo is required for critical issues. The release notes will include a summary of the fix and any migration steps.

---
*Last updated: 2026-02-12*
