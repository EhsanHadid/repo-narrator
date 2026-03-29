# Repo Narrator

> AI-powered GitHub Action that documents your repository after every merged PR —
> annotated file trees, updated READMEs, and auto-generated `structure.md`.

## What it does

After a PR is merged, Repo Narrator:
1. Walks your entire repo and builds an **annotated file tree** (every folder and file gets a one-line description)
2. Creates or updates **`structure.md`** with a guided tour of your codebase
3. Updates **`README.md`** to reflect new features, APIs, or setup changes
4. Updates **`CHANGELOG.md`** (or any other `.md` files you specify)

Supports **Claude**, **OpenAI**, and **Gemini**.

## Quick start
```yaml
# .github/workflows/repo-narrator.yml
name: Repo Narrator
on:
  pull_request:
    types: [closed]

jobs:
  narrate:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: your-username/repo-narrator@v1
        with:
          ai_provider: claude
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `ai_provider` | ✅ | `claude` | `claude` · `openai` · `gemini` |
| `anthropic_api_key` | if claude | — | API key from console.anthropic.com |
| `openai_api_key` | if openai | — | API key from platform.openai.com |
| `gemini_api_key` | if gemini | — | API key from aistudio.google.com |
| `model` | ❌ | provider default | Override the model (e.g. `gpt-4o-mini`) |
| `update_readme` | ❌ | `true` | Update README.md |
| `structure_file` | ❌ | `structure.md` | Output file for annotated tree. Set to `none` to skip |
| `embed_structure_in_readme` | ❌ | `false` | Embed file tree inside README in a collapsible section |
| `ignored_paths` | ❌ | `node_modules,.git,dist,...` | Comma-separated paths to exclude |
| `extra_md_files` | ❌ | `CHANGELOG.md` | Additional markdown files to update |
| `commit_message` | ❌ | `docs: repo-narrator update` | Commit message |

## Default models

| Provider | Default model |
|---|---|
| Claude | `claude-opus-4-5` |
| OpenAI | `gpt-4o` |
| Gemini | `gemini-1.5-pro` |