# Codex Installation

This repository is prepared to work in two Codex-friendly modes:

1. As a skills repository: install one or more folders under `skills/`.
2. As a plugin package: use the root `.codex-plugin/plugin.json`, which points Codex at `./skills/`.

No publication step is required for local use. After cloning the repository, install the stable skills into Codex with:

```bash
git clone https://github.com/JiaqiLiZju/s2f-agent.git
cd s2f-agent
./scripts/link_skills.sh --copy
```

The default destination is `${CODEX_HOME:-$HOME/.codex}/skills`. Use `--skills-dir` to install elsewhere:

```bash
./scripts/link_skills.sh --copy --skills-dir "$HOME/.codex/skills"
```

For a development checkout, symlinks are more convenient because edits are picked up after restarting Codex:

```bash
./scripts/link_skills.sh --force
```

Install a subset by naming skill IDs:

```bash
./scripts/link_skills.sh --copy alphagenome-api borzoi-workflows dnabert2
```

To install directly from GitHub with Codex's skill installer, use paths under `skills/`:

```text
repo: JiaqiLiZju/s2f-agent
path: skills/alphagenome-api
path: skills/borzoi-workflows
path: skills/dnabert2
path: skills/evo2-inference
path: skills/gpn-models
path: skills/nucleotide-transformer-v3
path: skills/segment-nt
path: skills/skill-factory
```

Validate packaging before publishing or tagging a release:

```bash
./scripts/validate_codex_package.sh
# or
make validate-codex-package
```

For the broader agent and registry test suite, run:

```bash
make validate-agent
make smoke-lite
```

Restart Codex after installing or updating skills.
