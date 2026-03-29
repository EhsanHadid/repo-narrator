import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import re
import subprocess
from pathlib import Path
from tree import build_tree, render_plain_tree, render_annotated_tree

# ── Bootstrap provider ──────────────────────────────────────────────────────

def get_provider():
    provider = os.environ.get("AI_PROVIDER", "claude").lower()
    if provider == "claude":
        from providers.claude import ClaudeProvider
        return ClaudeProvider()
    elif provider == "openai":
        from providers.openai import OpenAIProvider
        return OpenAIProvider()
    elif provider == "gemini":
        from providers.gemini import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown AI provider: {provider}")

# ── Helpers ──────────────────────────────────────────────────────────────────

def git_diff() -> str:
    try:
        return subprocess.check_output(
            ["git", "diff", "HEAD~1", "HEAD"], text=True, stderr=subprocess.DEVNULL
        )[:10000]
    except subprocess.CalledProcessError:
        return ""

def read_file(path: str) -> str:
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""

def write_file(path: str, content: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    print(f"✅  Written: {path}")

def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}

def extract_code_block(text: str, lang: str = "") -> str:
    pattern = rf"```{lang}\n(.*?)```" if lang else r"```(?:\w*)\n(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()

# ── Step 1: Annotate file tree ───────────────────────────────────────────────

ANNOTATE_SYSTEM = """You are a senior software engineer.
Your job: read a repository file tree and write a short, plain-English annotation for every entry.
Keep each annotation under 12 words. Be specific, not generic.
Folders get a purpose statement. Files get a one-liner of what they do."""

def annotate_tree(ai, entries: list[dict], plain_tree: str, pr_context: str) -> dict[str, str]:
    paths = [e["rel_path"] for e in entries]
    prompt = f"""Here is the repository file tree:

{plain_tree}

Recent PR context (use this to improve accuracy):
{pr_context}

Return ONLY a JSON object mapping every path to its annotation. Example:
{{
  "src/auth": "Handles JWT verification and session management",
  "src/auth/jwt.ts": "Signs and verifies RS256 JWT tokens"
}}

Paths to annotate:
{json.dumps(paths, indent=2)}"""

    response = ai.complete(prompt, system=ANNOTATE_SYSTEM)
    return extract_json(response)

# ── Step 2: Generate / update structure.md ───────────────────────────────────

STRUCTURE_SYSTEM = """You are a technical documentation writer.
Write clear, structured markdown documentation for a software project's repository structure.
Be concise but informative. Use second-person for folder summaries ("This folder contains...").
"""

def generate_structure_md(
    ai,
    annotated_tree: str,
    pr_context: str,
    existing: str,
) -> str:
    prompt = f"""Generate a `structure.md` file for this repository.

Annotated file tree:
{annotated_tree}

Recent changes:
{pr_context}

Existing structure.md (update it, don't start from scratch if it exists):
{existing or "(none — create fresh)"}

The document must include:
1. A short project overview paragraph (2-3 sentences)
2. A "## File Tree" section with the annotated tree inside a code block
3. A "## Module / Folder Guide" section with a short paragraph per top-level folder
4. A "## Key Files" section listing the most important files with one-line descriptions

Return ONLY the full markdown content, no extra commentary."""

    return ai.complete(prompt, system=STRUCTURE_SYSTEM)

# ── Step 3: Update README ────────────────────────────────────────────────────

README_SYSTEM = """You are a technical documentation writer maintaining a project README.
Only update sections that are directly affected by the PR changes.
Preserve the existing structure, tone, and formatting exactly.
Never remove sections. Never add fluff."""

def update_readme(ai, existing_readme: str, annotated_tree: str, pr_context: str, embed_structure: bool) -> str:
    embed_instruction = (
        "Also update or insert a collapsible <details><summary>📁 Repository Structure</summary> section "
        "near the bottom of the README containing the annotated file tree in a code block."
        if embed_structure else
        "Do NOT embed the file tree in the README."
    )

    prompt = f"""Update this README.md based on the merged PR below.

Current README:
{existing_readme or "(empty — create a minimal README)"}

PR context:
{pr_context}

Annotated repo structure (for reference):
{annotated_tree[:3000]}

Instructions:
- Update the features list, usage, or API sections only if the PR changes them.
- Update badges or version numbers if relevant.
- {embed_instruction}
- Return ONLY the full updated README content."""

    return ai.complete(prompt, system=README_SYSTEM)

# ── Step 4: Update extra markdown files ──────────────────────────────────────

EXTRA_MD_SYSTEM = """You are a technical documentation writer.
Update the given markdown file to reflect the merged PR changes.
Preserve all existing content and formatting. Be concise."""

def update_extra_md(ai, path: str, content: str, pr_context: str) -> str:
    prompt = f"""Update this markdown file based on the merged PR.

File: {path}
Current content:
{content or "(empty — create appropriate content for this file type)"}

PR context:
{pr_context}

For CHANGELOG.md: add a new entry under ## [Unreleased] with the PR details.
For other files: only update what's directly relevant to the PR.

Return ONLY the full updated file content."""
    return ai.complete(prompt, system=EXTRA_MD_SYSTEM)

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ai = get_provider()

    # Config
    ignored = [p.strip() for p in os.environ.get("IGNORED_PATHS", "node_modules,.git,dist,build,.next").split(",")]
    structure_file = os.environ.get("STRUCTURE_FILE", "structure.md")
    embed_structure = os.environ.get("EMBED_STRUCTURE_README", "false").lower() == "true"
    do_update_readme = os.environ.get("UPDATE_README", "true").lower() == "true"
    extra_files = [f.strip() for f in os.environ.get("EXTRA_MD_FILES", "CHANGELOG.md").split(",") if f.strip()]

    # PR context
    pr_context = f"""PR #{os.environ.get('PR_NUMBER')} by @{os.environ.get('PR_AUTHOR')}
Title: {os.environ.get('PR_TITLE')}
Description: {os.environ.get('PR_BODY', '')[:2000]}

Git diff:
{git_diff()}"""

    # ── 1. Build and annotate the tree
    print("🌳  Building file tree...")
    entries = build_tree(".", ignored)
    plain_tree = render_plain_tree(entries)

    print(f"🤖  Annotating {len(entries)} entries with {os.environ.get('AI_PROVIDER')}...")
    annotations = annotate_tree(ai, entries, plain_tree, pr_context)

    annotated_tree = render_annotated_tree(entries, annotations)

    # ── 2. Generate structure.md
    if structure_file and structure_file.lower() != "none":
        print(f"📄  Generating {structure_file}...")
        existing_structure = read_file(structure_file)
        structure_md = generate_structure_md(ai, annotated_tree, pr_context, existing_structure)
        write_file(structure_file, structure_md)

    # ── 3. Update README
    if do_update_readme:
        print("📝  Updating README.md...")
        existing_readme = read_file("README.md")
        new_readme = update_readme(ai, existing_readme, annotated_tree, pr_context, embed_structure)
        write_file("README.md", new_readme)

    # ── 4. Update extra markdown files
    for md_path in extra_files:
        print(f"📝  Updating {md_path}...")
        content = read_file(md_path)
        updated = update_extra_md(ai, md_path, content, pr_context)
        write_file(md_path, updated)

    print("✅  Repo Narrator done.")

if __name__ == "__main__":
    main()