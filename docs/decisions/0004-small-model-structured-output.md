# 0004 Structured output on a small model: guards in code, not prompt tuning

Date: 2026-11-16 · Status: accepted

## What we saw (qwen3:8b via Ollama, measured on the briefs in `eval/understand_check.py`)
1. A typed call ran away: about 4,000 tokens, 3 min 40 s, until the 4,096-token context filled.
   The model skipped optional keys, then repeated items in a list ("good view", "good price", ...).
2. Ollama loads models with a 4,096-token context and its OpenAI endpoint ignores context settings.
3. Making every key required in the schema stopped the skipping, but on sparse briefs the model
   filled every slot with invented values ("cheap room please" -> budget 3,000, HKUST, Kowloon Tong).
4. Even with optional keys it turned "cheap" into a budget and sometimes dropped a stated "40 min".

## Decision
- Every typed call sends `max_tokens` (profile `max_output_tokens`, 1,024) and has a request timeout;
  an output cut off by the limit is retried once without feeding the garbage back.
- List fields carry `maxItems` (Pydantic `max_length`), enforced by guided decoding: no list loops.
- Required-every-key is available (`require_all_keys=True`) but off by default.
- `infra/ollama/Modelfile` builds `flatjai-qwen3-8b` with `num_ctx 16384` (`make model`).
- The Understand stage grounds the profile in code (`ground_profile`): a budget must be a number the
  student wrote ("9k", "1.5萬", "八千"), else it is cleared; a stated budget or commute the model
  dropped is filled from the text. `0`/`""` placeholders mean unknown.
- The local profile uses `max_concurrency: 1` (Ollama serves one request at a time), so waiting is
  measured as `queue_ms` in our traces instead of hidden in the server.

## Result
`make eval-understand`: 6/6 briefs correct, 1 to 5 s each (was 3/6 with one 3-minute runaway).
