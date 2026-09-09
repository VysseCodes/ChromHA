# Cutting a release

## 1. Check the version

`custom_components/chromha/manifest.json` -> `version` must match the tag you
are about to create, without the `v`. The release workflow fails the release
if they disagree, because HACS serves whatever the manifest says.

The manifest is currently `0.3.0`, so the next tag is `v0.3.0`.

## 2. Update the changelog

Move anything under `## [Unreleased]` into a new version heading with today's
date, and add the link reference at the bottom.

## 3. Commit and tag

```bash
git add -A
git commit -m "Release v0.3.0"
git push origin main

git tag -a v0.3.0 -m "ChromHA v0.3.0"
git push origin v0.3.0
```

## 4. Publish the release

A tag alone is not enough - HACS reads GitHub *releases*.

GitHub -> Releases -> Draft a new release -> choose tag `v0.3.0` ->
title `v0.3.0` -> paste the changelog section as the body -> Publish.

## 5. Verify

- The Actions run for the release should pass the version check.
- The `hacs` job should report 9/9.
- Install it in Home Assistant via HACS custom repository and confirm the
  version shown matches.

## Before the first release

- [ ] Repository is **public** (HACS cannot read private repos)
- [ ] Repository has a description and at least one topic
- [ ] Issues are enabled
- [ ] Brand assets submitted to home-assistant/brands (optional; the copy in
      `custom_components/chromha/brand/` satisfies HACS on its own)
- [ ] Installed and smoke-tested on a real Home Assistant instance
