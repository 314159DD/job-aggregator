"""
aggregator/translate.py - Batch job-title translation via OpenRouter.

Translates English job titles to German in a single LLM call per batch.
German-source titles are detected and returned unchanged.
Gracefully degrades: if the API key is missing or the call fails,
all jobs keep title_de = None (frontend falls back to title).
"""

import json
import logging
import urllib.request

from aggregator.config import OPENROUTER_API_KEY
from aggregator.models import JobRecord

log = logging.getLogger(__name__)

_MODEL = 'google/gemini-2.5-flash-lite'
_BATCH_SIZE = 150  # titles per LLM call (keeps prompt short)
_TIMEOUT = 30      # seconds


def translate_titles(jobs: list[JobRecord], source_name: str) -> None:
    """Populate title_de on each JobRecord in-place.

    - If OPENROUTER_API_KEY is not set, silently skips (no-op).
    - Sends titles in batches to a cheap LLM for translation.
    - On error, leaves title_de as None (frontend falls back to title).
    """
    if not OPENROUTER_API_KEY:
        return

    # Filter to jobs that actually need translation (have a title, no title_de yet)
    need = [j for j in jobs if j.title and not j.title_de]
    if not need:
        return

    log.info(f"[{source_name}] Translating {len(need)} job titles to German")

    for i in range(0, len(need), _BATCH_SIZE):
        batch = need[i:i + _BATCH_SIZE]
        titles = [j.title for j in batch]

        try:
            translated = _translate_batch(titles)
            if len(translated) != len(batch):
                log.warning(
                    f"[{source_name}] Translation count mismatch: "
                    f"sent {len(batch)}, got {len(translated)} - skipping batch"
                )
                continue
            for job, title_de in zip(batch, translated):
                job.title_de = title_de or job.title
        except Exception as e:
            log.warning(f"[{source_name}] Batch translation failed: {e}")
            # Leave title_de as None - non-critical


def _translate_batch(titles: list[str]) -> list[str]:
    """Call OpenRouter to translate a batch of titles. Returns list of German titles."""
    numbered = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(titles))

    messages = [
        {
            'role': 'system',
            'content': (
                'You translate job titles to German. '
                'If a title is already in German, return it unchanged. '
                'Keep industry-standard English terms that are commonly used in German '
                '(e.g. "Data Scientist", "DevOps Engineer", "Product Owner"). '
                'Return ONLY a JSON array of strings in the same order. No markdown fences.'
            ),
        },
        {
            'role': 'user',
            'content': f'Translate these {len(titles)} job titles to German:\n{numbered}',
        },
    ]

    payload = json.dumps({
        'model': _MODEL,
        'messages': messages,
        'max_tokens': max(len(titles) * 30, 500),
        'temperature': 0.0,
    }).encode()

    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=payload,
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read())

    content = data['choices'][0]['message']['content'].strip()
    # Strip markdown fences if present
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
        content = content.removesuffix('```')
        content = content.strip()

    return json.loads(content)
