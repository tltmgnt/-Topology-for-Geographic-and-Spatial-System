# Geographic and Spatial Topology

<!-- research-workbench:start -->
## Research workbench

[Open this repository's private workbench](https://tltmgnt-topology-for-geographic-and-spatial-system.troturn31.chatgpt.site) · [All repository workbenches](https://tltmgnt-research-workbenches.troturn31.chatgpt.site)

The hosted interface requires ChatGPT sign-in and access to the private Site. It supports browser-local research records, evidence fingerprints and workspace export. It is a prototype: no live AI model or repository backend is connected, and it does not establish external validation.
<!-- research-workbench:end -->


## Topology Engine 2.0 upgrade

The project now includes opt-in directed and weighted routing, polygon relationships,
multiple simultaneous outage scenarios, scoped resilience scores, optional PostGIS
snapshots, dependency-free GeoPackage interchange, interactive offline geographic
reviews, and independent route checks. The existing v1 workflow remains available.
See [the v2 guide and exact contracts](docs/ENGINE2.md) for installation, examples,
semantics, limitations and benchmarks. Select v2 with requirements `schema_version: 2`.

The workflow documented below describes the preserved **v1** mode.

A dependency-free Python tool for **offline regional network gap analysis**.
Import an explicitly connected GeoJSON network, declare required locations and
routes, evaluate connectivity and single-edge failure exposure, and create a
self-contained review bundle that can be independently recomputed by this software.

The repository includes a working package, CLI, synthetic examples, unit and
end-to-end tests, installation checks, and CI. No paid API, live map service,
account credentials, or cloud infrastructure is required.

## Install and run

Requires Python 3.10 or later.

```sh
python -m pip install .
mkdir -p runs
spatial-topology analyze examples/network.geojson --requirements examples/requirements.json --output runs/reference
spatial-topology verify runs/reference
```

Create `runs/` first, or choose an existing parent directory. The output directory
itself must not exist. Open `runs/reference/review.html` in a browser for an offline
network diagram, requirement results and the full analysis. The diagram is a
longitude/latitude schematic with independently scaled axes, not a navigation map.

Without installing, run the same commands as `python -m spatial_topology` from the
repository root. Run `python -m unittest discover -s tests -v` for the test suite.

## Complete a gap and outage study

```sh
mkdir -p runs
spatial-topology analyze examples/network.geojson --requirements examples/gaps.json --output runs/gaps
# Expected exit 1: the bundle is created and contains four declared requirement gaps.
spatial-topology verify runs/gaps
# Expected exit 0: the bundle is internally consistent; its analysis still says GAPS_FOUND.
spatial-topology analyze examples/network.geojson --requirements examples/outage.json --output runs/outage
# Expected exit 1: disabling a node and edge exposes access and redundancy gaps.
spatial-topology verify runs/outage
spatial-topology compare runs/reference runs/outage
```

The synthetic network has triangle A–B–C, a spur C–D, and an isolated E. Expected
baseline results are components `[A,B,C,D]` and `[E]`, bridge `CD`, and articulation
node `C`. A–C tolerates any single active edge loss; A–D does not. The baseline
requirements permit the latter and do not require access to E. Consequently,
`REQUIREMENTS_SATISFIED` does not mean the entire graph is connected.

The gap example additionally requires a missing location, a resilient path to D,
and a route from isolated E. The outage example disables D and BC, without editing
the original input. Requirements and observations remain separate.

Successful CI runs also publish a seven-day `synthetic-spatial-review` artifact.
Download and extract it, open `review.html`, then run `spatial-topology verify` on
the extracted directory. Only the fictional example is uploaded.

## What is implemented

- Strict, bounded GeoJSON Point/LineString network validation.
- Explicit endpoint identity and geometry consistency checks.
- Undirected multigraphs, including distinct parallel links.
- Components, isolated nodes, bridges and articulation nodes.
- Deterministic shortest paths using approximate spherical segment lengths.
- Explicit required-node coverage and per-path gap codes.
- Node/edge outage scenarios and single-edge connectivity redundancy checks.
- Verified baseline/scenario comparison with changed-criteria disclosure.
- Deterministic JSON reports, self-contained HTML/SVG review, source fingerprints.
- Exclusive output creation and full bundle reconstruction verification.
- Clear success, gap and malformed-input CLI exit codes.

## Input contracts

This tool accepts a documented **subset** of GeoJSON, not every valid GeoJSON file.
Positions use WGS84 longitude then latitude, in decimal degrees, following
[RFC 7946](https://www.rfc-editor.org/rfc/rfc7946.html). Only two-dimensional Points
and LineStrings are supported. Projected coordinates, polygons, automatic snapping,
intersection inference and antimeridian-spanning networks are not supported.

Node feature:

```json
{"type":"Feature","id":"A","properties":{"kind":"node","label":"Site A"},
 "geometry":{"type":"Point","coordinates":[-122,37]}}
```

Edge feature:

```json
{"type":"Feature","id":"AB","properties":{"kind":"edge","source":"A","target":"B"},
 "geometry":{"type":"LineString","coordinates":[[-122,37],[-121.99,37]]}}
```

Wrap features in `{"type":"FeatureCollection","features":[...]}`. Point features
must define every referenced endpoint. Feature IDs are unique across nodes and
edges. Edge first/last positions must match their declared endpoints exactly.
Line crossings and equal coordinates do not create implicit junctions. All edges
are undirected; the tool does not model one-way roads, turn restrictions or traffic.

Requirements file:

```json
{
  "schema_version": 1,
  "required_nodes": ["A", "B"],
  "required_paths": [
    {"id":"access","source":"A","target":"B","max_distance_m":2000,
     "require_redundancy":true}
  ],
  "disabled_nodes": [],
  "disabled_edges": []
}
```

At least one required node or path must be declared. Missing required IDs are valid
analysis inputs and become visible gaps. Unknown disabled IDs are invalid scenario
configuration. Unknown fields are rejected rather than silently discarded. See
[full contracts and semantics](docs/CONTRACTS.md).

## Bundle and exit codes

A new output directory contains exactly:

| File | Purpose |
|---|---|
| `input.geojson` | Captured canonical input network |
| `requirements.json` | Captured canonical requirements and outages |
| `report.json` | Complete deterministic analysis and scope limits |
| `review.html` | Offline schematic and readable report |
| `manifest.json` | Sizes and SHA256 values of the other files |

| Command | Exit 0 | Exit 1 | Exit 2 |
|---|---|---|---|
| `analyze` | Declared requirements satisfied | Gaps found; bundle still created | Invalid input, limits or I/O failure |
| `verify` | Every file matches recomputation | Not used | Invalid, edited, incomplete or incompatible bundle |
| `compare` | Both bundles verified and comparison completed | Not used | Invalid bundle or different captured network |

`compare` verifies both bundles, requires the same captured network, and reports new
and resolved gaps plus component and bridge changes. It flags changes to acceptance
criteria separately from outages. Comparison is descriptive, not causal evidence.

Verification recomputes analysis and HTML from captured inputs and compares all
five files. Editing the report and updating its manifest cannot hide a mismatch.
However, replacing inputs and regenerating the entire bundle creates a different,
internally consistent study. Hashes are not signatures or proof of source truth.

## Boundaries and remaining work

This is a complete offline workflow within the contracts above, not a full GIS
platform, autonomous infrastructure controller or operational safety assessment.
Distances are approximate vertex-to-vertex great-circle segment sums on a sphere
of radius 6,371,008.8 meters. They are not ellipsoidal survey distances, GeoJSON
Cartesian-segment integrals, travel times, accessibility predictions or terrain costs.
Densify/prepare geometry externally when that distinction matters.

Single-edge redundancy checks connectivity only. It does not guarantee a second
route within the distance limit, node resilience, capacity, reliability probabilities
or resilience to correlated failures. Geometry and topology are supplied claims;
there is no independent source retrieval, freshness validation or live observation.

Reports include input geometry and labels. Keep sensitive real-world network data
private. The supplied examples are fictional. No action is executed and
`execution_authorized` is always false.

The v2 mode adds directed networks, caller-supplied costs, polygon predicates and
snapshot adapters. Calibrated travel models, authenticated provenance and a
TruthAi evidence-contract adapter remain future work. None is required for v1.

## License

Apache License 2.0. The repository's original LICENSE is retained.

## ResearchOS / TECT concept integration

The [ResearchOS / Topological Epistemic Control Theory technical concept paper](docs/researchos/TECT_WHITE_PAPER.md) proposes an epistemic control and assurance infrastructure for AI-generated knowledge. Read the [repository integration status](docs/researchos/INTEGRATION.md) and [machine-readable scope](docs/researchos/integration.json) for the boundary between the concept and implemented capabilities. Performance targets are research objectives, not achieved results. This documentation addition does not implement the complete ResearchOS architecture or change operational authority.

## ResearchOS / TECT assurance layer

This repository includes the shared v0.1 research controller, a scoped executable domain pilot, replayable evidence/decision bundles, adversarial regression probes, and explicit unassured outcomes. See [the workflow](docs/RESEARCHOS.md), [versioned semantics](docs/TECT_SPEC.md), and [research-program traceability](docs/TECT_RESEARCH_PLAN.md). Existing domain results retain their documented limits. No claim state authorizes external or clinical execution.

## Portfolio implementation boundary

See [current implementation and shared-core integration](docs/portfolio/INTEGRATION.md) and [machine-readable status](docs/portfolio/STATUS.json). Independent empirical reproduction and real-provider acceptance remain separate from software checks.

**∞**

## Topology compatibility and curriculum

See the [repository-specific v2 curriculum](docs/portfolio/TOPOLOGY_CURRICULUM_V2.md) for topology choices, worked explanations, a graded laboratory and adoption boundaries. Run the offline answer key from this repository root:\n\n```sh\npython curriculum/lab.py --verify\n```\n\n[Expected answers](curriculum/expected.json) · [Recorded local validation](curriculum/VALIDATION.json). The guide states any existing dependency needed for the lab.
