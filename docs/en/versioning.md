# Versioning & Compatibility

Canary Framework follows [Semantic Versioning](https://semver.org/) from 1.0.0 on. Versions
before 1.0 were exploratory and made breaking changes freely.

## What each number means

| Release | May contain |
|---|---|
| Patch — `1.0.x` | Bug fixes and documentation. No new public names. |
| Minor — `1.x.0` | New features and deprecations. Existing code keeps working. |
| Major — `x.0.0` | Breaking changes, each listed in the changelog with a migration path. |

## The public API {#public-api}

The stability promise covers:

- every name exported from `canary_framework` (listed in `__all__`), with the signatures and
  behaviour described in these docs;
- the exception types raised in the situations the docs describe;
- the lifecycle rules: dependency order, one run per unit and phase, the barrier between `init`
  and `start`, reverse-order reclamation, restart after `stop()`.

It does **not** cover:

- anything under `canary_framework.core.*` that is not re-exported from `canary_framework`;
- names that start with an underscore;
- the text of exception messages and notes;
- the shape of `Scope`'s record attributes — `phases`, `entered` and `known`. They are there for
  inspection and debugging, and may change in a minor release. `Scope.instances`,
  `Scope.instance()`, `Scope.provide()` and `Scope.resolve()` are covered.

## Deprecation

A public name or behaviour is removed only in a major release, and only after at least one
minor release in which using it emits a `DeprecationWarning` naming its replacement. Every
deprecation is recorded in the changelog.

## Supported versions

Only the latest minor release receives fixes, including security fixes. Upgrading within a
major version is expected to be a drop-in change.

## Python versions

Each release supports the Python versions listed on PyPI (currently 3.12 to 3.15). Support for a
Python version that has reached its end of life may be dropped in a minor release; the changelog
says so.

## Releases

Releases are cut from `main` by pushing a `vX.Y.Z` tag. The notes for each release are the
matching section of the [changelog](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md),
followed by the list of merged pull requests.
