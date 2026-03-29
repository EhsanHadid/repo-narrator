import os
import google.generativeai as genai
from .base import BaseProvider

DEFAULTS = {
    "gemini": "gemini-1.5-pro",
}

class GeminiProvider(BaseProvider):
    def __init__(self):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model_name = os.environ.get("OVERRIDE_MODEL") or DEFAULTS["gemini"]
        self.model = genai.GenerativeModel(model_name)

    def complete(self, prompt: str, system: str = "") -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = self.model.generate_content(full_prompt)
        return response.text