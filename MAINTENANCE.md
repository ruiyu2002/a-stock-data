# Fork maintenance

Notes for keeping this fork (`ruiyu2002/a-stock-data`) in sync with upstream (`simonlin1212/a-stock-data`).

## Re-sync from upstream

The fork was branched at upstream commit `9379ab90d0219312b5f4845cd8c97502f40b0806`. Upstream's only file of real interest is `SKILL.md` — everything in `a_stock_data/` is derived from it by the extractor below.

### Manual sync flow

```bash
cd /Users/chenruiyu/project/a-stock-data

# 1. fetch upstream
git fetch upstream

# 2. diff upstream's SKILL.md against current
git diff HEAD..upstream/main -- SKILL.md | less

# 3. if the diff is acceptable, merge SKILL.md only (avoid clobbering pyproject.toml, a_stock_data/, README header)
git checkout upstream/main -- SKILL.md CHANGELOG.md
git add SKILL.md CHANGELOG.md
git commit -m "sync: pull upstream SKILL.md @ <upstream-sha>"

# 4. re-run the extractor to regenerate a_stock_data/*.py from the new SKILL.md
python3 scripts/extract_skill.py     # see "Re-extract" below

# 5. smoke test
pip install -e .
python -c "from a_stock_data import tencent_quote; print(tencent_quote(['600519']))"

# 6. bump version + tag
# edit pyproject.toml: version = "3.X.Y.postN+1"
git add pyproject.toml a_stock_data/
git commit -m "regen: extract a_stock_data/ from SKILL.md @ <upstream-sha>"
git tag v3.X.Y.postN+1
git push origin main --tags
```

## Re-extract `a_stock_data/` from `SKILL.md`

The package modules in `a_stock_data/` are produced by an extractor that:

1. Parses every ```python``` code block in `SKILL.md`
2. Routes each block to a target module based on its `##` / `###` headers (see routing table in the extractor script)
3. Hoists common imports
4. For sections that only have demo code (mootdx 1.1 / 6.1 / 6.2 / 7.2), wraps the demo into named functions
5. Re-exports public functions via `a_stock_data/__init__.py`

The initial extraction was performed inline. If a future `SKILL.md` adds new sections, update the routing table or add new modules and re-run.

## What to NEVER commit

- `*.egg-info/`, `build/`, `dist/`, `.eggs/`
- IDE-specific config (`.idea/`, `.vscode/`)
- Local `data.db`, `.env`, or any actual market data

## Downstream

The `analyst` project (`stock_agent_v2`) depends on a pinned tag of this fork. When you bump the tag here, also bump the pin in `stock_agent_v2/pyproject.toml`:

```toml
dependencies = [
    "a-stock-data @ git+https://github.com/ruiyu2002/a-stock-data.git@v3.X.Y.postN+1",
]
```

Then re-run `analyst`'s integration smoke (`pytest tests/integration -m vendor_live`) before merging.
