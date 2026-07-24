# Trmachel Skill Branding Design

## Goal

Apply the Trmachel brand consistently to the published GitHub repository and
Codex Skill, and replace the existing local-machine Git identity in all
published commits.

## Public Names

- GitHub repository: `trmachel-depth-video-converter-skill`
- Codex Skill name: `trmachel-convert-depth-video`
- Skill invocation: `$trmachel-convert-depth-video`
- Skill directory: `skills/trmachel-convert-depth-video/`

The application title and its functional description remain unchanged. Runtime
cache paths also remain `convert-depth-video` so existing model and environment
caches continue to work after the branding change.

## Repository Updates

Rename the Skill directory and update every installation path, GitHub URL,
validation example, and default prompt that references the old repository or
Skill name. Validate the renamed Skill with the official Skill validator and
run the existing automated tests.

Rename the GitHub repository through repository settings. GitHub's redirect
from the previous repository URL is useful for compatibility, but the local
`origin` remote and all documentation must use the new canonical URL.

## Commit Identity

Rewrite every existing commit so both Author and Committer use:

- Name: `Trmachel`
- Email: `21993150+Trmachel@users.noreply.github.com`

The email is GitHub's account-linked privacy address derived from the public
account ID for `https://github.com/Trmachel`. It avoids publishing a personal
email while associating commits with that GitHub profile.

Preserve existing commit messages, timestamps, parent structure, and file
contents except for the intentional branding changes. Add the branding update
as a new commit using the same identity.

## History And Release

Create local backup refs before rewriting history. After verification:

1. Force-update remote `main` with force-with-lease semantics.
2. Move annotated tag `v0.1.0` to the completed branding commit.
3. Force-update the remote tag.

The commit hashes will change. No other branches, repositories, releases, or
GitHub account settings are in scope.

## Verification

- The worktree is clean and `main` tracks the renamed remote.
- Every commit reports `Trmachel` for Author and Committer.
- Every commit uses the GitHub privacy email.
- The Skill directory and `SKILL.md` name match
  `trmachel-convert-depth-video`.
- The official Skill validator passes.
- The existing automated test suite passes.
- GitHub shows the renamed public repository, Apache-2.0 license, README,
  Skill directory, and `v0.1.0` tag.
- The GitHub commit list displays `Trmachel` instead of the local name.

## Recovery

Keep local backup refs until all remote and browser checks pass. If the rewrite
or force push fails, restore `main` and `v0.1.0` from those refs and repeat only
after identifying the failure.
