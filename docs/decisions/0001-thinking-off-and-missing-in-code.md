# 0001 Typed calls run with Qwen3 thinking off; missing constraints are checked in code

Date: 2026-11-16 · Status: accepted

## Context
The M0 check (`make check-model`) on `qwen3:8b` passed but took 73 s: the model spent about 1,000
tokens "thinking" before the JSON, and still missed the commute limit, "own room" and "quiet".
The model also filled `missing` (hard constraints to ask about) wrongly.

## Decision
- Each profile in `backend/models.yaml` carries `extra_body` that turns thinking off for typed calls
  (Ollama: `reasoning_effort: none`; vLLM/Qwen on TACC: `chat_template_kwargs.enable_thinking: false`).
  The JSON schema already structures the answer.
- The Understand prompt gives phrase-to-field rules and one worked example.
- `Profile.missing()` is computed in code from the null hard constraints (budget, campus, move-in).
  It is a fact, not a judgement; the model keeps deciding *whether* to ask (M2).

## Result
Same brief: all fields correct, 7.6 s, 60 output tokens (was 73 s, 1,020 tokens, 3 fields wrong).

## Revisit
Experiment E3 can turn thinking back on for the Reflect stage only if it improves grounding.
