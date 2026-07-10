# OpenClaw Memory Stack Demo

A reproducible A/B experiment showing what the claw-operator's opt-in memory
stack ([claw-operator PR #36](https://github.com/redhat-et/claw-operator/pull/36),
`spec.memory`) actually does for an agent.

Two identical OpenClaw instances are seeded with an identical two-month memory
corpus. The only difference between them is a two-line block in the Claw
custom resource:

```yaml
spec:
  memory:
    enabled: true
```

Both instances have every note on disk. Ask them a paraphrased question about
a decision buried a month deep in the corpus and:

- **`claw-plain`** (no `spec.memory`) answers in ~18s: *"I don't have that
  saved... this workspace looks fresh... remind me once and I'll keep it
  straight going forward."*
- **`claw-memory`** (`spec.memory.enabled: true`) answers in ~49s: *"For
  Beacon, the hobby weather dashboard, we settled on Open-Meteo... Python +
  FastAPI, with dependencies managed by uv only, not pip"*, citing the exact
  memory file and line numbers.

The point: **storing everything is trivial; remembering is a system.** The
plain instance keeps the same notes and cannot use them. The memory stack adds
the pieces that close that gap: semantic (vector) recall, the memory-wiki
knowledge layer, and dreaming consolidation, packaged as one CR field.

## How the experiment is designed

- `gen_corpus.py` deterministically generates 61 daily memory logs
  (2026-05-09 to 2026-07-08, 244 entries). Most entries are realistic noise:
  homelab chores, family notes, weather small talk. It also contains decoy
  projects that made their own API decisions (a photo-backup tool on
  Backblaze B2, a garden-sensor dashboard on Adafruit IO, a newsletter on
  Buttondown), so naive keyword search cannot shortcut the test.
- Buried on 2026-06-06: the "Beacon" hobby project decision, its API choice
  (Open-Meteo), the stack (Python + FastAPI), a working preference (uv, never
  pip), and the full rationale for rejecting five other weather APIs.
- The recall probe (`prompts/recall-only.txt`) deliberately never says
  "Beacon" or "Open-Meteo". Answering it requires semantic retrieval, not
  string matching.
- The corpus is seeded onto BOTH instances byte-for-byte, so the contrast is
  attributable to the memory system alone.

## Why the control instance needs the gated operator

Two facts make an honest "no memory" baseline harder than it sounds, and both
were discovered by running this experiment:

1. `memory-core` is a bundled, auto-enabled OpenClaw plugin on every instance.
   Every agent writes daily memory files and can read recent ones. At small
   scale (facts from the same day) the baseline recalls fine.
2. Before PR #36's gating fix, the operator auto-enabled vector memory search
   from any embedding-capable credential (regardless of `spec.memory`), so the
   baseline had semantic recall too and the A/B showed no contrast at any
   scale.

PR #36 gates semantic search behind `spec.memory.enabled`. With the gated
operator, the control instance's config carries
`memorySearch.enabled: false` and the CLI reports "Memory search disabled".
This experiment therefore requires an operator build that includes PR #36.

## Prerequisites

- An OpenShift/Kubernetes cluster running claw-operator **with `spec.memory`
  support** (PR #36). Verify with: `oc explain claw.spec.memory`
- A namespace you can deploy to, and a Secret holding an OpenAI API key
  (embeddings are required for vector recall; the same credential drives chat)
- `oc`, `python3`, and `bash` locally

The CRs carry no namespace; every command below applies them with `-n $NS`.
They expect a Secret named `openai-api-key` (key `api-key`) in that namespace;
either create one or edit the `secretRef` in both CR files to point at yours.

## Repository contents

| File | Purpose |
|---|---|
| `claw-plain.yaml` | Control instance CR (no `spec.memory`) |
| `claw-memory.yaml` | Memory instance CR (`spec.memory.enabled: true`) |
| `gen_corpus.py` | Deterministic 61-day corpus generator (writes `corpus/`) |
| `prompts/recall-only.txt` | The paraphrased recall probe (the headline test) |
| `prompts/s2probe2.txt` | Decision-rationale probe |
| `prompts/s2probe1.txt` | Recall + scaffold probe (see caveats before using) |
| `prompts/s1p1.txt`, `prompts/s1p2.txt` | Interactive two-session variant of the scenario |
| `run-probe.sh` | Headless probe runner (`oc exec` + `openclaw agent --json`) |

## Running the experiment

### 1. Deploy both instances

```bash
export NS=<your-namespace>
oc apply -n $NS -f claw-plain.yaml -f claw-memory.yaml
oc get claw -n $NS -w   # wait for Ready=True on both
```

### 2. Seed the identical corpus onto both instances

```bash
python3 gen_corpus.py    # writes corpus/ (61 files; deterministic seed)
for inst in claw-plain claw-memory; do
  tar -C corpus -cf - . | oc exec -i -n $NS deploy/$inst -c gateway -- \
    sh -c 'mkdir -p ~/.openclaw/workspace/memory && tar -C ~/.openclaw/workspace/memory -xf -'
done
```

### 3. Build the vector index on the memory instance

```bash
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw memory index
oc exec -n $NS deploy/claw-memory -c gateway -- openclaw memory status
# expect: Embedding cache: enabled (61 entries)
```

### 4. Verify the preconditions

```bash
# Control: semantic search must be OFF
oc exec -n $NS deploy/claw-plain -c gateway -- openclaw memory status
# expect: "Memory search disabled"

# Memory instance: stack active with vector recall
oc get claw claw-memory -n $NS \
  -o jsonpath='{.status.conditions[?(@.type=="MemoryStack")].message}'
# expect: "Memory stack enabled with vector recall"
```

### 5. Run the probes

`run-probe.sh` drives a headless agent turn. A new `--session-key` is a fresh
session, so each probe below starts with an empty context window. It reads
the namespace from `$NS`.

```bash
./run-probe.sh claw-plain  prompts/recall-only.txt take1 plain.json
./run-probe.sh claw-memory prompts/recall-only.txt take1 memory.json

# Read the answers and token usage:
python3 -c "import json;d=json.load(open('plain.json'));print(d['result']['payloads'][0]['text'])"
python3 -c "import json;d=json.load(open('memory.json'));m=d['result']['meta']['agentMeta'];print(m['usage']);print(d['result']['payloads'][0]['text'])"
```

Follow up with the rationale probe (`prompts/s2probe2.txt`, a new session
key): the rejection rationale for the other APIs is in the corpus; the memory
instance retrieves the real trade-offs, the control cannot.

You can also run the probes interactively in each instance's WebChat instead
of headlessly; for a clean session boundary use `/new` and optionally
`oc rollout restart deploy/<name> -n $NS`.

### Expected results

| | `claw-plain` | `claw-memory` |
|---|---|---|
| Recall probe outcome | Asks to be re-told the project, API, and stack | Names Beacon, Open-Meteo, FastAPI, uv, with file citations |
| Observed latency | ~15-20s | ~30-60s |
| Observed tokens | ~17.5k | ~21k |

Note the memory instance is *slower*, retrieval work is not free. The result
is about correctness, not speed.

### The consolidation follow-on

After the memory instance has recalled the buried facts once, check
`~/.openclaw/workspace/MEMORY.md` on both instances. The memory instance
distills the recalled decision into curated long-term memory (loaded into
context at every session start); the control never develops a `MEMORY.md` at
all. `MEMORY.md` maintenance is bundled memory-core behavior available to
both, and that is the finding: an instance that cannot retrieve a fact can
never promote it. Recall is what makes the other memory layers compound.

## Caveats and known issues

- **Heavy multi-tool turns can OOM the memory instance's gateway** at the
  operator's default 4Gi memory limit (upstream OpenClaw issue involving the
  codex harness session mirroring and the memory-wiki bridge; the pod
  self-recovers). The recall and rationale probes are stable; the scaffold
  probe (`prompts/s2probe1.txt`) is the risky one.
- Re-running probes writes new memory on the memory instance (including
  `MEMORY.md`), which changes later recall citations. For a clean repeat of
  the experiment, delete both Claws and their PVCs and start from step 1.
- `uv` is not installed in the OpenClaw gateway image and the egress proxy
  blocks its installer, so generated project scaffolds cannot be fully run
  in-pod.
- Probe timings vary with model load; the numbers above are single-run
  observations, not benchmarks.
