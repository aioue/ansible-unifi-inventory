# Maintainers

| Name | GitHub | Role |
|------|--------|------|
| Tom Paine | [@aioue](https://github.com/aioue) | Original author; collection owner |
| Lenny Shirley | [@lennysh](https://github.com/lennysh) | Co-maintainer |

Triage issues and review pull requests as availability permits. Run the checks in [CONTRIBUTING.md](CONTRIBUTING.md) and require passing CI before merging.

## Release checklist

1. Bump `version` in `galaxy.yml` and add the matching version section to `CHANGELOG.md`.
2. Run local source tests, installed-artifact tests, and Ansible sanity. Commit and push the release change to `main`; wait for CI to pass.
3. Create and push an annotated tag: `git tag -a vX.Y.Z -m "vX.Y.Z"`, then `git push origin vX.Y.Z`.
4. Check the [Release workflow](.github/workflows/release.yml), [Galaxy version](https://galaxy.ansible.com/ui/repo/published/aioue/network/), and GitHub release assets.

The workflow validates tag/version/release notes before publication, runs tests and sanity, and builds the archive once. It checks and tests that archive, publishes it to Galaxy, and attaches it with `SHA256SUMS` to the GitHub release.

## Galaxy access

Publishing requires the `GALAXY_API_TOKEN` repository secret. Ask the collection owner for publish access under the `aioue` namespace or to rotate the CI secret.

## Handover

If you can no longer maintain the collection, open an issue titled "Seeking maintainers" before archiving. Downstream users install `aioue.network`; namespace changes require a migration plan.
