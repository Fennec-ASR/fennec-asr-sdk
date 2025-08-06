# Security Policy

We take the security of Fennec ASR and its users seriously. If you believe you’ve found a vulnerability, please follow the guidelines below.

## Supported Versions

This SDK tracks the latest minor release. We generally fix security issues on the current major/minor version and publish a patch release.

| Version | Supported |
|--------:|:---------:|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

- **Email:** security@fennec-asr.com  
- **Subject:** `[Security][fennec-asr] <short summary>`
- Please include:
  - A clear description of the issue and potential impact.
  - Steps to reproduce / proof of concept.
  - Any logs, stack traces, or screenshots that help us understand the problem.
  - Your environment (OS, Python version, SDK version).

**Please do not** open public GitHub issues for security reports.

## Coordinated Disclosure

We aim to acknowledge reports within **3 business days**, provide a status update within **7 business days**, and work with you on a coordinated disclosure timeline. We appreciate responsible disclosure and will credit reporters if desired.

## Out of Scope

- Vulnerabilities requiring physical access to a device.
- Social engineering or phishing.
- Denial of Service from unreasonable traffic volumes.
- Issues in **third-party dependencies** not maintained by us (please report upstream).

## Data & Keys

Never include real API keys or live user data in your report. If needed, redact sensitive values (e.g., `sk_***`).

## Legal

We will not pursue legal action for good-faith, responsible security research that respects this policy and applicable laws.
