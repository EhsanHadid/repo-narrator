import os
import anthropic
from .base import BaseProvider

DEFAULTS = {
    "claude": "claude-opus-4-5",
}

class ClaudeProvider(BaseProvider):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = os.environ.get("OVERRIDE_MODEL") or DEFAULTS["claude"]

    def complete(self, prompt: str, system: str = "") -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=8096,
            system=system or "You are a senior software engineer writing clear, concise technical documentation.",
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text