# OpenClaw Memory Stack Demo

Two identical OpenClaw instances share the same two-month memory corpus. The only
real difference is one block in the Claw custom resource:

```yaml
spec:
  memory:
    enabled: true
```

Ask both a paraphrased question about a decision buried a month deep:

- **`claw-plain`** (no stack): *"this workspace looks fresh, I don't know what
  project or API you mean."*
- **`claw-memory`** (`spec.memory.enabled: true`): names the project, API, and
  stack, citing the exact memory file.


## The three stages

1. **Search** — find a buried note from meaning, even a paraphrase.
2. **Dreaming** — consolidate durable facts into `MEMORY.md`, which loads into
   every new session automatically.
3. **Wiki** — organize memory into a self-auditing knowledge graph (entities,
   concepts, and the relationships between them).

---

# Setup

## Prerequisites

- A cluster running claw-operator with **`spec.memory` and `spec.resources`**
  support (PR #36 + the gateway-resources change).
- Two Secrets (key `api-key` each): a **chat-model** credential and an
  **embedding** credential (OpenAI). The chat model **must be non-Codex**
  (Claude): OpenAI models route through the Codex harness, which does *not* load
  `MEMORY.md` into context and silently breaks Layer 2. Exact credential blocks
  are in the CR files.
- `oc`, `python3`, `bash`, and [Obsidian](https://obsidian.md) for the Layer 3 graph.
- Both CRs pin image `2026.7.1`.

## Steps

```bash
export NS=<your-namespace>

# 1. Deploy both instances, wait for Ready=True on both
oc apply -n $NS -f claw-plain.yaml -f claw-memory.yaml
oc get claw -n $NS -w

# 2. Seed the identical corpus onto both
python3 gen_corpus.py            # writes corpus/ (61 files, deterministic)
for inst in claw-plain claw-memory; do
  tar -C corpus -cf - . | oc exec -i -n $NS deploy/$inst -c gateway -- \
    sh -c 'mkdir -p ~/.openclaw/workspace/memory && tar -C ~/.openclaw/workspace/memory -xf -'
done

# 3. Build the vector index on the memory instance
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw memory index

# 4. Verify preconditions
oc exec -n $NS deploy/claw-plain -c gateway -- openclaw memory status   # expect: "Memory search disabled"
oc get claw claw-memory -n $NS -o jsonpath='{.status.conditions[?(@.type=="MemoryStack")].message}'
# expect: "Memory stack enabled with vector recall"
```

Open each instance's **WebChat** side by side (`claw-plain` left, `claw-memory` right).

---

# Walkthrough

Start a fresh session (`/new`) in each instance before Layer 1.

## Layer 1 — Search

Paste into **both** (it never names Beacon or Open-Meteo, so it needs semantic
recall, not keyword matching):

```
Quick question, no need to do any work: which API did we settle on for that hobby project we talked about, and what stack did we agree on?
```

`claw-plain` has no context and asks to be re-told. `claw-memory` names Beacon,
Open-Meteo, FastAPI, and the uv preference, citing the exact file. Optional
follow-up into both: *"Remind me why we ruled out the other weather APIs."*

## Layer 2 — Dreaming

Run the dreaming cron (after Layer 1 — it only promotes facts that were recalled):

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw cron list        # find the "Memory Dreaming Promotion" job id
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw cron run <job-id>
```

It writes `DREAMS.md` (reflections) and promotes the Beacon decision into
`MEMORY.md`. Reveal both:

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- sh -c 'cat ~/.openclaw/workspace/MEMORY.md'
oc exec -n $NS deploy/claw-memory -c gateway -- sh -c 'cat ~/.openclaw/workspace/DREAMS.md'
```

**The payoff:** start a fresh session and ask the Layer 1 question again. This
time it answers straight from `MEMORY.md` — no search, no tool calls, faster —
because the promoted fact loads at session start. Not "it searches faster", but
"it doesn't have to look".

## Layer 3 — Wiki

Paste into **`claw-memory` only** (~2-4 min; this exact prompt is
`prompts/build-wiki-v3.txt`):

```
Use your memory-wiki tools to build your knowledge vault from your existing memory (the daily notes and MEMORY.md).

Use the correct pageType for each page. This matters:
- pageType "entity" for each project you find. These go in entities/.
- pageType "concept" for each significant decision you find. These go in concepts/.
- pageType "synthesis" for a page that abstracts across projects: a pattern that only becomes visible when you compare them. These go in syntheses/.

Do not put projects or decisions in syntheses/. Capture source-backed claims with line-level evidence, and link entities to their related concepts and to each other. Then compile the vault and report which pages you created and their pageType.
```

The prompt names no projects and no decisions: the agent discovers them. It defines
the page **vocabulary** (and the directory each type lands in) because that is what
memory-wiki enforces — a page's type is derived from its directory, and a page
outside `entities/`, `concepts/`, `sources/`, `syntheses/`, or `reports/` is
invisible to the vault. `prompts/build-wiki-v2.txt` is the earlier, more prescriptive
version (it named Beacon/Nimbus/Larkspur and pre-stated the synthesis pattern); keep
it as a fallback if a run tags everything `synthesis` and the structure collapses.

Extract the vault and open it in Obsidian:

```bash
mkdir -p wiki-vault
oc exec -n $NS deploy/claw-memory -c gateway -- \
  sh -c 'cd ~/.openclaw/workspace/wiki && tar -cf - main' | tar -C wiki-vault -xf -
```

**Open folder as vault** → `wiki-vault/main` → **Graph view** (`Cmd/Ctrl+G`): the
three projects as hubs, their decisions as concept satellites, source notes as
leaves, and one synthesis page tying the clusters together.

**Close:** find it, keep it, organize it. The plain instance had every note and
could do none of it. The operator packages the whole thing behind a `spec.memory`
checkbox.

---

# Notes

- **Non-Codex chat model is required** (see Prerequisites) — this is why both CRs
  pin Claude.
- **`claw-memory` sets `spec.resources.limits.memory: 8Gi`** — the Layer 3 wiki
  build OOMs (silent SIGKILL, no pages written) at the 4Gi default.
- **Two dreaming knobs in `claw-memory.yaml` are required:** `minScore: 0.45`
  (the default 0.8 never promotes paraphrased recall) and
  `maxPromotedSnippetTokens: 1200` (the default 160 truncates the snippet before
  the API choice).
- **`claw-plain` disables `memorySearch`.** The operator auto-enables vector
  search from any embedding credential (upstream
  [#177](https://github.com/codeready-toolchain/claw-operator/pull/177)), so the
  control must turn it off to be a true "file memory only" baseline. PR #36 is
  purely additive over #177 (adds wiki + dreaming behind `spec.memory`).
- **Clean repeat:** delete both Claws and their PVCs, then redo Setup —
  conversational turns mutate `MEMORY.md`.
- If `cron run` returns a scope-upgrade error, append
  `--token "$(oc get secret claw-memory-gateway-token -n $NS -o jsonpath='{.data.token}' | base64 -d)"`.

## Corpus

`gen_corpus.py` generates 61 deterministic daily logs (2026-05-09 → 2026-07-08,
244 entries): mostly noise, plus decoy projects with their own API decisions
(Backblaze B2, Adafruit IO, Buttondown). The Beacon decision is buried on
2026-06-06. Seeded byte-for-byte onto both instances, so the contrast is
attributable to the memory system alone.

## Headless

`run-probe.sh` drives one agent turn via `oc exec` and returns JSON with
timing/usage:

```bash
./run-probe.sh claw-memory prompts/recall-only.txt take1 memory.json
```

Reference single-run timings (`2026.7.1`, Claude Sonnet; vary with load): Layer 1
cold ~13s (plain) vs ~15s (memory, via search); Layer 2 ~10s with zero tool
calls (answered from `MEMORY.md`).
