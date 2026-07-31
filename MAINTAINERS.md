# Maintainers

| Name | GitHub | Role |
|------|--------|------|
| Tom Paine | [@aioue](https://github.com/aioue) | Original author; collection owner |
| Lenny Shirley | [@lennysh](https://github.com/lennysh) | Co-maintainer |

## Expectations

- Triage issues and review pull requests within a reasonable timeframe.
- Run CI locally (`pre-commit run --all-files`, `pytest tests/unit/`) before merging.
- Cut Galaxy releases from annotated git tags (`v*`) after CI passes on `main`.

## Release checklist

1. Bump `version` in `galaxy.yml` and add an entry to `CHANGELOG.md`.
2. Commit and push to `main`.
3. Create and push an annotated tag: `git tag -a vX.Y.Z -m "vX.Y.Z"` then `git push origin vX.Y.Z`.
4. The [Release workflow](.github/workflows/release.yml) runs unit tests, `ansible-test sanity`, builds the artifact, publishes to [Galaxy](https://galaxy.ansible.com/ui/repo/published/aioue/network/), and creates a GitHub Release.

## Galaxy access

Publishing requires a Galaxy API token stored as the `GALAXY_API_TOKEN` repository secret. Maintainers who need publish access should ask the collection owner to add them on [galaxy.ansible.com](https://galaxy.ansible.com/) under the `aioue` namespace or to rotate the CI secret.

## Handover

If you can no longer maintain the collection, open a GitHub issue titled **Seeking maintainers** before archiving. Downstream users install via `ansible-galaxy collection install aioue.network`; breaking namespace changes require a migration plan.
