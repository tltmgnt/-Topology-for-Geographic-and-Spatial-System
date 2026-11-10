# Topology compatibility and curriculum v2 — -Topology-for-Geographic-and-Spatial-System

The verified edition of version 2 adapts the explicit-molecular-graph teaching pattern to this repository's actual role. This edition adds executable learning checks and reviewed answer keys. It does not introduce a new topology engine or grant operational permission.

## Repository decision

| Question | Repository-specific answer |
| --- | --- |
| Architectural role | specialized spatial tool |
| Minimum useful mathematics | Graph connectivity/routing and explicit polygon predicates |
| Relationships to preserve | Edge identity, direction, distance units, outages and spatial relations |
| Concrete operation / capstone | Remove a bridge in a synthetic network and compare components and routes; keep legacy and opt-in Engine 2.0 contracts distinct |
| Necessity and scope boundary | A route or polygon result does not establish map completeness, geographic safety or source authenticity |

The decision is a source-based recommendation, not measured proof that a new specialty improves this repository. Start with the existing implementation and compare any proposed abstraction against a simpler alternative.

## Six-criterion compatibility scorecard

Complete one scorecard per proposed candidate and per concrete operation. Leave unmeasured entries unknown. Scores are human judgments from 0 (no fit) to 5 (strong evidenced fit); unknown is not zero. Do not sum an incomplete card. A total out of 30 is a heuristic, not adoption approval, and feasibility or necessity can veto a high total.

| Criterion | Score | Required evidence |
| --- | --- | --- |
| Structural compatibility | Not yet scored | Map the repository objects and the relationships above without losing direction, labels, units or missingness. |
| Transformation support | Not yet scored | Demonstrate the capstone operation on accepted and rejected inputs. |
| Invariant preservation | Not yet scored | State the property preserved and supply a counterexample or perturbation. |
| Computational feasibility | Not yet scored | Measure size, time and memory on bounded fixtures; record limits. |
| Integration compatibility | Not yet scored | Verify existing schemas, APIs and neighboring contracts remain compatible. |
| Mathematical necessity | Not yet scored | Compare with graph connectivity/routing and explicit polygon predicates and explain the additional capability, if any. |

## Curriculum

Prerequisites: basic programming, sets, functions and graph vocabulary. Work in six competency-gated sessions, approximately 60–90 minutes each; empirical evaluation is a separate research activity.

| Session | Learning objective | Exercise | Completion evidence |
| --- | --- | --- | --- |
| 1. Model | Identify edge identity, direction, distance units, outages and spatial relations. | Draw a minimal valid example and one excluded relationship. | Annotated object/relation inventory with explicit assumptions. |
| 2. Contract | Distinguish schema validity from substantive correctness. | Trace validation and propose malformed, missing and boundary inputs. | Input-to-rejection table grounded in current source. |
| 3. Operation | Explain graph connectivity/routing and explicit polygon predicates. | Remove a bridge in a synthetic network and compare components and routes; keep legacy and opt-in Engine 2.0 contracts distinct. | Hand trace compared with existing software, or a clearly labeled specification when no runtime exists. |
| 4. Preservation | State what a transformation must preserve. | Rename identifiers, reorder records, then alter one meaningful relation; predict each effect under the actual contract. | Separate invariant, expected change and unsupported transformation. |
| 5. Comparison | Justify mathematical necessity and cost. | Complete the six-criterion card for the existing approach and one proposed alternative; record unknowns honestly. | Evidence-backed recommendation with baseline and explicit veto conditions. |
| 6. Reproduction | Communicate the bounded result. | Reproduce the capstone using existing offline fixtures and record software version, inputs, outputs and limitations. | Reviewable notebook or report distinguishing computation, replay, independent evaluation and authorization. |

## Worked reasoning and source explanation

The synthetic a—b—c route costs 2+3=5 supplied metres. Removing bc yields components {a,b}, {c}, {d}; removing b yields {a}, {c}, {d}. shortest_path() returns None for the isolated d rather than a zero distance. The lesson calls the legacy adjacency functions directly and makes no claim to validate Engine 2.0 polygon, directed-routing or geospatial import contracts.

Read the [inspected source](https://github.com/tltmgnt/-Topology-for-Geographic-and-Spatial-System/blob/113013012f1de5ef8d2f88196bc95e7edd5a2662/spatial_topology/analysis.py) alongside the [executable answer key](../../curriculum/lab.py). The source link is pinned to the inspected revision; the lab and any explicitly described fix are in this change.

## Run the worked laboratory

From the repository root, with Python 3.12 (the recorded local version is 3.12.14):

```sh
python curriculum/lab.py --verify
```

The lab checks **6 explicit expectations** against existing repository functions. It prints a JSON case report and exits nonzero on a wrong result. `--verify` additionally compares the entire case report with [expected.json](../../curriculum/expected.json). Read the input and predict each result before opening the answer key. No API account, credentials, model download, trading action or equipment connection is needed.

| Checkpoint | Expected answer |
| --- | --- |
| isolated vertex remains visible | `[["a", "b", "c"], ["d"]]` |
| weighted route a-to-c | `{"distance_m": 5.0, "edges": ["ab", "bc"], "nodes": ["a", "b", "c"]}` |
| edge bc is a separating bridge | `[["a", "b"], ["c"], ["d"]]` |
| vertex b separates the chain | `[["a"], ["c"], ["d"]]` |
| unreachable endpoint returns explicit missing route | `null` |
| zero-length self route | `0.0` |

The comparisons above encode independently specified small examples and contract expectations; a passing answer key is not evidence of complete domain correctness. The original functions and their existing test suites remain the authority for broader supported contracts.

## Learner tasks and assessment rubric

1. Before running the lab, predict every expected answer and derive one numeric result or state transition by hand.
2. Explain the worked reasoning above using the referenced source, including the rejected or counterexample case.
3. Add a new valid example and a nearby failing example. Explain which assumption changes, then compare against the existing implementation. For concept/static labs, keep the result explicitly at that level.
4. Complete the scorecard for a proposed extension and a simpler baseline. Leave measurements unknown until collected; a task that the baseline already solves is not evidence for additional topology.

| Competency | Points | Full-credit evidence |
| --- | --- | --- |
| Model and contract | 0–3 | Correct objects, relation direction, labels/units, input bounds and missingness. |
| Derivation and trace | 0–3 | Hand derivation agrees with the specified fixture; source steps explain why. |
| Counterexample | 0–3 | New failing/boundary case has a justified expected result; rejection is not suppressed. |
| Scope and necessity | 0–3 | Distinguishes software behavior from validation and compares an explicit simpler alternative. |

Completion requires at least 10/12 and no zero in scope/necessity. A runnable answer key alone is not evidence that a learner achieved this competency. No learner-outcome study has been performed.

## Verification evidence and maintenance

[VALIDATION.json](../../curriculum/VALIDATION.json) records the inspected base revision, local Python version, source/fixture hashes, lab/answer hashes, case count and exit codes. All cases were executed locally. An in-memory copy with a deliberately wrong comparison was also executed and returned nonzero, checking that the grading failure path is active. Those injected failures are harness checks, not scientific adversarial evaluations.

The dedicated [curriculum workflow](../../.github/workflows/curriculum.yml) runs the same `--verify` command on relevant pull-request changes. CI status is reported by GitHub; the local record does not assert that remote CI passed. Existing full-suite and installed-package requirements still apply to runtime changes. When source or fixture semantics change, inspect the diff and rederive answers before updating expected.json. Never regenerate expected answers solely to silence a failure. Refresh the local validation record after an actual run; do not rewrite its recorded base revision as if a new run occurred.

## Interoperability and adoption gate

Retain explicit domain contracts. Shared assurance records should refer to domain evidence and its assumptions rather than relabeling graph reachability, homology, statistical calibration and epistemic acceptance as interchangeable quantities. The canonical ResearchOs controller remains owned by ResearchOs; this curriculum does not create another controller fork.

Adopt additional mathematics only after a versioned experiment demonstrates a useful operation, the scorecard has evidence, the simpler baseline is inadequate and existing conformance checks remain satisfied. A route or polygon result does not establish map completeness, geographic safety or source authenticity.
