import os
from openai import OpenAI
from .base import BaseProvider

DEFAULTS = {
    "openai": "gpt-4o",
}

class OpenAIProvider(BaseProvider):
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = os.environ.get("OVERRIDE_MODEL") or DEFAULTS["openai"]

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