# Maintainer SSH signing keys

This file is the public record of SSH signing keys used by Efterlev maintainers to sign commits and release tags on `main`. It exists so anyone can verify that a commit or tag was produced by a legitimate maintainer's key — independent of GitHub's UI.

- **Format:** SSH public-key format, one maintainer per section, with GitHub handle and key fingerprint.
- **Why SSH, not GPG:** Git 2.34+ supports SSH signing natively; the same key used for `git push` authentication can sign commits; no separate key-management story. Simpler, newer, equivalent security.
- **Why public halves are recorded here, not only on GitHub profiles:** a transparent repo-level record means verification doesn't depend on GitHub API availability or profile-page state. This file is itself signed into `main` via the signing policy.

## How to use this file

Verify a commit:

```bash
git log --show-signature -1 <commit-sha>
```

Git compares the signature against your locally-configured allowed-signers file. Populate it from this file's SSH public-key lines plus the corresponding GitHub handle as the signer identity:

```bash
# Example: configure git to trust the maintainers in this file
git config --local gpg.ssh.allowedSignersFile .github/allowed-signers
```

An `.github/allowed-signers` file is generated at maintainer-onboarding time from the keys below; see "Key rotation and onboarding" for the procedure.

---

## Active maintainer keys

### @lhassa8 (BDFL)

- **Role:** BDFL (see [GOVERNANCE.md](../GOVERNANCE.md))
- **Since:** 2026-04-26
- **Fingerprint:** `SHA256:WmM2DTKXbVq8E+hq1kYumoFw7q9To8gUeMsSg8k2SJU`
- **Algorithm:** Ed25519
- **Public key:**

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMyb5ZmtCMcuo4D1LQODLpkwOXeqUgRcZjWmvMwnpP7U efterlev-git-signing
```

Registered as a GitHub **Signing Key** (separate from Authentication Keys) on the BDFL's account, scoped to commit signing only. The same public-key line lives at `https://github.com/lhassa8.gpg` (yes, GitHub serves SSH signing keys at the `.gpg` URL — historical naming).

Locally configured per-repo (not global) via `git config --local`: `gpg.format ssh`, `user.signingkey ~/.ssh/efterlev_signing.pub`, `commit.gpgsign true`, `tag.gpgsign true`. See PR #12 for the first signed commit on the post-rename, post-branch-protection repo — validates the end-to-end flow.

---

## Key rotation and onboarding

### When to rotate a key

- The private half is lost or suspected compromised.
- The maintainer is moving to a new primary machine and wants a clean break.
- More than 3 years have passed since the key was generated (Ed25519 has no practical expiry but fresh keys are inexpensive hygiene).

### How to rotate

1. Generate a new Ed25519 signing key (see inline instructions above).
2. Open a PR updating this file with a new section for the new key, marked `Since: <YYYY-MM>`. The old key's section gets moved to "Retired maintainer keys" below with `Retired: <YYYY-MM>`.
3. The PR is signed with the **old** key (proves the rotation comes from the same maintainer) OR, if the old key is lost, with the maintainer's GitHub-account authority (rare path, documented in the PR body).
4. The PR is merged by the BDFL or, for the BDFL's own rotation, by a co-maintainer. In the BDFL era with no co-maintainers, the BDFL merges their own PR with a `DECISIONS.md` entry recording the rotation.

### Maintainer onboarding

When a new maintainer is invited per GOVERNANCE.md:

1. The invited contributor generates an Ed25519 signing key and registers its public half on their GitHub profile as a signing key.
2. They open a PR adding their section to "Active maintainer keys" above, signed with the new key.
3. The BDFL reviews and merges.
4. `.github/CODEOWNERS` gains their handle for the relevant areas of ownership.

### Retired maintainer keys

_None yet._

<!-- When a key is retired, move it below with format:

### @handle (role during tenure)

- **Role:** <role>
- **Since / Retired:** <YYYY-MM> — <YYYY-MM>
- **Fingerprint:** `<fingerprint>`
- **Reason for retirement:** <rotation | resignation | compromise>

Retired sections are never deleted. A commit signed by a retired key
before retirement is still valid; verifiability requires the historical
public half to remain on record.
-->
