# Notes for Claude Code

Read `STATUS.md` first — it covers what this project is, how it works, and
what is still open.

## Conventions

- Python targets Home Assistant's runtime. No new dependencies; `palette.py`
  is deliberately pure-Python so it has no numpy or colour-library import.
- Entity state lives in the config entry's **options**, not in the entity.
  Write with `_async_store()` on the base class in `entity.py`.
- Anything user-facing that could go stale belongs in `CHANGELOG.md`, and the
  manifest version must match the git tag or the release workflow fails.

## When editing YAML for View Assist

Two nesting depths exist and they are not interchangeable — see the section in
`STATUS.md`. Before handing over any YAML block, parse it and confirm the key
you care about landed where you think:

```python
import yaml; d = yaml.safe_load(block)
assert "styles" in d["title"]["card"]
```

Never delete or move individual lines inside a block scalar. Replace whole
blocks.

## Before claiming something works

The palette maths and renderer have real coverage; run them. The Home
Assistant integration surface does not, and cannot be exercised here — say so
rather than implying it has been tested.
