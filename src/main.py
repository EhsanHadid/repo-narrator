import sys
import os
import json
import re
import subprocess
from pathlib import Path
from abc import ABC, abstractmethod

# ── Providers ────────────────────────────────────────────────────────────────

class BaseProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        pass

class ClaudeProvider(BaseProvider):
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = os.environ.get("OVERRIDE_MODEL") or "claude-opus-4-5"

    def complete(self, prompt: str, system: str = "") -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=8096,
            system=system or "You are a senior software engineer writing clear, concise technical documentation.",
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

class OpenAIProvider(BaseProvider):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = os.environ.get("OVERRIDE_MODEL") or "gpt-4o"

    def complete(self, prompt: str, system: str = "") -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=8096,
            messages=[
                {"role": "system", "content": system or "You are a senior software engineer writing clear, concise technical documentation."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content

class GeminiProvider(BaseProvider):
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model_name = os.environ.get("OVERRIDE_MODEL") or "gemini-1.5-pro"
        self.model = genai.GenerativeModel(model_name)

    def complete(self, prompt: str, system: str = "") -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = self.model.generate_content(full_prompt)
        return response.text

def get_provider():
    provider = os.environ.get("AI_PROVIDER", "claude").lower()
    if provider == "claude":
        return ClaudeProvider()
    elif provider == "openai":
        return OpenAIProvider()
    elif provider == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown AI provider: {provider}")

# ── Tree ─────────────────────────────────────────────────────────────────────

def build_tree(root: str, ignored: list) -> list:
    entries = []
    root_path = Path(root).resolve()

    def should_ignore(p: Path) -> bool:
        for part in p.parts:
            if part in ignored:
                return True
        return False

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath).resolve()
        try:
            rel = current.relative_to(root_path)
        except ValueError:
            continue

        if should_ignore(rel):
            dirnames.clear()
            continue

        dirnames[:] = sorted([
            d for d in dirnames
            if not should_ignore(rel / d)
        ])

        depth = len(rel.parts)
        if depth > 0:
            entries.append({
                "path": str(current),
                "rel_path": str(rel),
                "type": "dir",
                "depth": depth,
                "name": current.name,
            })

        for fname in sorted(filenames):
            frel = rel / fname
            if should_ignore(frel):
                continue
            entries.append({
                "path": str(current / fname),
                "rel_path": str(frel),
                "type": "file",
                "depth": depth + 1,
                "name": fname,
            })

    return entries

def render_plain_tree(entries: list) -> str:
    lines = []
    for e in entries:
        indent = "  " * (e["depth"] - 1)
        prefix = "[dir] " if e["type"] == "dir" else "[file] "
        lines.append(f"{indent}{prefix}{e['rel_path']}")
    return "\n".join(lines)

def render_annotated_tree(entries: list, annotations: dict) -> str:
    lines = []
    for e in entries:
        indent = "  " * (e["depth"] - 1)
        name = e["name"]
        suffix = "/" if e["type"] == "dir" else ""
        desc = annotations.get(e["rel_path"], "")
        comment = f"  # {desc}" if desc else ""
        lines.append(f"{indent}{name}{suffix}{comment}")
    return "\n".join(lines)

# ── Helpers ───────────────────────────────────────────────────────────────────

def git_diff() -> str:
    try:
        return subprocess.check_output(
            ["git", "diff", "HEAD~1", "HEAD"], text=True, stderr=subprocess.DEVNULL
        )[:10000]
    except Exception:
        return "(no diff available)"

def read_file(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""

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

# ── AI Steps ──────────────────────────────────────────────────────────────────

SYSTEM = "You are a senior software engineer writing clear, concise technical documentation."

def annotate_tree(ai, entries: list, plain_tree: str, pr_context: str) -> dict:
    paths = [e["rel_path"] for e in entries]
    prompt = f"""Here is the repository file tree:

{plain_tree}

Recent PR context:
{pr_context}

Return ONLY a valid JSON object mapping every path to a short annotation (under 12 words).
Folders get a purpose statement. Files get a one-liner.
Example:
{{
  "src/auth": "Handles JWT verification and session management",
  "src/auth/jwt.ts": "Signs and verifies RS256 JWT tokens"
}}

Paths to annotate:
{json.dumps(paths, indent=2)}"""

    print(f"🤖  Annotating {len(entries)} entries...")
    response = ai.complete(prompt, system=SYSTEM)
    result = extract_json(response)
    print(f"✅  Got {len(result)} annotations")
    return result

def generate_structure_md(ai, annotated_tree: str, pr_context: str, existing: str) -> str:
    prompt = f"""Generate a structure.md file for this repository.

Annotated file tree:
{annotated_tree}

Recent changes:
{pr_context}

Existing structure.md (update it if exists, otherwise create fresh):
{existing or "(none)"}

Include:
1. Short project overview (2-3 sentences)
2. ## File Tree section with the annotated tree in a code block
3. ## Folder Guide section with a short paragraph per top-level folder
4. ## Key Files section listing important files with one-line descriptions

Return ONLY the markdown content."""

    return ai.complete(prompt, system=SYSTEM)

def update_readme(ai, existing: str, annotated_tree: str, pr_context: str, embed: bool) -> str:
    embed_note = (
        "Also add or update a collapsible <details><summary>Repository Structure</summary> section with the file tree."
        if embed else "Do NOT embed the file tree in the README."
    )
    prompt = f"""Update this README.md based on the merged PR.

Current README:
{existing or "(empty - create a minimal README)"}

PR context:
{pr_context}

Repo structure (for reference):
{annotated_tree[:3000]}

Instructions:
- Only update sections directly affected by the PR.
- Preserve existing structure, tone, and formatting.
- {embed_note}
- Return ONLY the full updated README content."""

    return ai.complete(prompt, system=SYSTEM)

def update_extra_md(ai, path: str, content: str, pr_context: str) -> str:
    prompt = f"""Update this markdown file based on the merged PR.

File: {path}
Current content:
{content or "(empty)"}

PR context:
{pr_context}

For CHANGELOG.md: add a new entry under ## [Unreleased].
For other files: only update what is directly relevant.

Return ONLY the full updated file content."""
    return ai.complete(prompt, system=SYSTEM)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🚀  Repo Narrator starting with provider: {os.environ.get('AI_PROVIDER', 'claude')}")
    ai = get_provider()

    ignored_raw = os.environ.get("IGNORED_PATHS", "node_modules,.git,dist,build,.next,__pycache__,.nx,coverage")
    ignored = [p.strip() for p in ignored_raw.split(",")]

    structure_file = os.environ.get("STRUCTURE_FILE", "structure.md")
    embed_structure = os.environ.get("EMBED_STRUCTURE_README", "false").lower() == "true"
    do_readme = os.environ.get("UPDATE_README", "true").lower() == "true"
    extra_files = [f.strip() for f in os.environ.get("EXTRA_MD_FILES", "CHANGELOG.md").split(",") if f.strip()]

    pr_context = f"""PR #{os.environ.get('PR_NUMBER', 'N/A')} by @{os.environ.get('PR_AUTHOR', 'unknown')}
Title: {os.environ.get('PR_TITLE', 'Manual run')}
Description: {os.environ.get('PR_BODY', '')[:2000]}

Git diff:
{git_diff()}"""

    print("🌳  Building file tree...")
    entries = build_tree(".", ignored)
    print(f"    Found {len(entries)} entries")
    plain_tree = render_plain_tree(entries)

    annotations = annotate_tree(ai, entries, plain_tree, pr_context)
    annotated_tree = render_annotated_tree(entries, annotations)

    if structure_file and structure_file.lower() != "none":
        print(f"📄  Generating {structure_file}...")
        existing = read_file(structure_file)
        content = generate_structure_md(ai, annotated_tree, pr_context, existing)
        write_file(structure_file, content)

    if do_readme:
        print("📝  Updating README.md...")
        existing = read_file("README.md")
        content = update_readme(ai, existing, annotated_tree, pr_context, embed_structure)
        write_file("README.md", content)

    for md_path in extra_files:
        print(f"📝  Updating {md_path}...")
        content = update_extra_md(ai, md_path, read_file(md_path), pr_context)
        write_file(md_path, content)

    print("✅  Repo Narrator done.")

if __name__ == "__main__":
    main()