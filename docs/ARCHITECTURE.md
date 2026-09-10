# Bob Reliability Engineer (BRE)
## Software Reliability Intelligence Layer for IBM Bob

> **Purpose:** Build a software-reliability platform around IBM Bob that can investigate failures, determine root cause, assess remediation risk, safely orchestrate fixes, verify those fixes, and learn from completed incidents.
>
> **Core principle:** IBM Bob remains the engineering agent. BRE provides the reliability intelligence, orchestration, evidence, safety, verification, and engineering memory around Bob.

---

# 1. Product Vision

## Problem

Modern software failures require developers to reconstruct context across:

- source code
- tests
- configuration
- dependencies
- Git history
- CI failures
- runtime/monitoring signals
- previous incidents
- architectural decisions

A coding agent can often find and implement a fix, but a reliable software-engineering workflow also needs to answer:

1. What failed?
2. What is the root cause?
3. What evidence supports the diagnosis?
4. What components are affected?
5. How risky is the proposed remediation?
6. Should a human approve it?
7. Did the remediation actually resolve the failure?
8. What should be remembered for future incidents?

## Vision

BRE turns IBM Bob from an engineering agent into the core execution engine of a complete reliability workflow:

```text
Detect
  ↓
Investigate
  ↓
Diagnose
  ↓
Assess Risk
  ↓
Approve
  ↓
Remediate
  ↓
Verify
  ↓
Learn
```

---

# 2. Core Value Proposition

> **Don't just generate a fix. Build evidence, assess risk, verify the fix, and learn from the incident.**

The product should optimize for **developer trust**, not merely code-generation speed.

---

# 3. High-Level Architecture

```text
                         ┌──────────────────────┐
                         │      DEVELOPER       │
                         │  Bug / CI / Incident │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       IBM BOB        │
                         │   Engineering Agent  │
                         │ Ask / Plan / Agent    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                 ┌────────────────────────────────────┐
                 │     BOB RELIABILITY ENGINE         │
                 └────────────────┬───────────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
   ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐
   │   INVESTIGATION │  │  CONTEXT ENGINE  │  │  ENGINEERING    │
   │     ENGINE      │  │     (ASMOS)      │  │     MEMORY      │
   │                 │  │                  │  │                 │
   │ • Evidence      │  │ • Task Analysis  │  │ • Incidents     │
   │ • Root Cause    │  │ • Context Router │  │ • Root Causes   │
   │ • Dependencies  │  │ • Context Ranker │  │ • Fixes         │
   │ • Git History   │  │ • Agent Routing  │  │ • Decisions     │
   └────────┬────────┘  └────────┬─────────┘  │ • Learnings     │
            │                    │            └────────┬────────┘
            └────────────────────┼─────────────────────┘
                                 │
                                 ▼
                       ┌──────────────────┐
                       │   ROOT CAUSE     │
                       │     ANALYSIS     │
                       │                  │
                       │ Cause + Evidence │
                       │ + Confidence     │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   RISK ENGINE    │
                       │                  │
                       │ LOW / MED / HIGH │
                       │     / CRITICAL   │
                       └────────┬─────────┘
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
                  ▼                           ▼
          ┌────────────────┐         ┌──────────────────┐
          │ AUTO APPROVAL  │         │ HUMAN APPROVAL   │
          │  LOW / MEDIUM  │         │ HIGH / CRITICAL  │
          └───────┬────────┘         └────────┬─────────┘
                  │                           │
                  └─────────────┬─────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   REMEDIATION    │
                       │     VIA BOB      │
                       │                  │
                       │ • Implement Fix  │
                       │ • Generate Patch │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   VERIFICATION   │
                       │                  │
                       │ • Unit Tests     │
                       │ • Integration    │
                       │ • Regression     │
                       └────────┬─────────┘
                                │
                     ┌──────────┴──────────┐
                     │                     │
                     ▼                     ▼
              ┌──────────────┐      ┌────────────────┐
              │   SUCCESS    │      │    FAILURE     │
              │              │      │                │
              │ Close        │      │ Re-investigate │
              └──────┬───────┘      └───────┬────────┘
                     │                      │
                     └──────────┬───────────┘
                                ▼
                       ┌──────────────────┐
                       │   LEARN / STORE  │
                       │                  │
                       │ Engineering      │
                       │ Memory Update    │
                       └────────┬─────────┘
                                │
                                └───────────────► ASMOS
```

---

# 4. Architectural Principles

## 4.1 Bob is not replaced

BRE should not recreate Bob's coding-agent functionality.

Bob handles:

- code understanding
- planning
- code editing
- execution
- testing
- agentic software-engineering tasks

BRE handles:

- reliability orchestration
- incident lifecycle
- evidence management
- context selection
- risk classification
- approval policy
- verification policy
- engineering memory
- learning

## 4.2 Evidence before remediation

The system must establish evidence before recommending or implementing a fix.

```text
Incident
  ↓
Evidence
  ↓
Hypothesis
  ↓
Root Cause
  ↓
Risk
  ↓
Remediation
```

## 4.3 Verification is mandatory

A remediation is not considered successful because code was changed.

Success requires verification evidence.

## 4.4 Human control for risky operations

High-risk and critical operations must have an explicit approval boundary.

## 4.5 Minimal context, maximum relevance

ASMOS should route the smallest useful set of engineering context to the agent rather than indiscriminately providing the whole repository.

## 4.6 Learn only from verified outcomes

Engineering memory should prioritize:

- confirmed root causes
- successful remediations
- verified failures
- developer-approved decisions
- validated architectural constraints

---

# 5. Core Workflow / State Machine

```text
                    ┌───────────┐
                    │  DETECTED │
                    └─────┬─────┘
                          ▼
                    ┌───────────┐
                    │INVESTIGATE│
                    └─────┬─────┘
                          ▼
                    ┌───────────┐
                    │ DIAGNOSED │
                    └─────┬─────┘
                          ▼
                    ┌───────────┐
                    │ RISK CHECK│
                    └─────┬─────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
         AUTO APPROVE            HUMAN APPROVAL
              │                       │
              └───────────┬───────────┘
                          ▼
                    ┌───────────┐
                    │ REMEDIATE │
                    └─────┬─────┘
                          ▼
                    ┌───────────┐
                    │  VERIFY   │
                    └─────┬─────┘
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
              SUCCESS            FAILURE
                 │                 │
                 ▼                 ▼
              LEARN          RE-INVESTIGATE
                 │                 │
                 └────────┬────────┘
                          ▼
                       CLOSED
```

## State definitions

| State | Purpose |
|---|---|
| `DETECTED` | Failure/incident has been received |
| `INVESTIGATING` | System is collecting evidence |
| `DIAGNOSED` | Root-cause hypothesis established |
| `RISK_ASSESSED` | Remediation risk determined |
| `AWAITING_APPROVAL` | Human decision required |
| `REMEDIATING` | Bob is implementing the fix |
| `VERIFYING` | Tests and validation are running |
| `RESOLVED` | Fix verified successfully |
| `REINVESTIGATING` | Verification failed and investigation resumes |
| `CLOSED` | Incident lifecycle complete |

---

# 6. Component Architecture

## 6.1 Incident Intake

### Responsibilities

Accept incidents from:

- CI
- test runners
- monitoring
- developer reports
- GitHub
- future observability systems

### MVP

Support:

```text
Test/CI failure
```

### Example

```json
{
  "type": "test_failure",
  "repository": "dataforge",
  "branch": "main",
  "error": "DatabaseConnector test failed",
  "metadata": {}
}
```

---

# 7. Investigation Engine

The investigation engine builds an evidence package before remediation.

```text
Incident
   │
   ▼
Task Analyzer
   │
   ▼
Context Router
   │
   ├── Repository
   ├── Tests
   ├── Git History
   ├── Configuration
   ├── Dependencies
   └── Engineering Memory
             │
             ▼
        Evidence Set
```

## Responsibilities

- classify incident
- identify likely components
- collect relevant repository evidence
- inspect tests
- inspect configuration
- inspect Git history
- retrieve historical incidents
- construct investigation timeline
- produce root-cause candidates

## Investigation output

```json
{
  "incident_id": "inc_123",
  "likely_components": [
    "DatabaseConnector",
    "PostgresConfiguration"
  ],
  "relevant_files": [
    "database_connector.py",
    "test_database.py",
    "config.py"
  ],
  "recent_changes": [],
  "historical_incidents": [],
  "evidence": []
}
```

---

# 8. ASMOS Context Engine

ASMOS is the intelligence layer responsible for selecting useful engineering context.

```text
Incident
   ↓
Task Understanding
   ↓
ASMOS Router
   ↓
Context Ranking
   ↓
Relevant Context
   ↓
IBM Bob
```

## Context sources

```text
┌─────────────────────────┐
│ Engineering Memory      │
├─────────────────────────┤
│ Source Code             │
│ Tests                   │
│ Git History             │
│ Configuration           │
│ Dependencies            │
│ Documentation           │
│ Previous Incidents      │
│ Architecture Decisions  │
└─────────────────────────┘
```

## Example ranking

```text
Incident:
"Authentication requests timing out"

Context ranking:

1. auth/service.py          0.96
2. auth/client.py           0.94
3. test_auth_timeout.py     0.91
4. config/auth.yaml         0.87
5. git commit 8f32a         0.83
6. README.md                0.31
```

## Initial interfaces

```python
class ContextRouter:
    def route(
        self,
        incident,
        repository_context,
        memory_context
    ) -> list:
        ...
```

```python
class ContextRanker:
    def rank(
        self,
        task,
        candidates
    ) -> list:
        ...
```

```python
class TaskAnalyzer:
    def analyze(self, incident) -> dict:
        ...
```

---

# 9. Engineering Memory

Engineering memory stores validated software knowledge.

## Memory categories

```text
Incident
Root Cause
Remediation
Verification
Architecture Decision
Engineering Constraint
Developer Correction
Known Failure Pattern
```

## Memory lifecycle

```text
Incident
   │
   ├── Root Cause
   ├── Evidence
   ├── Fix
   ├── Tests
   ├── Verification
   └── Developer Feedback
            │
            ▼
      Memory Consolidation
            │
            ▼
      Engineering Memory
```

## Memory quality rules

Do not automatically promote uncertain hypotheses into permanent knowledge.

Preferred lifecycle:

```text
Candidate Knowledge
       ↓
Verified Outcome
       ↓
Confidence Score
       ↓
Memory
```

---

# 10. Root Cause Analysis

Bob performs the engineering reasoning using the evidence assembled by BRE.

```text
Evidence
   │
   ▼
IBM Bob
   │
   ├── inspect
   ├── reason
   ├── trace
   ├── compare
   └── test hypothesis
          │
          ▼
      Root Cause
```

## Output

```json
{
  "root_cause": "Connection pool exhaustion caused by ...",
  "confidence": 0.91,
  "affected_components": [
    "AuthService",
    "SessionManager"
  ],
  "evidence": [
    "commit abc123",
    "failing test xyz",
    "configuration change"
  ]
}
```

Root cause analysis must contain:

- root cause
- evidence
- affected components
- confidence
- assumptions
- unresolved uncertainty

---

# 11. Risk Engine

The risk engine determines whether remediation can proceed automatically.

```text
Root Cause
     │
     ▼
Risk Assessment
```

## Risk levels

```text
LOW
MEDIUM
HIGH
CRITICAL
```

## Risk factors

Initial factors:

- number of affected components
- production-facing API impact
- database/schema impact
- authentication/security impact
- infrastructure impact
- deployment impact
- test coverage
- confidence in diagnosis
- size of change
- blast radius
- historical failure severity

## Example

```text
┌───────────────────────────────┐
│       REMEDIATION RISK        │
├───────────────────────────────┤
│ Risk: HIGH                    │
│ Confidence: 92%               │
├───────────────────────────────┤
│ Affected components: 4        │
│ API surface affected: YES     │
│ Database migration: YES       │
│ Tests available: PARTIAL      │
└───────────────────────────────┘
```

---

# 12. Approval Engine

Approval policy:

```text
LOW
 ↓
Automatic remediation

MEDIUM
 ↓
Additional verification / policy dependent

HIGH
 ↓
Human approval

CRITICAL
 ↓
Mandatory human approval
```

## Approval record

```json
{
  "incident_id": "inc_123",
  "risk_level": "HIGH",
  "decision": "APPROVED",
  "approved_by": "developer",
  "timestamp": "...",
  "reason": "..."
}
```

Approval must be auditable.

---

# 13. Remediation Engine

After authorization, IBM Bob performs the actual engineering work.

```text
Risk Accepted
      │
      ▼
   IBM Bob
      │
      ▼
Implement Fix
      │
      ▼
Generate Patch
```

## Remediation constraints

Bob should:

- modify only necessary files
- preserve architectural constraints
- avoid unrelated refactoring
- avoid disabling tests
- avoid bypassing safety checks
- avoid unnecessary configuration changes
- explain the proposed changes

## Remediation output

```json
{
  "incident_id": "inc_123",
  "changed_files": [
    "database_connector.py"
  ],
  "patch_summary": "...",
  "tests_added": [
    "test_connection_pool.py"
  ]
}
```

---

# 14. Verification Engine

Verification is mandatory.

```text
Patch
 │
 ▼
Unit Tests
 │
 ▼
Integration Tests
 │
 ▼
Regression Tests
 │
 ▼
Verification
 │
 ├───────────────┐
 ▼               ▼
PASS             FAIL
 │                │
 ▼                ▼
Success       Re-investigate
```

## Verification levels

### Level 1 — Targeted

Tests directly related to the incident.

### Level 2 — Component

Tests for the affected subsystem.

### Level 3 — Regression

Tests covering potentially impacted functionality.

### Level 4 — Full suite

Optional depending on repository size and risk.

## Verification result

```json
{
  "status": "PASSED",
  "tests_run": 143,
  "tests_passed": 143,
  "tests_failed": 0,
  "regressions": [],
  "evidence": []
}
```

---

# 15. Failure Feedback Loop

Verification failure must not simply terminate the workflow.

```text
Verification Failed
        │
        ▼
New Evidence
        │
        ▼
Re-investigation
        │
        ▼
Updated Diagnosis
        │
        ▼
Risk Reassessment
        │
        ▼
Remediation
        │
        ▼
Verification
```

This creates the autonomous reliability loop.

---

# 16. Bob Integration Boundary

IBM Bob should be treated as an external engineering execution capability.

Conceptually:

```text
BRE
 │
 ├── Task
 ├── Relevant Context
 ├── Constraints
 ├── Expected Output
 └── Verification Requirements
          │
          ▼
      IBM Bob
          │
          ▼
 ┌─────────────────────┐
 │ Engineering Result  │
 │                     │
 │ • Analysis          │
 │ • Code Changes      │
 │ • Tests             │
 │ • Explanation       │
 └─────────────────────┘
```

Create a clean adapter:

```python
class BobAdapter:

    def investigate(self, task, context):
        ...

    def remediate(self, task, context):
        ...

    def verify(self, task, context):
        ...
```

The exact Bob integration mechanism should be determined from the current IBM Bob capabilities and hackathon environment rather than hardcoded into the architecture prematurely.

---

# 17. Connector Architecture

Use a connector abstraction so the reliability engine is not tied to one data source.

```text
                 Connector Registry
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
   Repository          CI            Monitoring
   Connector         Connector       Connector
        │               │                │
        ▼               ▼                ▼
      GitHub          GitHub          Future
                                      Sources
```

Initial connectors:

```text
RepositoryConnector
GitConnector
TestConnector
CIConnector
```

Future:

```text
MonitoringConnector
DatabaseConnector
IssueTrackerConnector
DeploymentConnector
CloudConnector
```

---

# 18. API Architecture

Use a service-oriented API boundary.

```text
/api
 ├── /incidents
 ├── /investigations
 ├── /diagnoses
 ├── /risk
 ├── /approvals
 ├── /remediations
 ├── /verifications
 └── /memory
```

## Example endpoints

```text
POST   /api/incidents
GET    /api/incidents/{id}

POST   /api/incidents/{id}/investigate
GET    /api/investigations/{id}

POST   /api/investigations/{id}/diagnose

POST   /api/remediations/{id}/approve
POST   /api/remediations/{id}/reject

POST   /api/remediations/{id}/execute

POST   /api/verifications/{id}/run
GET    /api/verifications/{id}

GET    /api/memory/search
```

---

# 19. Data Model

Initial relational model:

```text
Incident
   │
   ├── Investigation
   │       │
   │       └── Evidence[]
   │
   ├── Diagnosis
   │
   ├── RiskAssessment
   │
   ├── Approval
   │
   ├── Remediation
   │       │
   │       └── ChangedFiles[]
   │
   └── Verification
           │
           └── TestResults[]
```

Engineering memory is logically connected to completed incidents:

```text
Incident
   ↓
Verified Outcome
   ↓
Memory Record
```

---

# 20. Suggested Database Schema

## incidents

```text
id
repository
branch
type
severity
status
description
created_at
updated_at
```

## investigations

```text
id
incident_id
status
summary
started_at
completed_at
```

## evidence

```text
id
investigation_id
source_type
source_reference
content
relevance_score
confidence
created_at
```

## diagnoses

```text
id
incident_id
root_cause
confidence
affected_components
assumptions
created_at
```

## risk_assessments

```text
id
incident_id
risk_level
confidence
factors
blast_radius
created_at
```

## approvals

```text
id
incident_id
risk_level
decision
approved_by
reason
created_at
```

## remediations

```text
id
incident_id
status
summary
patch_reference
created_at
completed_at
```

## verification_runs

```text
id
incident_id
status
tests_run
tests_passed
tests_failed
regressions
created_at
completed_at
```

## engineering_memory

```text
id
type
title
content
source_incident_id
confidence
embedding_reference
created_at
updated_at
```

---

# 21. Repository Structure

Recommended initial structure:

```text
bob-reliability-engineer/
│
├── apps/
│   └── api/
│       ├── routes/
│       │   ├── incidents.py
│       │   ├── investigations.py
│       │   ├── remediations.py
│       │   └── approvals.py
│       │
│       ├── services/
│       │   ├── incident_service.py
│       │   ├── investigation_service.py
│       │   ├── remediation_service.py
│       │   └── verification_service.py
│       │
│       └── main.py
│
├── reliability/
│   ├── investigator/
│   │   ├── analyzer.py
│   │   ├── evidence.py
│   │   └── investigator.py
│   │
│   ├── diagnosis/
│   │   ├── root_cause.py
│   │   └── confidence.py
│   │
│   ├── risk/
│   │   ├── classifier.py
│   │   └── policies.py
│   │
│   ├── remediation/
│   │   └── orchestrator.py
│   │
│   ├── verification/
│   │   ├── test_runner.py
│   │   └── verifier.py
│   │
│   └── orchestration/
│       └── workflow.py
│
├── asmos/
│   ├── memory/
│   │   ├── store.py
│   │   ├── retriever.py
│   │   └── models.py
│   │
│   ├── routing/
│   │   ├── router.py
│   │   ├── ranking.py
│   │   └── task_analyzer.py
│   │
│   └── consolidation/
│       └── learner.py
│
├── bob/
│   ├── adapter.py
│   ├── prompts.py
│   └── execution.py
│
├── connectors/
│   ├── repository.py
│   ├── git.py
│   ├── ci.py
│   └── tests.py
│
├── models/
│   ├── incident.py
│   ├── investigation.py
│   ├── diagnosis.py
│   ├── risk.py
│   ├── remediation.py
│   └── verification.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/
│
└── README.md
```

---

# 22. Event-Driven Internal Architecture

Use domain events to decouple workflow stages.

```text
IncidentDetected
       │
       ▼
InvestigationRequested
       │
       ▼
InvestigationCompleted
       │
       ▼
DiagnosisCompleted
       │
       ▼
RiskAssessmentCompleted
       │
       ├───────────────┐
       ▼               ▼
AutoApproved      ApprovalRequested
       │               │
       └───────┬───────┘
               ▼
       RemediationStarted
               │
               ▼
       RemediationCompleted
               │
               ▼
       VerificationStarted
               │
          ┌────┴─────┐
          ▼          ▼
     Verification  Verification
       Passed        Failed
          │            │
          ▼            ▼
        Closed    Reinvestigation
```

Potential implementation:

```python
class DomainEvent:
    event_type: str
    incident_id: str
    payload: dict
    timestamp: datetime
```

---

# 23. Observability

Every workflow step should produce structured logs.

Track:

```text
incident_id
workflow_id
component
agent_action
context_sources
tool_calls
duration
status
error
confidence
```

This will later support both debugging and hackathon metrics.

---

# 24. Security and Safety

The system should treat remediation as a privileged operation.

## Required controls

- explicit approval for high-risk changes
- audit trail
- repository/branch restrictions
- command execution restrictions
- patch visibility
- test verification
- rollback capability
- no destructive action without policy authorization

## Principle

```text
Analyze freely
     ↓
Propose carefully
     ↓
Approve explicitly
     ↓
Execute safely
     ↓
Verify independently
```

---

# 25. Rollback Architecture

Every remediation should be reversible.

```text
Before Remediation
       │
       ▼
Create Checkpoint
       │
       ▼
Apply Patch
       │
       ▼
Verify
       │
   ┌───┴───┐
   ▼       ▼
 PASS     FAIL
   │       │
   ▼       ▼
 Commit   Rollback
```

For the MVP, Git-based rollback is sufficient.

---

# 26. MVP Scope

The first version should intentionally be small.

## MVP workflow

```text
CI / Test Failure
       ↓
Incident Intake
       ↓
Investigation
       ↓
ASMOS Context Routing
       ↓
IBM Bob Root Cause Analysis
       ↓
Risk Assessment
       ↓
Human Approval
       ↓
IBM Bob Remediation
       ↓
Automated Tests
       ↓
Verification
       ↓
Engineering Memory
```

## MVP supports

- one repository
- one incident type: test/CI failure
- Git history
- repository inspection
- targeted tests
- one Bob integration path
- four risk levels
- human approval
- remediation
- verification
- basic engineering memory

---

# 27. Phase 2

After the MVP works:

```text
CI
Monitoring
GitHub Issues
Production Errors
      │
      ▼
Incident Normalization
      │
      ▼
Reliability Engine
```

Add:

- GitHub Issues
- monitoring alerts
- runtime errors
- dependency failures
- performance regressions
- richer historical memory
- semantic embeddings
- specialized agents
- advanced context routing
- richer observability
- rollback automation
- dashboard

---

# 28. Phase 3

Long-term autonomous reliability platform:

```text
             Software System
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
       CI       Monitoring    Runtime
        │           │           │
        └───────────┼───────────┘
                    ▼
             Incident Engine
                    │
                    ▼
             Reliability Agent
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
   Investigation  Diagnosis   Prediction
        │           │            │
        └───────────┼────────────┘
                    ▼
               Remediation
                    │
                    ▼
               Verification
                    │
                    ▼
                Learning
```

---

# 29. Hackathon Demo Architecture

The demo should use a controlled failure.

```text
                Developer
                    │
                    ▼
              "CI is failing"
                    │
                    ▼
             ┌────────────┐
             │ IBM Bob    │
             └─────┬──────┘
                   │
                   ▼
          ┌─────────────────┐
          │ BRE Investigation│
          └────────┬────────┘
                   │
                   ▼
             Root Cause
                   │
                   ▼
              Risk: HIGH
                   │
                   ▼
           Human Approval
                   │
                   ▼
             Bob Remediates
                   │
                   ▼
              Run Tests
                   │
              ┌────┴────┐
              ▼         ▼
            PASS       FAIL
              │         │
              ▼         ▼
           RESOLVED  RESEARCH LOOP
              │
              ▼
         Memory Updated
```

## Demo screen should expose

### Incident

```text
❌ CI Failure
```

### Investigation

```text
✓ Source analysis
✓ Tests
✓ Git history
✓ Configuration
✓ Historical knowledge
```

### Diagnosis

```text
Root cause:
...

Confidence:
94%

Evidence:
...
```

### Risk

```text
Risk: HIGH

Human approval required.
```

### Remediation

```text
IBM Bob:
Implementing fix...
```

### Verification

```text
143 tests
143 passed

✓ Incident resolved
```

### Learning

```text
Engineering memory updated
```

---

# 30. Success Metrics

We need measurable impact.

## Reliability metrics

```text
Incident Resolution Rate
Root Cause Accuracy
Verification Success Rate
Regression Rate
Rollback Rate
```

## Engineering efficiency

```text
Time To Diagnose
Time To Remediate
Time To Verify
Total Developer Intervention Time
```

## Context intelligence

```text
Relevant Context Ratio
Context Rediscovery Rate
Unnecessary Files Inspected
Historical Context Retrieval Accuracy
```

## Safety

```text
High-Risk Changes Correctly Escalated
Unauthorized Changes
Verification Failures
Rollback Success Rate
```

---

# 31. Baseline Comparison

The hackathon demo should compare:

```text
             BASELINE
             IBM Bob
                │
                ▼
             Incident
                │
                ▼
            Investigation
                │
                ▼
              Fix
                │
                ▼
             Testing


                VS


          BRE + IBM Bob
                │
                ▼
             Incident
                │
                ▼
        Context Routing
                │
                ▼
           Investigation
                │
                ▼
          Root Cause
          + Evidence
                │
                ▼
          Risk Assessment
                │
                ▼
         Human Approval
                │
                ▼
              Fix
                │
                ▼
           Verification
                │
                ▼
             Learning
```

Measure actual results rather than manufacturing a benchmark.

---

# 32. Critical Design Decisions

## Decision 1

**Bob remains the primary engineering agent.**

BRE orchestrates Bob rather than replacing it.

## Decision 2

**ASMOS is an intelligence subsystem, not the product itself.**

Its primary roles:

- context routing
- engineering memory
- task analysis
- learning

## Decision 3

**Reliability lifecycle is the product.**

The product owns:

```text
Detect → Investigate → Diagnose → Risk → Approve → Remediate → Verify → Learn
```

## Decision 4

**Verification is a first-class subsystem.**

Never mark an incident resolved merely because a patch was generated.

## Decision 5

**Risk determines autonomy.**

The higher the risk, the stronger the human control.

---

# 33. What Not to Build

Do not start by implementing:

- dozens of connectors
- Kubernetes support
- production deployment automation
- complex multi-agent swarms
- massive vector databases
- fully autonomous production deployment
- sophisticated observability infrastructure
- dozens of incident types
- large UI/dashboard
- unnecessary microservices

The first milestone is a **complete end-to-end reliability loop**.

---

# 34. Implementation Order

Build in this order:

```text
PHASE 1
────────
Project skeleton
       ↓
Domain models
       ↓
Incident state machine
       ↓
Incident API


PHASE 2
────────
Repository connector
       ↓
Git connector
       ↓
Test runner
       ↓
Investigation engine


PHASE 3
────────
ASMOS task analyzer
       ↓
Context router
       ↓
Context ranking
       ↓
Basic engineering memory


PHASE 4
────────
IBM Bob adapter
       ↓
Root cause analysis
       ↓
Remediation orchestration


PHASE 5
────────
Risk engine
       ↓
Approval workflow
       ↓
Audit trail


PHASE 6
────────
Verification engine
       ↓
Failure feedback loop
       ↓
Rollback


PHASE 7
────────
Memory consolidation
       ↓
Metrics
       ↓
Demo UI
```

---

# 35. First Milestone

The first milestone is **not** a polished UI.

It is this:

```text
Given:
    A repository
    A reproducible failing test

BRE can:

    1. Create incident
    2. Investigate repository
    3. Gather evidence
    4. Produce root cause
    5. Calculate risk
    6. Request approval
    7. Ask Bob to implement fix
    8. Run tests
    9. Verify result
   10. Store verified learning
```

If this works end-to-end, we have the core product.

---

# 36. Product North Star

```text
              ┌─────────────────────────┐
              │       IBM BOB           │
              │                         │
              │  Understand             │
              │  Plan                   │
              │  Code                   │
              │  Execute                │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   BOB RELIABILITY       │
              │       ENGINE             │
              │                         │
              │  Investigate            │
              │  Reason                 │
              │  Assess Risk            │
              │  Control                │
              │  Verify                 │
              │  Remember               │
              └────────────┬────────────┘
                           │
                           ▼
                 ┌──────────────────┐
                 │ TRUSTWORTHY       │
                 │ SOFTWARE         │
                 │ ENGINEERING      │
                 └──────────────────┘
```

> **North-star statement:**  
> **BRE enables IBM Bob to safely own the software-reliability lifecycle—from failure detection through investigation, evidence-backed remediation, independent verification, and engineering learning.**

---

# 37. Implementation Status

## Tech Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite + SQLAlchemy
- **Models:** Pydantic v2
- **Testing:** pytest

## Phase 1 — Foundation ✅ (Complete)

### What Was Built

```text
Project Skeleton
       ↓
Domain Models (Pydantic)
       ↓
Incident State Machine
       ↓
SQLite Database Schema
       ↓
FastAPI REST Endpoints
```

### Project Structure

```text
bob-reliability-engineer/
├── apps/api/
│   ├── main.py              # FastAPI application
│   ├── database.py          # SQLAlchemy models + SQLite setup
│   └── routes/
│       ├── incidents.py     # Incident CRUD + state transitions
│       └── investigations.py # Investigation + evidence management
├── models/
│   ├── incident.py          # Incident model + state machine
│   ├── investigation.py     # Investigation + Evidence models
│   ├── diagnosis.py         # Diagnosis model
│   ├── risk.py              # RiskAssessment model
│   ├── approval.py          # Approval model
│   ├── remediation.py       # Remediation model
│   └── verification.py      # Verification model
└── requirements.txt
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/incidents` | Create incident |
| `GET` | `/api/incidents` | List incidents |
| `GET` | `/api/incidents/{id}` | Get incident |
| `POST` | `/api/incidents/{id}/transition?new_status=X` | State transition |
| `POST` | `/api/investigations` | Create investigation |
| `GET` | `/api/investigations` | List investigations |
| `GET` | `/api/investigations/{id}` | Get investigation |
| `POST` | `/api/investigations/{id}/evidence` | Add evidence |
| `POST` | `/api/investigations/{id}/complete` | Complete investigation |

### Incident State Machine

```text
DETECTED → INVESTIGATING → DIAGNOSED → RISK_ASSESSED → AWAITING_APPROVAL → REMEDIATING → VERIFYING → RESOLVED → CLOSED
```

### Database Tables

- `incidents` — Core incident record
- `investigations` — Investigation tracking
- `evidence` — Evidence collected during investigation
- `diagnoses` — Root cause analysis
- `risk_assessments` — Risk classification
- `approvals` — Approval audit trail
- `remediations` — Fix tracking
- `verification_runs` — Test verification
- `engineering_memory` — Learned knowledge

### Running the Service

```bash
cd bob-reliability-engineer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --port 8001
```

## Phase 2 — Evidence Collection (Planned)

```text
RepositoryConnector    — Read source files, detect structure
GitConnector           — Commit history, blame, diffs
TestConnector          — Discover and run tests
CIConnector            — Parse CI failure output
InvestigationEngine    — Orchestrate evidence collection
```

## Phase 3 — Context Intelligence (Planned)

```text
TaskAnalyzer           — Classify incident type
ContextRouter          — Gather candidates from sources
ContextRanker          — Score and rank relevance
EngineeringMemory      — Basic keyword search storage
```

## Phase 4 — Bob Integration (Planned)

```text
BobAdapter             — REST client to IBM Bob
RootCauseAnalyzer      — Structure Bob's diagnosis output
RemediationOrchestrator — Send fix tasks to Bob
```

## Phase 5 — Risk + Approval (Planned)

```text
RiskClassifier         — 4-level risk assessment
ApprovalWorkflow       — Human approval gate
AuditTrail             — Decision logging
```

## Phase 6 — Verification + Feedback (Planned)

```text
Verifier               — Run targeted/component/regression tests
FailureFeedbackLoop    — Re-investigate on failure
Rollback               — Git-based rollback
```

## Phase 7 — Learning + Demo (Planned)

```text
MemoryConsolidation    — Store verified outcomes only
Observability          — Structured logging
DemoDashboard          — Visual workflow stages
Metrics                — Resolution rate, time-to-diagnose
```
