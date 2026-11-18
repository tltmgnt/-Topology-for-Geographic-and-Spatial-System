# MathOS × — guarded self-improving discovery (v1)

**Status:** implemented offline research scheduler and finite-test harness. This is **not** an autonomous mathematician, an AI model, a proof assistant, an independent literature audit, or evidence that any new theorem has been discovered.

## What is implemented

The engine has seven candidate frontiers: intervention-preserving abstraction, emergence, theory-space geometry, proof geometry, information-time, changing rules, and global explanation obstructions. Each is explored in four directions (invent, conjecture, unify, foundations) at both research-grade and radical depths. The resulting 7 × 4 × 2 = **56 catalogued research prompts** include explicit bounded falsification suggestions and an existing-mathematics neighborhood to investigate before claiming novelty.

The offline evaluator includes **two rigorous, finite checks**:

1. **Interventional abstraction:** computes exact rational total-variation defects for user-supplied finite transition kernels and coarse-graining maps. It reports witnesses and the proven interval D/2 ≤ optimal uniform macro-model error ≤ D. It also enumerates all canonical nontrivial quotients for systems with 3–7 states, ranking them by their measured defect. This does not discover or certify new causal laws.
2. **Explanation obstruction:** uses GF(2) elimination to identify a deletion-minimal inconsistent subsystem of binary parity constraints. The three-equation odd triangle is a regression case. This does not establish a general sheaf obstruction or solve an open problem.

### Run it

From the repository root with Python 3.10+ (no internet, keys, or third-party packages needed):

    python -m mathosx.discovery --limit 8
    python -m mathosx.discovery --direction conjecture --depth radical --limit 7
    python -m mathosx.discovery --output-dir artifacts/discovery
    python -m unittest discover -s tests -p 'test_discovery.py' -v

The output JSON includes the full directions/depths, top-ranked questions, finite benchmark evidence, catalog SHA-256, feedback sample count, and explicit NOT_CERTIFIED and novelty-not-assessed markers.

## Precisely what "self-improving" means here

The **prioritization policy**, not the program's own code or mathematical truth claims, changes when reviewers supply useful/not_useful evidence labels. Initially all questions have the same prior. For each question with u useful labels out of n labeled outcomes, the fixed heuristic priority is:

    priority = (u + 1)/(n + 2) + 0.15/(n + 1)

The first term is a Beta(1,1)-smoothed usefulness frequency; the second is a simple exploration bonus. These scores are **heuristic scheduling scores**, not calibrated probabilities of mathematical truth, novelty, or breakthrough. A negative result is retained rather than discarded. Feedback outcomes are not generated or graded automatically. Requiring a reviewer field does not authenticate that person's identity.

To record a review locally:

    python -m mathosx.discovery \
      --feedback-file mathosx/feedback.v1.json \
      --rate-question causal-abstraction:invent:research \
      --outcome useful \
      --evidence-ref evidence/local-causal-example-001.json \
      --reviewer researcher-id

A successful command atomically updates that JSON ledger. Commit the resulting change through normal Git review if you want the learning to survive across machines and GitHub Actions runs. Never put confidential reviewer information or sensitive evidence in a public repository.

Question IDs and schema are validated; duplicate evidence for the same question is rejected. An unknown question, missing reviewer, unsupported label, or extra certification field fails closed. The ledger is a *suggestion signal*, not permission to promote claims.

## Continuous iteration and human gates

The companion GitHub Actions workflow runs on pull requests, manual dispatch, and a weekly schedule **after this PR is merged**. It executes offline tests and generates a JSON discovery report as an artifact. It uses read-only repository permissions, no API keys, no arbitrary model-proposed code, no automatic commits, no automatic merges, and no theorem-status mutations.

A review cycle should:

1. Choose a prioritized question and write its exact mathematical claim and assumptions.
2. Search for prior art independently; a generated prior-art neighborhood is not a literature review.
3. Attempt a proof, disproof, or finite counterexample and retain failures.
4. Record a human assessment with a reviewable evidence reference.
5. Re-run the scheduler and examine whether useful research questions rise in priority.
6. Independently verify any claimed theorem with appropriate mathematics/formalization, outside this feedback loop.

This is a deliberately **bounded first implementation** of self-improvement. Automatic LLM hypothesis invention, live novelty search, autonomous PR creation, code mutation, and perpetual AI model runs are **not** enabled. The existing MathOS Clay research and proof-assurance gates remain unchanged and authoritative.

## Known mathematical limits

- Exact zero abstraction defect is intervention-relative: adding interventions can reveal distinctions previously erased by coarse-graining. The optimal-error bounds need not be tight.
- The finite quotient search is exhaustive only over the specified finite states and canonical partitions (2 through n−1 blocks); a trivial one-block quotient is intentionally excluded.
- A deletion-minimal inconsistent parity core is not necessarily the smallest-cardinality core.
- Finite benchmark passes certify code behavior on those inputs, not a universal theorem.
- "Self-improvement" is restricted to transparent, labeled research-queue adaptation. Repeated labels from correlated evidence are not independent confirmations and should be adjudicated during review.

See also the existing MathOS research-scope and non-certification requirements in docs/research/AGENTIC_RESEARCH_PROCESS.md and README.md.
