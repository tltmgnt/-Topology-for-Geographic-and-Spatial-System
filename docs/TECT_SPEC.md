# ResearchOS / TECT specification 0.1.0

Status: executable research prototype derived from the user-supplied September 2026 concept draft. This is neither a solicitation response nor a claim that the research hypotheses or illustrative targets have been achieved. AI generation is not knowledge acceptance.

## Implemented architecture

Structured claim registration → epistemic graph → evidence receipts → validation gates → adversarial/reproduction gates → declared-role governance → versioned ledger and assurance record. The generator and human claim-extraction process remain outside this offline library. No model, network, source retrieval or arbitrary executable command is invoked by scenario data. The repository-specific pilot calls a fixed adapter in `researchos/domain.py`.

All ten repositories in the topology series receive the same versioned `researchos` core, with one repository-specific adapter. `core_manifest.json` records hashes of the shared Python modules. Packaging includes these modules and the `researchos` CLI alongside existing domain tools. Each copy is independently reviewable; copies do not auto-update one another. The manifest is a synchronization aid, not an authenticity certificate.

## State and graph contracts

A claim has stable `id`, content `version`, statement, provenance references, confidence in [0,1], scope, state, challenges, reassessment reasons and last-validation timestamp. Content changes increment the claim version; old evidence remains in the record and cannot support the revised content. Global state version increments for every accepted operation. Optional `expected_version` enforces optimistic concurrency. Getters return detached copies.

States proceed only through adjacent transitions:

GENERATED → UNVERIFIED → SUPPORTED → ADVERSARIAL_TEST → REPRODUCED → VALIDATED → STABLE → ASSURED.

CONTESTED is entered by challenges, failed evidence and expired prerequisite checks. Unresolved challenges must receive a reviewer resolution tied to current passing validation evidence recorded **after** the challenge before returning to UNVERIFIED. Registration and revision cannot erase challenge history. New evidence on an advanced claim reopens review. Revisions, changes in relations and upstream failures propagate reassessment to dependent claims.

All `supports`, `derives`, `depends_on`, `reproduces` and `qualifies` edges have the same explicit computational orientation: **source is a prerequisite of target**. These edges must form a DAG in this prototype. This restriction is an implementation boundary, not a claim that all real reasoning graphs are acyclic. `contradicts` and `invalidates` create challenges on the target. No relation deletes historical evidence. Existing edges cannot be silently removed through the API.

A prerequisite must be at least SUPPORTED before target support/adversarial testing and at least VALIDATED before target reproduction or later promotion. Changing an edge changes incident reasoning degree and reopens both affected evidence assessments. Dependencies are supplied assertions, not inferred causal relationships.

## Evidence and independence

An evidence receipt records stable ID, claim and content version, kind (`validation`, `reproduction`, `attack`), PASS/FAIL/UNCERTAIN result, source, method, run identity, declared provenance group, weight, quality, reliability, independence estimate, observation and expiry timestamps, actual base64 bytes and SHA256. The actor and ledger sequence are added by the controller. Attack evidence additionally names a registered attack class and a normalized declared distance.

Evidence is current exactly when observation ≤ explicit assessment time < expiry. Future, expired, empty, malformed or mismatched evidence is rejected. Dates and byte agreement do not authenticate the source or establish the truth/relevance of artifact contents. Existing evidence IDs are immutable. Imported outcomes, quality, independence, run IDs and distances are declarations of the submitting evaluator. The controller does not scientifically verify those declarations.

For current passing validation receipts, correlation clusters connect receipts with the same group **or** identical content hash, including transitive connections. Each cluster contributes only its maximum `weight × quality × reliability × independence`. Density is the sum of these maxima divided by `1 + incident reasoning degree`. This is the draft's D_v implemented with conservative de-duplication, not a calibrated probability or independence estimator; density may exceed one. Different group names and byte hashes do not prove statistical independence.

Required validation methods are explicit in policy. The latest current result per required method must be PASS; a later UNCERTAIN result cannot be hidden behind an earlier pass. Preliminary support also requires minimum density and correlation-cluster count. A failed receipt creates a material challenge, even if other support remains.

Reproduction requires a passing current reproduction receipt separated from at least one passing validation receipt by actor, run ID, method, group and artifact hash. This checks declared separation only. A caller can fabricate those labels; independent scientific execution requires an external trust boundary. Re-running the same code is not automatically credited as independent reproduction.

## Gates and outcomes

| Target | Additional predicates |
|---|---|
| UNVERIFIED | Adjacent registration transition, or resolved challenge reassessment |
| SUPPORTED / ADVERSARIAL_TEST | Provenance, prerequisite readiness, required methods PASS, minimum support, no unresolved challenge |
| REPRODUCED / VALIDATED | Above plus latest PASS in every required attack class and separated reproduction |
| STABLE | Above plus every current passing attack receipt's declared distance strictly below epsilon |
| ASSURED | Above plus explicit nonempty mission/use scope and reviewer role |

An accepted operation has outcome PASS, even when that operation correctly records failed evidence or a challenge. An inadmissible/malformed operation has outcome FAIL. A well-formed promotion lacking evidence has outcome UNCERTAIN. Thus **operation PASS does not imply claim correctness or assurance**. Rejected operations preserve the prior state and are retained in the ledger. Non-JSON/nonfinite transport inputs are rejected before state mutation and cannot be serialized as ledger operations.

`STABLE` is only this encoded finite, declared-attack gate. It neither evaluates a supremum over an attack family nor certifies unseen robustness. Controller attack probes are separate from domain attack evidence and never automatically satisfy a domain gate. `ASSURED` is local acceptance for the encoded scope and policy; it is not a certification or permission to act.

## Governance and time

Actors and their roles are configured in the scenario: author, validator, adversary, reproducer and reviewer. Each operation enforces a role and exact field contract; unknown operations/fields fail closed. Scenario actor names are **not authentication**. Anyone controlling the scenario or Python process can define a new policy. An external authenticated service, signed receipts and trusted storage are future integrations, not implemented controls.

`reassess` advances explicit assessment time monotonically under reviewer authority. It reopens claims whose current gate predicates fail, including expiry, and propagates to dependents. There is no background clock, scheduler or monitoring service; callers must submit a reassessment. Policies are fixed per scenario; a different policy starts a new root rather than silently rewriting history.

`execution_authorized` and `clinical_use_authorized` are always false, including for ASSURED claims. Existing biomedical, geographic and finite-state semantics remain intact. No deployment, experiment, trading, treatment, infrastructure action or robot execution is implemented.

## Ledger and replay

A bundle contains exactly `scenario.json`, `ledger.json` and `report.json`. Every event binds its operation, actor, deterministic assessment timestamp, outcome, reasons, before/after state hashes and previous event hash. The root binds engine version, initial policy and initial assessment time. The report includes state, evidence, density, current assurance blockers, potential terms and ledger head.

`verify` replays every operation from the captured initial scenario and compares all canonical output bytes. It detects edits to reports and rehashed event chains inconsistent with execution. Replacing the entire scenario and regenerating a bundle yields another internally consistent record; without an externally trusted root this is not tamper-proof, signed, append-only durable storage or authenticated provenance. Ledger events exist in memory until exported. Concurrent hostile filesystem writers are unsupported.

Files are bounded to 8 MiB, reject duplicate keys/nonfinite values/symlinks, and are UTF8 JSON. Output directories are exclusively created; existing outputs are preserved. A handled failure removes only the newly created partial output. Limits are 128 claims, 512 relations, 1024 evidence receipts, 2000 operations, 64 KiB per decoded receipt and approximately 1 MiB total decoded evidence. Reports can hit the separate output limit before object-count limits. Malformed policy/scenario roots are rejected before a ledger is constructed.

## Metrics and theoretical limits

The potential reports equal-weight counts of unsupported states (below VALIDATED), unresolved challenges, missing provenance, encoded governance deficiencies and missing attack classes. These are research diagnostics, not a control law: accepted transitions are **not** constrained to decrease this potential. Correctly discovering a contradiction can increase it. No termination/convergence result is claimed for this implementation.

`state_distance` is a normalized distance on a projection combining claim-state mismatch, confidence L1, and relation/evidence Jaccard distances. Different statements or provenance can project to distance zero, so it is not a metric on the full epistemic state. Imported attack distances are not automatically computed or certified with this helper.

The draft's convergence claim needs qualification. Strict descent gives finite termination on a **finite** state space when every nonstable step strictly descends and the process can continue. On a merely compact state space, nonincreasing bounded potential plus strict descent does not ensure reaching a stable region or that a limit is stable. For example x → x/2 on [0,1], with stability defined only at zero, strictly decreases positive potential forever without reaching zero. Additional uniform progress, closedness, continuity or another appropriate convergence argument is required for a particular result.

A validation margin exceeding a perturbation distance is also insufficient without a specified relation between that metric, the decision function and its sensitivity (for example an appropriate Lipschitz bound). This prototype does not implement or claim the draft's adversarial-resilience theorem. Stability is not truth; stable false beliefs remain a research risk.

## Experiments

`benchmark` computes descriptive throughput, labeled accepted false-claim rate, reproduction rate, failure detection, audit time and reviewer effort from supplied observations. Unknown ground truth and undefined denominators remain explicit. It reports missing/mismatched task inventories across human-tools, single-model, unstructured multi-agent and ResearchOS conditions. It does not run human/model baselines, infer ground truth, establish independent observations or calculate significance. Synthetic fixtures must remain labeled synthetic.

Illustrative 5× throughput, 95% reproduction/coverage and 50% audit-time reduction targets from the draft are **unmeasured objectives**, not achieved results. See the research plan for remaining work.
