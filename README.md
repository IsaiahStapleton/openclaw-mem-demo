# OpenClaw Memory Stack Demo

A reproducible walkthrough of what the claw-operator's opt-in memory stack
([claw-operator PR #36](https://github.com/redhat-et/claw-operator/pull/36),
`spec.memory`) does for an agent.

Two identical OpenClaw instances are seeded with an identical two-month memory
corpus. The only difference is a two-line block in the Claw custom resource:

```yaml
spec:
  memory:
    enabled: true
```

Both instances have every note on disk. Ask them a paraphrased question about a
decision buried a month deep and:

- **`claw-plain`** (no memory stack) answers ~18s: *"I don't have that saved...
  this workspace looks fresh... remind me once and I'll keep it straight."*
- **`claw-memory`** (`spec.memory.enabled: true`) answers ~49s: *"For Beacon,
  the weather dashboard, we settled on Open-Meteo... Python + FastAPI, uv only,
  not pip"*, citing the exact memory file and line.

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
  support** (PR #36). Verify: `oc explain claw.spec.memory`
- A namespace, and a Secret holding an OpenAI API key (embeddings drive vector
  recall; the same credential drives chat).
- `oc`, `python3`, `bash`, and (for layer 3's graph) [Obsidian](https://obsidian.md).

The CRs carry no namespace; commands apply them with `-n $NS`. They expect a
Secret named `openai-api-key` (key `api-key`); create one or edit the
`secretRef` in both CR files.

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

This layer needs no prompt. The operator seeds a nightly "Memory Dreaming
Promotion" cron (`0 3 * * *`) that, on its own, promotes durable facts into
`MEMORY.md` (loaded into context every session) and writes reflections into
`DREAMS.md`. Reveal what it produced:

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- cat ~/.openclaw/workspace/MEMORY.md
oc exec -n $NS deploy/claw-memory -c gateway -- cat ~/.openclaw/workspace/DREAMS.md
```

The Beacon decision has been distilled into curated long-term memory,
autonomously. (To trigger it on demand instead of waiting for 03:00:
`openclaw memory rem-backfill --path ~/.openclaw/workspace/memory` then
`openclaw memory promote`.) The flywheel: an instance can only promote a fact it
could recall in the first place, which is why `claw-plain` never builds one.

## Layer 3 — Wiki: it organizes everything

Paste into **`claw-memory` only** (a heavy turn, ~4-5 min; time-cut it in edit):

```
Use your memory-wiki tools to build out your knowledge vault from your existing memory. Review your memory (the daily notes and MEMORY.md), and create or update wiki entity and concept pages for the projects and decisions you find, especially the Beacon project (its API choice and stack), and the other projects (Nimbus, Larkspur). Capture source-backed claims and relationships between them. Then compile the vault. Report which pages you created.
```

Then the "it doesn't just catalog, it abstracts" beat, into **`claw-memory`**:

```
Using your memory-wiki tools, write a synthesis page that abstracts the decision-making pattern across your three hobby projects: Beacon, Nimbus, and Larkspur. What do their technology/API choices have in common? Look for the shared decision criteria and any recurring preferences. Link the synthesis to the three entity pages and the relevant concept pages, with source-backed claims. Then compile the vault. Report the page you created and what pattern you found.
```

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
it is two lines of YAML on a Claw resource.

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
`recall-only.txt`, `s2probe2.txt` (rationale), `build-wiki.txt`,
`build-synthesis.txt`. (`s1p1.txt`/`s1p2.txt` are an older two-session variant;
`s2probe1.txt` is a recall+scaffold probe, heavier and OOM-prone, see caveats.)

Measured single-run A/B (recall probe): `claw-plain` ~18s / ~17.5k tokens of
amnesia vs `claw-memory` ~49s / ~21k tokens of cited recall. The memory instance
is *slower*, retrieval is not free; the result is about correctness, not speed.

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

- **Heavy multi-tool turns can OOM the memory instance's gateway** at the default
  4Gi limit (an upstream issue involving the codex harness's session mirroring
  and the wiki bridge; the pod self-recovers). Recall, rationale, and the wiki
  builds are stable; the recall+scaffold probe (`prompts/s2probe1.txt`) is the
  risky one, keep it off camera.
- Re-running conversational prompts writes new memory on `claw-memory`
  (including `MEMORY.md`), which changes later citations. For a clean repeat,
  delete both Claws and their PVCs and start from Setup.
- The wiki's entity/concept synthesis is driven by the prompts above (or ongoing
  agent activity); there is no wiki cron yet, unlike dreaming. Bridge *import* of
  raw memory is automatic, but was bypassed here by side-loading the corpus, so
  the wiki starts empty until the build prompt runs.
- `uv` is not installed in the gateway image and the proxy blocks its installer,
  so generated scaffolds cannot be fully run in-pod.
- Timings vary with model load; the numbers here are single-run observations,
  not benchmarks.
