# OpenClaw Memory Stack Demo

A reproducible walkthrough of what the claw-operator's opt-in memory stack
([claw-operator PR #36](https://github.com/redhat-et/claw-operator/pull/36),
`spec.memory`) does for an agent.

Two identical OpenClaw instances are seeded with an identical two-month memory
corpus. The load-bearing difference is one block in the Claw custom resource:

```yaml
spec:
  memory:
    enabled: true
```

(The memory instance also carries a few tuning knobs — a raised memory limit and
two dreaming thresholds, all explained inline in `claw-memory.yaml` — but
`spec.memory.enabled: true` is what turns the stack on.)

Both instances have every note on disk. Ask them a paraphrased question about a
decision buried a month deep and:

- **`claw-plain`** (no memory stack) answers ~13s: *"this appears to be a fresh
  workspace... I genuinely don't know what project or API you're referring to."*
- **`claw-memory`** (`spec.memory.enabled: true`) answers ~15s: *"The project is
  Beacon... Open-Meteo... Python + FastAPI, with dependencies managed via uv
  only, no pip"*, citing the exact memory file (`memory/2026-06-06.md`).

The point: **storing everything is trivial; remembering is a system.** The plain
instance keeps the same notes and cannot use them.

## The three layers

The demo walks the three things that turn storage into memory:

1. **Search** (retrieval) — find the right note from meaning, even a paraphrase.
2. **Dreaming** (consolidation) — promote durable facts into always-loaded
   long-term memory, autonomously, overnight.
3. **Wiki** (organization) — synthesize a self-auditing knowledge graph of
   entities, concepts, claims, and the relationships between them.

Arc: **find it → keep what matters → organize it all.**

---

# Setup (before the walkthrough)

One-time prep, done off-camera. The walkthrough itself is just pasting prompts
into two chat windows and revealing a few artifacts.

## Prerequisites

- An OpenShift/Kubernetes cluster running claw-operator **with `spec.memory`
  and `spec.resources` support** (PR #36 plus the gateway-resources change).
  Verify: `oc explain claw.spec.memory` and `oc explain claw.spec.resources`
- A namespace and two Secrets:
  - `anthropic-api-key` (key `api-key`) — the **chat model**. Layer 2 requires a
    **non-Codex** model: OpenAI models route through the Codex harness, which
    references `MEMORY.md` by pointer instead of loading its contents, so the
    consolidation payoff silently disappears. Claude loads `MEMORY.md` at session
    start. Any non-Codex model works; Claude Sonnet is the reference.
  - `openai-api-key` (key `api-key`) — an **embedding-capable** credential, used
    only to drive vector recall (Layer 1), not for chat.
- `oc`, `python3`, `bash`, and (for layer 3's graph) [Obsidian](https://obsidian.md).

The CRs carry no namespace; commands apply them with `-n $NS`. They expect
Secrets named `anthropic-api-key` and `openai-api-key` (key `api-key` on each);
create them or edit the `secretRef`s in both CR files. The image is pinned to
`2026.7.1` (needed for the Anthropic provider plugin and the non-Codex harness).

> Reference setup note: this demo was validated with Claude served via GCP Vertex
> (an `anthropic` credential of `type: gcp`). A native Anthropic API key routes
> the same Claude models through the same non-Codex harness; if you use Vertex
> instead, swap the `anthropic` credential block accordingly.

## 1. Deploy both instances

```bash
export NS=<your-namespace>
oc apply -n $NS -f claw-plain.yaml -f claw-memory.yaml
oc get claw -n $NS -w        # wait for Ready=True on both
```

`claw-plain` explicitly disables `memorySearch` in `spec.config.raw` (the
operator enables it by default from the credential; see
[Why the control disables search](#why-the-control-disables-search)).

## 2. Seed the identical corpus onto both instances

```bash
python3 gen_corpus.py         # writes corpus/ (61 files; deterministic)
for inst in claw-plain claw-memory; do
  tar -C corpus -cf - . | oc exec -i -n $NS deploy/$inst -c gateway -- \
    sh -c 'mkdir -p ~/.openclaw/workspace/memory && tar -C ~/.openclaw/workspace/memory -xf -'
done
```

## 3. Build the vector index on the memory instance

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw memory index
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw memory status
# expect: Embedding cache: enabled (61 entries)
```

## 4. Verify the preconditions

```bash
# control: search OFF
oc exec -n $NS deploy/claw-plain -c gateway -- openclaw memory status
# expect: "Memory search disabled"

# memory instance: stack active
oc get claw claw-memory -n $NS \
  -o jsonpath='{.status.conditions[?(@.type=="MemoryStack")].message}'
# expect: "Memory stack enabled with vector recall"
```

Open each instance's **WebChat** in its own browser window, tiled side by side
(`claw-plain` left, `claw-memory` right).

---

# The walkthrough

Paste each prompt into **both** chat windows unless noted. Start a fresh session
(`/new`) in each before Layer 1 so the context window is empty.

## Layer 1 — Search: it can find what matters

Paste into **both** instances (it never says "Beacon" or "Open-Meteo", so
answering it requires semantic recall, not string matching):

```
Quick question, no need to do any work: which API did we settle on for that hobby project we talked about, and what stack did we agree on?
```

**What you'll see:** `claw-plain` says it has no such context and asks to be
re-told. `claw-memory` names Beacon, Open-Meteo, FastAPI, and the uv preference,
with a citation to the exact memory file and line.

Follow up, into **both**:

```
Remind me why we ruled out the other weather APIs for that project.
```

The rejection rationale is in the corpus; `claw-memory` reproduces the real
trade-offs, `claw-plain` can only guess.

## Layer 2 — Dreaming: it keeps what matters

The operator seeds a nightly "Memory Dreaming Promotion" cron (`0 3 * * *`) that,
on its own, promotes durable facts into `MEMORY.md` and writes reflections into
`DREAMS.md`. `MEMORY.md` is loaded into context at the **start of every session**
(on a non-Codex model), so once a fact is promoted the agent knows it without
searching. Reveal what dreaming produced:

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- cat ~/.openclaw/workspace/MEMORY.md
oc exec -n $NS deploy/claw-memory -c gateway -- cat ~/.openclaw/workspace/DREAMS.md
```

`MEMORY.md` holds the Beacon decision, distilled from the raw daily log into
curated long-term memory. `DREAMS.md` is the cron's own reflection diary.

**The payoff — show it, don't just assert it.** Start a fresh session in
`claw-memory` (`/new`) and ask the Layer 1 question again:

```
Quick question, no need to do any work: which API did we settle on for that hobby project we talked about, and what stack did we agree on?
```

In Layer 1 the answer came from a semantic **search** over the corpus (you can
see the `memory_search` call and a file citation). Now it answers straight from
`MEMORY.md` — **no search, no tool calls, faster** (~10s vs ~15s), opening with
"From memory:". The fact rode in at session start. That is what promotion buys:
not "it searches faster", but "it doesn't have to look".

The flywheel: an instance can only promote a fact it could recall in the first
place, which is why `claw-plain` never builds a `MEMORY.md` at all.

> **Triggering dreaming for the recording.** The cron fires itself at 03:00. To
> promote on demand instead of waiting, run a few recalls first (Layer 1 does
> this), then:
> ```bash
> oc exec -n $NS deploy/claw-memory -c gateway -- openclaw memory promote --min-score 0.45 --apply
> ```
> Two dreaming knobs in `claw-memory.yaml` make this work at all: `minScore: 0.45`
> (the default 0.8 is unreachable for paraphrased recall, so nothing would
> promote) and `maxPromotedSnippetTokens: 1200` (the default 160 truncates the
> snippet *before* the API choice, so the recalled fact would be incomplete).

## Layer 3 — Wiki: it organizes everything

Paste into **`claw-memory` only** (a heavy turn, ~2-4 min; time-cut it in edit).
The prompt is explicit about page **type**, because the models will otherwise
tag everything as a generic `synthesis` page and you lose the entity/concept
structure that makes the graph legible (this exact prompt is `prompts/build-wiki-v2.txt`):

```
Use your memory-wiki tools to build your knowledge vault from your existing memory (the daily notes and MEMORY.md).

Use the correct pageType for each page. This matters:
- pageType "entity" for each PROJECT you find (Beacon, Nimbus, Larkspur). These go in entities/.
- pageType "concept" for each DECISION you find (the weather API choice for Beacon, the storage API choice for Nimbus, the device API choice for Larkspur). These go in concepts/.
- pageType "synthesis" for exactly ONE page that abstracts ACROSS the projects: the shared pattern in how these API decisions were made. This goes in syntheses/.

Do not put projects or decisions in syntheses/. Capture source-backed claims with line-level evidence, and link entities to their related concepts and to each other. Then compile the vault and report which pages you created and their pageType.
```

This single build produces the entity pages (Beacon, Nimbus, Larkspur), the
concept pages (each API decision), and one cross-project synthesis page — the
"it doesn't just catalog, it abstracts" beat — in one turn.

Reveal a synthesized page (cited claims + relationships):

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- \
  cat ~/.openclaw/workspace/wiki/main/entities/beacon.md
```

**Visualize the knowledge graph in Obsidian.** Extract the vault and open it:

```bash
mkdir -p wiki-vault
oc exec -n $NS deploy/claw-memory -c gateway -- \
  sh -c 'cd ~/.openclaw/workspace/wiki && tar -cf - main' | tar -C wiki-vault -xf -
```

In Obsidian: **Open folder as vault** → select `wiki-vault/main` → open
**Graph view** (`Cmd/Ctrl+G`). You'll see the three project entities (Beacon,
Nimbus, Larkspur) as hubs, their concept pages as satellites, the source notes
as provenance leaves, and the synthesis page as a top node tying all three
clusters together. For a clean view, filter out scaffolding with a graph search
of `-file:index -file:WIKI -file:AGENTS -file:inbox`, and color-group by folder
(`entities`/`concepts`/`sources`). The vault is plain markdown with relative
links, so any Obsidian-compatible (or Open-Knowledge-Format-aware) viewer
renders the same graph.

## Close

Three layers: **find it, keep it, organize it.** The plain instance had every
note and could do none of it. Storing is trivial; this is a memory system, and
the operator packages it behind a `spec.memory` checkbox on a Claw resource.

---

# Headless / scriptable alternative

Everything conversational above can be driven without a browser, which is how
the token/latency numbers were measured. `run-probe.sh` sends one agent turn via
`oc exec` and returns JSON with usage and timing (set `NS` first):

```bash
./run-probe.sh claw-plain  prompts/recall-only.txt take1 plain.json
./run-probe.sh claw-memory prompts/recall-only.txt take1 memory.json
python3 -c "import json;d=json.load(open('memory.json'));m=d['result']['meta']['agentMeta'];print(m['usage']);print(d['result']['payloads'][0]['text'])"
```

The prompts used in the walkthrough are also in `prompts/` for scripting:
`recall-only.txt`, `s2probe2.txt` (rationale), `build-wiki-v2.txt` (the explicit
pageType build). (`build-wiki.txt` is the older, under-specified build that tags
everything as a synthesis page; `s1p1.txt`/`s1p2.txt` are an older two-session
variant; `s2probe1.txt` is a recall+scaffold probe, heavier and OOM-prone.)

Measured single-run A/B on the reference stack (`2026.7.1`, Claude Sonnet):
- **Layer 1 (cold):** `claw-plain` ~13s of amnesia vs `claw-memory` ~15s of cited
  recall via `memory_search`. The memory instance is slightly slower here;
  retrieval is not free, and Layer 1 is about correctness, not speed.
- **Layer 2 (after promotion):** the same question answered from `MEMORY.md` in
  ~10s with **zero** retrieval tool calls. Consolidation is where the speed win
  shows up, because the fact is already in context.

---

# How the experiment is designed

- `gen_corpus.py` deterministically generates 61 daily logs (2026-05-09 to
  2026-07-08, 244 entries). Most are realistic noise (homelab chores, family
  notes, weather). It also plants **decoy projects** that made their own API
  decisions (a photo-backup tool on Backblaze B2, a garden dashboard on Adafruit
  IO, a newsletter on Buttondown), so naive keyword search cannot shortcut it.
- Buried on 2026-06-06: the Beacon decision, API choice (Open-Meteo), stack
  (FastAPI), the uv-never-pip preference, and the rationale for rejecting five
  other weather APIs.
- The recall prompt never names the project or API, so it requires semantic
  retrieval.
- The corpus is seeded onto BOTH instances byte-for-byte, so the contrast is
  attributable to the memory system alone.

## Why the control disables search

Two facts make an honest "no memory" baseline harder than it sounds, both
discovered by running this experiment:

1. `memory-core` is a bundled, auto-enabled OpenClaw plugin on every instance.
   Every agent writes daily memory files and reads recent ones, so at small
   scale (same-day facts) even a bare instance recalls fine. The buried-a-month
   corpus defeats that: recent-file loading misses it.
2. The operator auto-enables vector `memorySearch` from any embedding-capable
   credential (upstream
   [codeready-toolchain/claw-operator#177](https://github.com/codeready-toolchain/claw-operator/pull/177)),
   independently of `spec.memory`. So a bare instance with an OpenAI key would
   *also* have semantic recall.

To isolate the memory stack's contribution, `claw-plain` therefore sets
`agents.defaults.memorySearch.enabled: false` in `spec.config.raw`; the operator
respects a user-set `memorySearch` and backs off. That makes the control a true
"file memory only" baseline. (PR #36 itself is purely additive over #177: it
adds the wiki and dreaming layers and packages them behind `spec.memory`.)

---

# Caveats and known issues

- **The wiki build (Layer 3) OOMs the gateway at the default 4Gi limit** — it is
  a large single synthesis turn. `claw-memory.yaml` sets
  `spec.resources.limits.memory: 8Gi` to fix this, which needs a claw-operator
  that supports `spec.resources`. At 8Gi the build completes in ~2 min; at 4Gi it
  is SIGKILLed with no error and writes no pages.
- **Layer 2 requires a non-Codex chat model.** On the Codex harness (OpenAI
  models) `MEMORY.md` is injected only as a pointer, not as content, so a
  promoted fact never rides into context and the "answers without searching"
  payoff silently fails. This is why both CRs pin Claude.
- Re-running conversational prompts writes new memory on `claw-memory`
  (including `MEMORY.md`), which changes later citations. For a clean repeat,
  delete both Claws and their PVCs and start from Setup.
- The wiki's entity/concept synthesis is driven by the prompt above (or ongoing
  agent activity); there is no wiki cron yet, unlike dreaming. Bridge *import* of
  raw memory is automatic, but was bypassed here by side-loading the corpus, so
  the wiki starts empty until the build prompt runs.
- `uv` is not installed in the gateway image and the proxy blocks its installer,
  so generated scaffolds cannot be fully run in-pod.
- Timings vary with model load; the numbers here are single-run observations,
  not benchmarks.
