---
name: homebrew-packaging
description: >-
  Homebrew tap and formula packaging for bluefinctl. Use when setting up
  the tap, updating the formula, debugging brew install failures, or
  modifying the release workflow that publishes to homebrew-bluefinctl.
metadata:
  context7-sources:
    - /homebrew/brew
---

# Homebrew Packaging

## When to Use

- Formula install fails (404, wrong SHA, bad resource block)
- Setting up a new tap or moving the formula
- Updating the release workflow to auto-publish the formula
- Debugging `brew install` on Bluefin (trust + tap mechanics)

## When NOT to Use

- Python dependency issues at runtime — that's `core/` not the formula
- CI failures unrelated to packaging — see `docs/skills/ci-tooling.md`

## Core Process

### 1. Tap naming (canonical rule)

`brew tap user/name` expands to `https://github.com/user/homebrew-name`.
The GitHub repo **must** be named `homebrew-<name>` for the short form to work.

```
brew tap projectbluefin/bluefinctl
  → clones https://github.com/projectbluefin/homebrew-bluefinctl
```

Source: [Homebrew Taps docs](https://github.com/homebrew/brew/blob/main/docs/Taps.md)

Our tap repo: **`projectbluefin/homebrew-bluefinctl`**
Our main repo: **`projectbluefin/bluefinctl`** (code + release CI)

### 2. Install command on Bluefin

Bluefin sets `HOMEBREW_REQUIRE_TAP_TRUST`. Any non-official tap must be
explicitly trusted before Homebrew will load its formulae.
`brew trust` marks the tap in `~/.homebrew/trust.json` but does **not** add
it to the tap list. `brew tap` must be called separately.

**One-liner for users:**

```bash
brew trust --tap projectbluefin/bluefinctl && brew tap projectbluefin/bluefinctl && brew install bluefinctl
```

- `brew trust --tap projectbluefin/bluefinctl` — marks trusted (required by Bluefin sandbox)
- `brew tap projectbluefin/bluefinctl` — clones `homebrew-bluefinctl`, adds formulae to search path
- `brew install bluefinctl` — short name works once the tap is added

**Do not use** `brew install projectbluefin/bluefinctl/bluefinctl` — the
repeated name is confusing and unnecessary once the tap is added.

### 3. Formula structure

The formula lives at `homebrew-bluefinctl/bluefinctl.rb`.
It uses `Language::Python::Virtualenv` — the standard pattern for Python CLI tools:

```ruby
class Bluefinctl < Formula
  include Language::Python::Virtualenv

  url "https://github.com/projectbluefin/bluefinctl/releases/download/vX.Y.Z/bluefinctl-X.Y.Z.tar.gz"
  sha256 "<sdist sha256>"
  version "X.Y.Z"

  depends_on "python@3.13"

  # Each PyPI dependency needs its own resource block with exact SHA256.
  # Get SHA256 with: pip download <pkg>==<ver> -d /tmp && sha256sum /tmp/*.gz
  resource "textual" do
    url "https://files.pythonhosted.org/packages/.../textual-X.Y.Z.tar.gz"
    sha256 "..."
  end

  def install
    virtualenv_install_with_resources
  end
end
```

Source: [Python for Formula Authors](https://github.com/homebrew/brew/blob/main/docs/Python-for-Formula-Authors.md)

### 4. Release workflow

On every `v*` tag push to `projectbluefin/bluefinctl`, the workflow:

1. Builds the sdist (`python -m build`)
2. Computes SHA256 of the `.tar.gz`
3. Creates a GitHub Release with the assets
4. Clones `homebrew-bluefinctl`, patches `url`, `sha256`, `version` with `sed`
5. Commits and pushes to `homebrew-bluefinctl` main

**Critical:** The workflow uses a **GitHub App token** (mergeraptor) — not `GITHUB_TOKEN` — to push to `homebrew-bluefinctl`. `GITHUB_TOKEN` is scoped to the triggering repo and cannot write to a different repo. The mergeraptor app must be installed on `homebrew-bluefinctl` with write permission.

```yaml
- name: Generate mergeraptor app token
  id: app-token
  uses: actions/create-github-app-token@<pinned-sha> # v3
  with:
    app-id: ${{ vars.MERGERAPTOR_APP_ID }}
    private-key: ${{ secrets.MERGERAPTOR_PRIVATE_KEY }}
    repositories: homebrew-bluefinctl

- name: Update Homebrew tap formula
  env:
    GH_TOKEN: ${{ steps.app-token.outputs.token }}
    TAG: ${{ github.ref_name }}
    SHA256: ${{ steps.sha.outputs.sha256 }}
    FILENAME: ${{ steps.sha.outputs.filename }}
  run: |
    VERSION="${TAG#v}"
    URL="https://github.com/${{ github.repository }}/releases/download/${TAG}/${FILENAME}"
    git clone https://x-access-token:${GH_TOKEN}@github.com/projectbluefin/homebrew-bluefinctl.git tap
    sed -i \
      -e "s|url \".*\"|url \"${URL}\"|" \
      -e "s|sha256 \".*\"|sha256 \"${SHA256}\"|" \
      -e "s|version \".*\"|version \"${VERSION}\"|" \
      tap/bluefinctl.rb
    cd tap
    git config user.name "mergeraptor[bot]"
    git config user.email "mergeraptor[bot]@users.noreply.github.com"
    git add bluefinctl.rb
    git commit -m "chore: update bluefinctl to ${TAG}" || echo "no changes"
    git push
```

### 5. Cutting a release

```bash
git tag vX.Y.Z
git push upstream vX.Y.Z
```

The release workflow runs on `projectbluefin/bluefinctl` and auto-updates
the formula in `homebrew-bluefinctl`. No manual formula edits needed.

**Bump `version` in `pyproject.toml` before tagging** — the sdist filename
and the formula version must match.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The formula can live in the main repo." | It can, but then `brew install` requires the ugly `user/repo/formula` triple-path. A separate `homebrew-<name>` repo enables `brew install formula`. |
| "I can tag before merging to main." | The release workflow runs on the tagged commit. Tag only after the work is on `main` in `projectbluefin/bluefinctl`. |
| "The formula SHA updates automatically." | Only if the workflow ran with the new tap-push step. If the workflow was changed after the tag, update the formula manually via the GitHub API. |
| "`brew trust --tap` is enough to install." | No — trust marks the tap safe to load but does not add it. `brew tap` is still required. |

## Red Flags

- Formula `sha256` is `0000...` — the release workflow didn't run or ran the old version; update manually
- `brew install bluefinctl` returns "No available formula" — tap not added (`brew tap` not run)
- `brew install` returns 404 — formula URL points to wrong repo or release assets not uploaded yet
- Formula `version` doesn't match `pyproject.toml` version — tagging happened before version bump
- `brew install user/repo/formula` in docs — always use the three-step trust + tap + install instead
- Release workflow uses `secrets.GITHUB_TOKEN` for tap push — `GITHUB_TOKEN` is scoped to the source repo; use the mergeraptor GitHub App token (`vars.MERGERAPTOR_APP_ID` + `secrets.MERGERAPTOR_PRIVATE_KEY`) instead

## Verification

- [ ] `projectbluefin/homebrew-bluefinctl` exists and has `bluefinctl.rb` at root
- [ ] Formula `url` matches the latest GitHub Release asset URL
- [ ] Formula `sha256` matches `sha256sum` of the sdist tarball (not all-zeros)
- [ ] Formula `version` matches `pyproject.toml` version
- [ ] `brew trust --tap projectbluefin/bluefinctl && brew tap projectbluefin/bluefinctl && brew install bluefinctl` installs cleanly
- [ ] Release workflow `.github/workflows/release.yml` pushes to `homebrew-bluefinctl`, not back to main repo
