# Git Commit Signing Policy

## Overview
All commits, tags, and notes in this repository MUST be cryptographically signed and include the following trailer:

```
Signed-off-by: Lazarus Laboratories <ops@lazarus-labs.com>
```

## Setup Instructions

### 1. Initial Configuration
The repository has been pre-configured with the following settings:

```bash
# User information
git config user.name "Lazarus Laboratories"
git config user.email "ops@lazarus-labs.com"

# Enable commit signing
git config commit.gpgsign true

# Use commit template
git config commit.template .git-commit-template.txt

# Use custom hooks
git config core.hooksPath .githooks

# Require signed tags
git config tag.gpgSign true

# Require signed merges
git config merge.verifySignatures true
```

### 2. Signing Method Configuration

Choose ONE of the following signing methods:

#### Option A: SSH Signing (Git 2.34+ Required) - CURRENTLY CONFIGURED
```bash
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519.pub
```

To use a different SSH key:
```bash
git config user.signingkey ~/.ssh/YOUR_KEY.pub
```

#### Option B: GPG Signing
```bash
# Remove SSH configuration
git config --unset gpg.format

# Configure GPG
git config user.signingkey YOUR_GPG_KEY_ID
git config gpg.program gpg
```

To find your GPG key ID:
```bash
gpg --list-secret-keys --keyid-format=long
```

### 3. SSH Key Setup (if using SSH signing)

#### Generate a new SSH key (if needed):
```bash
ssh-keygen -t ed25519 -C "ops@lazarus-labs.com"
```

#### Add SSH key to allowed signers:
```bash
echo "ops@lazarus-labs.com $(cat ~/.ssh/id_ed25519.pub)" >> ~/.ssh/allowed_signers
git config gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
```

### 4. GPG Key Setup (if using GPG signing)

#### Generate a new GPG key (if needed):
```bash
gpg --full-generate-key
```

#### Export public key:
```bash
gpg --armor --export ops@lazarus-labs.com
```

## Usage Examples

### Signed Commits
All commits will automatically be signed with the `-S` flag enabled by default:

```bash
# Regular commit (automatically signed)
git commit -m "feat: Add new feature

Implements XYZ functionality

Signed-off-by: Lazarus Laboratories <ops@lazarus-labs.com>"

# Explicit signed commit
git commit -S -m "fix: Resolve critical bug

Fixes issue #123

Signed-off-by: Lazarus Laboratories <ops@lazarus-labs.com>"
```

### Signed Tags
```bash
# Create a signed tag
git tag -s v1.0.0 -m "Release version 1.0.0

Major features:
- Feature A
- Feature B

Signed-off-by: Lazarus Laboratories <ops@lazarus-labs.com>"

# Verify a signed tag
git tag -v v1.0.0
```

### Signed Merges
```bash
# Merge with signature verification
git merge --verify-signatures branch-name
```

## Hook Enforcement

### commit-msg Hook
Located at `.githooks/commit-msg`, this hook validates that every commit message contains the required trailer. If the trailer is missing, the commit will be rejected with an error message.

### prepare-commit-msg Hook
Located at `.githooks/prepare-commit-msg`, this hook automatically injects the commit template (including the trailer) when creating a new commit with an empty message.

## Verification

### Verify Commit Signatures
```bash
# Verify last commit
git verify-commit HEAD

# Verify specific commit
git verify-commit COMMIT_SHA

# Show signature details
git log --show-signature -1
```

### Verify Tag Signatures
```bash
git tag -v TAG_NAME
```

## Troubleshooting

### Issue: "gpg failed to sign the data"
**Solution for SSH signing:**
```bash
# Ensure SSH agent is running
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Verify key is loaded
ssh-add -l
```

**Solution for GPG signing:**
```bash
# Check GPG agent
gpg-agent --daemon

# Test GPG signing
echo "test" | gpg --clearsign

# Set GPG TTY
export GPG_TTY=$(tty)
```

### Issue: "Missing required trailer"
**Solution:** Ensure your commit message ends with:
```
Signed-off-by: Lazarus Laboratories <ops@lazarus-labs.com>
```

The prepare-commit-msg hook should automatically add this if you start with an empty message.

### Issue: "error: gpg.ssh.allowedSignersFile needs to be configured"
**Solution:**
```bash
echo "ops@lazarus-labs.com $(cat ~/.ssh/id_ed25519.pub)" >> ~/.ssh/allowed_signers
git config gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
```

### Issue: Hooks not executing
**Solution:** Verify hooks path is configured:
```bash
git config core.hooksPath
# Should output: .githooks

# Make hooks executable
chmod +x .githooks/*
```

## CI/CD Integration

For CI/CD pipelines, add a verification step:

```bash
#!/bin/bash
# ci-verify-signature.sh

# Verify commit signature
if ! git verify-commit HEAD 2>/dev/null; then
    echo "ERROR: HEAD commit is not signed"
    exit 1
fi

# Verify trailer
if ! git log -1 --format=%B | grep -qE '^Signed-off-by:\s+Lazarus Laboratories\s+<ops@lazarus-labs\.com>\s*$'; then
    echo "ERROR: Missing required trailer in HEAD commit"
    exit 1
fi

echo "Commit signature and trailer verified successfully"
```

## Additional Resources

- [Git Documentation - Signing Commits](https://git-scm.com/book/en/v2/Git-Tools-Signing-Your-Work)
- [GitHub - About commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)
- [Using SSH Keys for Git Commit Signing](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification#ssh-commit-signature-verification)

## Policy Compliance

All contributors MUST:
1. Configure commit signing before making commits
2. Include the required `Signed-off-by` trailer in all commits
3. Sign all tags with `-s` flag
4. Verify signatures when merging branches

Failure to comply will result in rejected commits and pull requests.

Signed-off-by: Lazarus Laboratories <ops@lazarus-labs.com>