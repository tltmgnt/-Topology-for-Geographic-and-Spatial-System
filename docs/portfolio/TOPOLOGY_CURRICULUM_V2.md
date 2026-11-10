# Topology compatibility and curriculum v2 — -Topology-for-Geographic-and-Spatial-System

Version 2 adapts the explicit-molecular-graph teaching pattern to this repository's actual role. This is documentation and a learning/decision framework; it introduces no mathematical engine, runtime dependency or operational permission.

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

## Source-linked reading laboratory

The table is a guided selection of source lines, not an assertion that the whole repository is covered. Line numbers refer to the inspected source blob `88052fc88da84bc52782a479df3621455418f18b` in [spatial_topology/analysis.py](../../spatial_topology/analysis.py). Recheck anchors after source changes.

| Line | Statement | Learning check |
| --- | --- | --- |
| [10](../../spatial_topology/analysis.py#L10) | `def canonical(value):` | State the input/output contract and trace one normal and one failing case. |
| [11](../../spatial_topology/analysis.py#L11) | `return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()` | Predict the returned value and distinguish a computed result from authorization. |
| [14](../../spatial_topology/analysis.py#L14) | `def fingerprint(value):` | State the input/output contract and trace one normal and one failing case. |
| [15](../../spatial_topology/analysis.py#L15) | `return hashlib.sha256(canonical(value)).hexdigest()` | Explain the exact bytes bound by the digest and why hashing does not authenticate the source. |
| [18](../../spatial_topology/analysis.py#L18) | `def adjacency(network, requirements):` | State the input/output contract and trace one normal and one failing case. |
| [25](../../spatial_topology/analysis.py#L25) | `return graph` | Predict the returned value and distinguish a computed result from authorization. |
| [28](../../spatial_topology/analysis.py#L28) | `def components(graph, skip_node=None, skip_edge=None):` | State the input/output contract and trace one normal and one failing case. |
| [43](../../spatial_topology/analysis.py#L43) | `return groups` | Predict the returned value and distinguish a computed result from authorization. |
| [46](../../spatial_topology/analysis.py#L46) | `def shortest_path(graph, source, target):` | State the input/output contract and trace one normal and one failing case. |
| [48](../../spatial_topology/analysis.py#L48) | `return None` | Predict the returned value and distinguish a computed result from authorization. |
| [62](../../spatial_topology/analysis.py#L62) | `return {'nodes': list(reversed(nodes)), 'edges': list(reversed(edges)),` | Draw the represented relation; identify direction, multiplicity and edge labels. |
| [70](../../spatial_topology/analysis.py#L70) | `return None` | Predict the returned value and distinguish a computed result from authorization. |
| [73](../../spatial_topology/analysis.py#L73) | `def build_report(geojson, requirements):` | State the input/output contract and trace one normal and one failing case. |
| [74](../../spatial_topology/analysis.py#L74) | `if type(requirements) is dict and requirements.get('schema_version') == 2:` | Separate type, shape and value checks; test a missing field and an invalid value. |
| [76](../../spatial_topology/analysis.py#L76) | `return build_report_v2(geojson, requirements)` | Predict the returned value and distinguish a computed result from authorization. |
| [116](../../spatial_topology/analysis.py#L116) | `return {'schema_version': 1, 'engine_version': ENGINE_VERSION,` | Separate type, shape and value checks; test a missing field and an invalid value. |
## Assessment and verification

A learner must explain the model, trace the capstone, identify a counterexample and state the scope boundary. Assess these four competencies equally; a numerical score cannot compensate for an unsupported scientific or operational claim.

Relevant existing checks:

- [tests/test_engine2.py](../../tests/test_engine2.py)
- [tests/test_postgis.py](../../tests/test_postgis.py)
- [tests/test_researchos.py](../../tests/test_researchos.py)

Follow [README](../../README.md) for environment and installed-package instructions. Read scripts before execution; source-reading exercises do not authorize provider calls, model downloads, live orders, hardware actions or messages. Synthetic fixtures establish software behavior only. This documentation change does not report those exercises as already executed.

## Interoperability and adoption gate

Retain explicit domain contracts. Shared assurance records should refer to domain evidence and its assumptions rather than relabeling graph reachability, homology, statistical calibration and epistemic acceptance as interchangeable quantities. The canonical ResearchOs controller remains owned by ResearchOs; this curriculum does not create another controller fork.

Adopt additional mathematics only after a versioned experiment demonstrates a useful operation, the scorecard has evidence, the simpler baseline is inadequate and existing conformance checks remain satisfied. A route or polygon result does not establish map completeness, geographic safety or source authenticity.
