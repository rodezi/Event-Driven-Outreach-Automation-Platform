# Security Notes

This repository was refactored for public publication. During the review, local development artifacts indicated that sensitive credentials may have existed outside version-controlled source files, including:

- EasyBroker API credentials
- Resend API credentials
- Resend webhook signing secret
- Google Sheets spreadsheet identifiers
- Google service account JSON credentials

Recommended actions:

1. Rotate any EasyBroker, Resend, and Google credentials previously used by this project.
2. Replace webhook signing secrets after redeploying the webhook service.
3. Audit GitHub Actions secrets and Railway variables to confirm they match the rotated values.
4. Review who had access to any shared Google Sheet or service account key files.

Important:

- Removing a secret from the latest commit does not remove it from Git history.
- If a secret was ever committed, use a history-rewrite tool such as `git filter-repo` or BFG Repo-Cleaner, then force-push the cleaned history and rotate the exposed credential.

Suggested cleanup commands:

```bash
pipx run git-filter-repo --path .env --invert-paths
pipx run git-filter-repo --path-glob '*.json' --invert-paths
```
