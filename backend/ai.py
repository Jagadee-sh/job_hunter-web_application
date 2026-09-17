from typing import Any

from openai import AsyncOpenAI, OpenAIError

from backend.config import get_settings


class AIService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.model = settings.openai_model

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        if self.client is None:
            return {"score": 0.0, "rationale": "AI scoring is unavailable until an API key is configured.", "skill_gaps": []}
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
        except OpenAIError:
            return {
                "score": 0.0,
                "rationale": "AI scoring is temporarily unavailable. Check the API key and account billing, then try again.",
                "skill_gaps": [],
            }
        content = response.choices[0].message.content or "{}"
        import json

        result = json.loads(content)
        return result if isinstance(result, dict) else {}
