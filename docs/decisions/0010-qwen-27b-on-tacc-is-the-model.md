# 0010 Qwen 27B on TACC is FlatJai's model; a model on your own machine is the fallback

Date: 2026-11-22 · Status: accepted

## Context
The course serves Qwen3.8-27B (AWQ INT4, vLLM, 2 GPUs, 32K context) as a TACC GPU job. It is the
largest model available to the project and the one E3 evaluates: it confirms more limits than an 8B
model (62% against 52%) and answers a brief in a median of 19 s. Its URL is internal to the cluster,
the job lasts an hour and takes 4 to 7 minutes to load, and reaching TACC needs the HKUST network or
VPN. Anyone running FlatJai must be able to tell which model they are using, and the default must be
the one the results are about.

## Decision
- **27B on TACC is the default model.** `./setup.sh` asks where the model runs, with TACC first and
  preselected; the answer goes into `.env` (`FJ_MODEL=tacc-tunnel`). The settings default and
  `.env.example` say the same.
- **The app reaches it through an SSH tunnel.** `./run.sh app` submits the course's serve job, opens
  `localhost:8001` to it through the TACC gateway as the person running it (credentials from
  tcloud's own config), waits for the model, runs the app, and cancels the job on exit. Search,
  routing, storage and the UI stay on the user's machine; only model calls cross the tunnel.
- **The evaluation runs inside TACC** (`./run.sh suite`, profile `tacc`), next to the service, so a
  long suite does not depend on the user's connection.
- **Qwen3 8B through Ollama is the fallback** for anyone without TACC access (`./setup.sh --model
  local`, or `./run.sh app --model local` for one run). It downloads ~5 GB and needs 16 GB of RAM.
- One time budget for both (`RUN_MAX_SECONDS=240`): 27B extracts each page itself the first time it
  reads it, as in the E3 runs.

## Consequences
- A first `./run.sh app` takes about 5 minutes before the first brief; the job must be cancelled to
  free shared GPUs (Ctrl-C does it). After an hour the service ends and the app needs a restart.
- Targets that call the model (`make dev`, `make eval`, `make ablate`, `make check-model`) stop with
  a hint when the profile is `tacc-tunnel` and no tunnel is open.
- E1 and E2 were run on 8B and stay reported as such; they show the design does not depend on the
  large model. E3 reports 27B. Graders without TACC access can rescore the shipped E3 runs.
