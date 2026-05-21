# Ontology Extraction Roadmap

## Vision

Ontology는 두 개의 독립적이지만 결합된 layer로 구성된다:

- **Layer 1: Banking Core Schema** — core banking system (JH/Temenos/FIS/Fiserv 등)의 데이터 구조
- **Layer 2: nCino Domain Logic** — workflow intent, compliance, business semantics

두 레이어가 합쳐져야 AI agent가 단순히 데이터를 읽는 것이 아니라, 은행 운영의 맥락에서 의미 있는 의사결정을 할 수 있다.

---

## Current State

### Completed (Production-ready)

| Capability | Status | Artifact |
|------------|--------|----------|
| SF metadata XML parsing | 285 entities extracted | `parse_sf_metadata.py` |
| Entity/Field/Relationship graph | 902 edges mapped | `output/vault/entities/*.md` |
| Domain classification | 39 domains (LLM + manual) | `_meta/index.json` |
| Query library | Entity, traverse, field search, resolve | `ontology_query/` (zero deps) |
| Unified Graph Model | 343 nodes, 5 edge types | `_meta/graph.json` |
| Process modeling | Loan origination 18 stages | `configs/processes/` |
| Bottleneck analysis | Severity-based detection | `process_search.py` |
| LLM-assisted automation | Domain/tier classification, process discovery | `agent_assist.py`, `process_agent.py` |
| Obsidian vault visualization | Entity graph + process flow | `.obsidian/` plugin |
| S3 deployment | Gateway Lambda via S3VaultReader | `reader.py` Protocol |
| Tests | 140 tests, 5 modules | `tests/` |

### Partial (15-50%)

| Capability | Current | Gap |
|------------|---------|-----|
| Process coverage | Loan origination only | Deposit, HELOC, credit etc. undefined |
| Metrics | 100% synthetic (benchmark-based) | No real SF API integration |
| Field semantics | Name/type only | No business meaning or data classification |

### Not Started (0%)

| Capability | Why It Matters | Layer |
|------------|----------------|-------|
| Semantic meaning | "What does this entity represent in business terms?" | Layer 2 |
| Compliance/regulatory mapping | Which fields have PCI-DSS, GLBA, state lending law implications? | Layer 2 |
| Workflow intent | Why does each stage exist? Approval gates? Error recovery? | Layer 2 |
| Data lineage | Where is this field derived from? (formula, rollup) | Layer 2 |
| Business glossary | Term definitions, homonym disambiguation | Layer 2 |
| Banking Core Schema | Core system (JH/FIS/etc) data structure extraction | Layer 1 |
| Core-nCino mapping | JH loan_amount <-> LLC_BI__Amount__c | Layer 1<->2 |

---

## Progress Map

```
Layer 1: Banking Core Schema          ░░░░░░░░░░░░░░░░░░░░  0% (not started)
Layer 2: nCino Domain Logic
  ├── Structural metadata             ████████████████████  95%
  ├── Relationship graph              ████████████████████  90%
  ├── Process definition              ████░░░░░░░░░░░░░░░░  20%
  ├── Metrics (real data)             ██████░░░░░░░░░░░░░░  30% (synthetic only)
  ├── Semantic meaning                ██░░░░░░░░░░░░░░░░░░  10%
  ├── Compliance rules                █░░░░░░░░░░░░░░░░░░░  5%
  ├── Workflow logic (intent)         █░░░░░░░░░░░░░░░░░░░  5%
  ├── Data lineage                    ░░░░░░░░░░░░░░░░░░░░  0%
  └── Business glossary               ░░░░░░░░░░░░░░░░░░░░  0%
Layer 1<->2 Mapping                    ░░░░░░░░░░░░░░░░░░░░  0% (not started)

Overall: ~30-35%
```

---

## Roadmap

### Phase 1: Layer 2 Depth (Current -> 2 months)

**Goal**: Add semantic meaning on top of structural metadata.

| Task | Method | Expected Result |
|------|--------|-----------------|
| Process addition (3-4) | `--discover-processes` + manual curation | Deposit, HELOC, credit etc. |
| Semantic enrichment | LLM + SF field description parsing | 1-2 line business meaning per entity |
| Compliance tagging | GLBA/CRA/PCI-DSS framework mapping | `compliance_tags` in field/entity frontmatter |
| Stage intent capture | LLM prompt: "why does this stage exist?" | Purpose + gates per stage |
| Real metrics pipeline | SF API adapter (SalesforceMetricsAdapter) | Synthetic -> actual transition |

**Key question**: Role of Manifest JSON
- Manifest defines what is provisioned to customer orgs
- Current pipeline input is `orgMetadata` XML (extracted from demo org)
- The delta between manifest and orgMetadata = "domain logic nCino added"

### Phase 2: Layer 1 Start (2-4 months)

**Goal**: Select one banking core system and build schema extraction POC.

| Task | Dependency | Notes |
|------|-----------|-------|
| Core system selection | Ryan/Steven + banking expert | Dev sandbox accessibility priority |
| BankingCoreAdapter interface | None | Follow `VaultReader` Protocol pattern |
| Schema extraction POC | Dev sandbox access | Entity/field/relationship extraction |
| Core-nCino mapping | Layer 2 completeness | Field-level cross-reference |

**Security framing**: We're not requesting new core access. nCino packages already access core data via customer Salesforce. Ontology consumes the same data more efficiently.

### Phase 3: Integration + Agent Layer (4-6 months)

**Goal**: Merge both layers so AI agent can answer "why?" questions.

```
Agent question: "Why is this loan stuck in Credit Underwriting?"
Required knowledge:
  - Layer 1: Core system's loan status (JH loan record)
  - Layer 2: Credit Underwriting stage entry/exit conditions (nCino workflow)
  - Mapping: JH status <-> nCino stage correspondence
  - Compliance: Regulatory checks required at this point
```

---

## Key Insight

Currently aos-ontology is a **schema crawler** — it extracts Salesforce structure well but doesn't know "why it's structured that way."

To become a domain knowledge system, it needs:
- **Intent** (why things exist)
- **Rules** (what constraints apply)
- **Real data** (actual performance metrics)
- **Feedback** (learning from usage patterns)

The highest-impact next step is **Process intent capture** — using LLM to extract each stage's business purpose, approval gates, and error handling.
