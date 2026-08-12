from __future__ import annotations

import json
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.schemas.legal_generation import GenerationDraft, GroundedClaim


class GenerationProvider(Protocol):
    provider_id: str
    model_id: str

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationDraft: ...


class GenerationProviderUnavailable(RuntimeError):
    pass


class DeterministicTestGenerationProvider:
    '''TEST_ONLY: explicit test injection only; never selected from settings.'''

    provider_id = 'deterministic-test-only'
    model_id = 'deterministic-test-only-v1'

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationDraft:
        payload = json.loads(user_prompt)
        evidence = payload.get('evidence', [])
        if not evidence:
            return GenerationDraft(status='insufficient_evidence')
        first = evidence[0]
        law_name = first['law_name']
        title = first['title']
        return GenerationDraft(
            status='grounded',
            claims=[GroundedClaim(text=f'{law_name}의 {title} 근거를 확인해야 합니다.', citation_ids=[first['citation_id']])],
        )


class OpenAICompatibleGenerationProvider:
    provider_id = 'openai-compatible'

    def __init__(self, *, base_url: str, api_key: str, model_id: str, timeout_seconds: float = 30.0):
        if not api_key or not model_id:
            raise GenerationProviderUnavailable('Generation provider configuration is incomplete.')
        self.base_url = base_url.rstrip('/')
        self._api_key = api_key
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationDraft:
        try:
            response = httpx.post(
                f'{self.base_url}/chat/completions',
                headers={'Authorization': f'Bearer {self._api_key}'},
                json={
                    'model': self.model_id,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                    'temperature': 0,
                    'response_format': {'type': 'json_object'},
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            return GenerationDraft.model_validate_json(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise GenerationProviderUnavailable('Generation provider request failed.') from exc


def production_generation_provider(settings):
    if not settings.generation_configured:
        return None
    return OpenAICompatibleGenerationProvider(
        base_url=settings.generation_base_url,
        api_key=settings.generation_api_key,
        model_id=settings.generation_model,
        timeout_seconds=settings.generation_timeout_seconds,
    )
