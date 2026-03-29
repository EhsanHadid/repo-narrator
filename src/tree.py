import os
from pathlib import Path

def build_tree(root: str, ignored: list[str]) -> list[dict]:
    """
    Walks the repo and returns a flat list of entries:
    [{ path, rel_path, type: 'file'|'dir', depth, name }]
    """
    entries = []
    root_path = Path(root).resolve()

    def should_ignore(p: Path) -> bool:
        for part in p.parts:
            if part in ignored:
                return True
        return False

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath).resolve()
        rel = current.relative_to(root_path)

        if should_ignore(rel):
            dirnames.clear()
            continue

        # Filter dirnames in-place so os.walk skips ignored dirs
        dirnames[:] = sorted([
            d for d in dirnames
            if not should_ignore(rel / d) and not d.startswith(".")
            or d in (".github", ".claude", ".gemini")  # allow selected dot dirs
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


def render_plain_tree(entries: list[dict]) -> str:
    """Render a plain text tree (no annotations) for the AI prompt."""
    lines = []
    for e in entries:
        indent = "  " * (e["depth"] - 1)
        prefix = "📁 " if e["type"] == "dir" else "📄 "
        lines.append(f"{indent}{prefix}{e['rel_path']}")
    return "\n".join(lines)


def render_annotated_tree(entries: list[dict], annotations: dict[str, str]) -> str:
    """
    Merge AI-generated annotations back into the tree for markdown output.
    annotations: { rel_path -> description }
    """
    lines = []
    for e in entries:
        depth = e["depth"]
        indent = "  " * (depth - 1)
        name = e["name"]
        suffix = "/" if e["type"] == "dir" else ""
        desc = annotations.get(e["rel_path"], "")
        comment = f"  # {desc}" if desc else ""
        lines.append(f"{indent}{name}{suffix}{comment}")
    return "\n".join(lines)