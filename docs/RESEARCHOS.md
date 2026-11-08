# ResearchOS: run the implemented TECT workflow

Requires Python 3.10+. Use a separate virtual environment per repository; the vendored `researchos` package and command intentionally share a name and must not be co-installed from multiple repositories into one environment. The bundles share a common versioned interchange contract, not a live cross-repository database. Install the repository package as usual; existing domain commands remain available.

```sh
python -m pip install .
mkdir -p runs
researchos pilot --output runs/pilot
# Expected exit 1: computed support exists, but domain attacks and separate reproduction are missing.
researchos verify runs/pilot
# Expected exit 0: the unresolved report and its ledger replay consistently.
```

Without installation, use `python -m researchos`. Each destination must be new and its parent must exist. Reports contain captured evidence and source metadata; use synthetic/public inputs for public CI and keep confidential real evidence private.

The pilot executes the fixed repository-specific adapter, captures its configuration, measured outputs and adapter-source SHA256, and runs three isolated controller attack probes (source poisoning, contradiction injection, assumption violation). These probes test the controller, not the domain claim's robustness. The claim stops at ADVERSARIAL_TEST with explicit missing domain attack and separate reproduction blockers. Nothing is marked deployment-ready.

```sh
researchos evaluate examples/researchos/unsupported.json --output runs/unsupported
# Expected exit 1: missing evidence yields UNCERTAIN.
researchos benchmark examples/researchos/observations.json
python -m unittest discover -s tests -p test_researchos.py -v
python tests/check_researchos_installed.py
```

The benchmark fixture is one synthetic observation, deliberately **not** a fabricated four-condition study. Missing baseline conditions, undefined rates and absent matched-task coverage remain visible. Pilot timestamps are a fixed fictional assessment fixture; rerun with an explicit scenario and current evidence intervals for another assessment. No automatic freshness is implied.

## Exit semantics

| Command | 0 | 1 | 2 |
|---|---|---|---|
| pilot/evaluate | Nonempty claim set all ASSURED under declared policy | Bundle completed with unresolved/contested/unassured claims | Invalid input, I/O or resource failure |
| verify | Exact replay matches, including unresolved/failed decisions | Not used | Replay mismatch or invalid bundle |
| benchmark | Descriptive computation completed | Not used | Invalid observations |

Read the full `ledger.json`, claim state and `assurance_blockers` instead of treating successful file creation or replay as knowledge acceptance.

## Python API

```python
from researchos import Controller, policy_default

controller = Controller(policy_default(), '2026-11-08T00:00:00Z')
event = controller.apply({
    'op': 'register', 'actor': 'author',
    'data': {'id': 'candidate', 'statement': 'A scoped candidate assertion',
             'provenance': ['local:experiment-1'], 'confidence': 0.5,
             'assurance_scope': 'Offline research review only'}
})
print(event['outcome'])
print(controller.report()['state']['claims']['candidate']['state'])
```

Available operations are register, evidence, transition, challenge, resolve, revise, relation and reassess. Use `expected_version` for stale-write rejection. See [the versioned specification](TECT_SPEC.md), [schemas](../schemas/researchos-scenario.schema.json), and [research plan](TECT_RESEARCH_PLAN.md). Schemas describe serialization shape; runtime semantic checks additionally enforce versions, roles, time, hashes, dependency readiness and transition predicates.

No credentials, model accounts, paid services or cloud infrastructure are needed. The supplied roles, sources and independence estimates are declarations. The implementation is an offline research assurance prototype, not identity management, a truth oracle or certification.
