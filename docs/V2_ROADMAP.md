# ResearchPilot V2 roadmap

V2 extends the verified V1 paper-analysis workflow without replacing it. The stable V1 snapshot is preserved on the `release/v1.0.0` branch, while V2 development happens on `codex/v2`.

## V2 objective

Turn paper understanding into a cautious, traceable reproduction-planning workflow. V2 must clearly separate verified facts, model inferences, planned actions, and actually executed results.

## Phase 1: Reproduction readiness

- Extract code repository, dataset, supplementary-material, and project-page links from the paper.
- Identify required frameworks, libraries, model checkpoints, hardware, parameters, and evaluation metrics.
- Produce a readiness checklist with `available`, `missing`, `unclear`, and `not applicable` states.
- Cite every paper-derived requirement with its PDF page number.
- Let the user approve or reject external downloads before any action occurs.

### Acceptance criteria

- A user can upload one PDF and receive a structured reproduction-readiness report.
- Missing information is reported explicitly rather than invented.
- Every paper-derived claim links back to one or more PDF pages.
- No repository, dataset, or executable file is downloaded without approval.

## Phase 2: Experiment planning

- Generate a reproducible environment specification and ordered execution plan.
- Separate commands copied from official sources from commands inferred by the model.
- Estimate storage, memory, accelerator, runtime, and API requirements when evidence permits.
- Add approval checkpoints for costly, networked, or potentially unsafe steps.

### Acceptance criteria

- Plans include dependencies, inputs, outputs, metrics, and stop conditions.
- Unverified assumptions are visibly labeled.
- Users can edit the plan before execution.

## Phase 3: Sandboxed execution

- Run approved commands in an isolated workspace with time and resource limits.
- Disable network access by default and allow it only for approved steps.
- Capture commands, environment details, logs, outputs, and failures.
- Stop safely when limits are exceeded or unexpected behavior occurs.

### Acceptance criteria

- Every executed step has an auditable record.
- Failed experiments remain reproducible and do not appear as successful results.
- The sandbox cannot access user secrets unless explicitly provided for that step.

## Phase 4: Validation and reporting

- Compare reproduced metrics with the paper's reported values.
- Explain deviations using evidence from configuration, data, logs, and the paper.
- Export a report containing citations, approvals, environment details, commands, results, and limitations.

### Acceptance criteria

- Reported metrics are sourced from actual run artifacts.
- Paper values and reproduced values are clearly distinguished.
- The final report states what was not reproduced and why.

## Initial V2 implementation scope

The first V2 milestone covers Phase 1 only: resource extraction, readiness assessment, evidence citations, and approval preparation. It does not execute paper code or claim successful reproduction.

## Version policy

- `main`: current stable public version.
- `release/v1.0.0`: preserved V1 snapshot.
- `codex/v2`: active V2 development.
- V2 reaches `main` only after tests and a real-paper acceptance run pass.
