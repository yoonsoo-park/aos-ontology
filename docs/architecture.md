# AOS Ontology — Architecture Overview

Salesforce 메타데이터(XML)를 파싱해서 entity/process/domain 통합 그래프 모델로 변환하고, Obsidian vault + JSON 형태로 출력하는 시스템. Query 라이브러리로 entity 검색, relationship 탐색, process bottleneck 분석을 지원.

---

## 데이터 파이프라인

```
SF Metadata XML                                     사용자 조회
(.object-meta.xml,                                  (cli_demo.py,
 .field-meta.xml)                                    Lambda API)
      |                                                  ^
      v                                                  |
 [1. Parsing]                                      [4. Query]
 parse_sf_metadata.py                              ontology_query/
      |                                                  ^
      v                                                  |
 dict[str, SFObject]                               output/vault/
      |                                            entities/*.md
      +--------+--------+                          _meta/index.json
      |        |        |                          _meta/graph.json
      v        v        v                          _meta/metrics/*.json
 [2a. Vault] [2b. Graph] [2c. Process]             processes/*.md
```

### 단계별 설명

| 단계 | 입력 | 출력 | 핵심 모듈 |
|------|------|------|-----------|
| **1. Parsing** | SF XML 디렉토리 | `dict[str, SFObject]` | `parse_sf_metadata.py` |
| **2a. Vault 생성** | SFObject + VaultConfig | `entities/*.md`, `domains/*.md`, `_meta/index.json` | `generate_vault.py` |
| **2b. Graph 생성** | SFObject + ProcessConfig | `_meta/graph.json`, `_meta/metrics/*.json` | `graph_builder.py` → `generate_graph.py` |
| **2c. Process 생성** | ProcessConfig (from JSON) | `processes/*.md`, `_meta/process_index.json` | `generate_processes.py` |
| **3. LLM 보조** (optional) | SFObject + context | VaultConfig 또는 ProcessConfig JSON | `agent_assist.py`, `process_agent.py` |
| **4. Query** | vault 디렉토리 | 검색 결과, traversal, bottleneck 분석 | `ontology_query/` |

---

## 모듈 맵

4개 레이어로 구성. 위에서 아래로 의존.

### Layer 1: Data Models (의존성 없음)

| 파일 | 역할 | 핵심 클래스 |
|------|------|-------------|
| `scripts/ontology/models.py` | SF 메타데이터 구조 | `SFObject`, `SFField`, `SFRelationship`, `SFPicklistValue` |
| `scripts/ontology/process_models.py` | 프로세스/스테이지 구조 | `ProcessConfig`, `StageConfig`, `StageMetrics`, `EntityInvolvement`, `BottleneckSeverity`, `StageType` |
| `scripts/ontology/graph_model.py` | 통합 그래프 구조 | `OntologyGraph`, `Node`, `Edge`, `NodeType`, `EdgeType` |

### Layer 2: Parsing & Loading

| 파일 | 역할 | 입력 → 출력 |
|------|------|-------------|
| `scripts/ontology/parse_sf_metadata.py` | SF XML 파서 | XML dirs → `dict[str, SFObject]` |
| `scripts/ontology/process_config_loader.py` | JSON config 로더 | `configs/processes/*.json` → `dict[str, ProcessConfig]` |
| `scripts/ontology/config.py` | 정적 설정 | tier 정의, domain 매핑, 네임스페이스 |
| `scripts/ontology/vault_config.py` | Vault 설정 모델 | domain/tier 매핑 save/load |

### Layer 3: Generation (출력 생성)

| 파일 | 역할 | 출력 |
|------|------|------|
| `scripts/ontology/generate_vault.py` | Entity/domain markdown 생성 | `entities/*.md`, `domains/*.md`, `_meta/index.json` |
| `scripts/ontology/generate_processes.py` | Process bottleneck 노트 생성 | `processes/*.md`, `_meta/process_index.json` |
| `scripts/ontology/graph_builder.py` | SFObject + ProcessConfig → Graph 조립 | `OntologyGraph` (in-memory) |
| `scripts/ontology/generate_graph.py` | Graph JSON 직렬화 | `_meta/graph.json`, `_meta/metrics/*.json` |
| `scripts/ontology/generate_obsidian_config.py` | Obsidian 설정 생성 | `.obsidian/` (CSS, graph colors) |
| `scripts/ontology/metrics.py` | Metrics adapter 인터페이스 | `MetricsAdapter` ABC + `SyntheticMetricsAdapter` |

### Layer 4: LLM Agent (optional, Bedrock Claude)

| 파일 | 역할 | LLM이 하는 일 |
|------|------|---------------|
| `scripts/ontology/agent_assist.py` | Vault config 자동 생성 | entity → domain 분류, tier 랭킹 |
| `scripts/ontology/process_agent.py` | Process config 자동 생성 | stage picklist → 구조/entity/metrics 추론 |

### Query Library (독립 모듈, 외부 의존성 없음)

| 파일 | 역할 | 핵심 클래스 |
|------|------|-------------|
| `ontology_query/reader.py` | 파일 읽기 추상화 | `VaultReader` (Protocol), `LocalVaultReader`, `S3VaultReader` |
| `ontology_query/index.py` | Entity 인덱스 | `OntologyIndex` — api_name/label로 조회 |
| `ontology_query/search.py` | Entity 검색 + BFS 탐색 | `OntologySearch` — 상세 조회, relationship, traverse |
| `ontology_query/resolver.py` | Source 매핑 | `SourceResolver` — entity → data source/SLA |
| `ontology_query/process_index.py` | Process 인덱스 | `ProcessIndex` — process 조회, entity 참여 조회 |
| `ontology_query/process_search.py` | Process 검색 | `ProcessSearch` — stage 조회, bottleneck, flow |
| `ontology_query/frontmatter.py` | YAML 파서 | `parse_frontmatter()` — 외부 의존성 없음 |

---

## 핵심 데이터 모델

### SFObject (SF 메타데이터)

```
SFObject
  ├── api_name: "LLC_BI__Loan__c"
  ├── label: "Loan"
  ├── namespace: "LLC_BI"
  ├── fields: [SFField, ...]        ← 각 필드의 type, picklist values 포함
  ├── relationships: [SFRelationship, ...]     ← 이 object가 참조하는 관계
  └── incoming_relationships: [SFRelationship, ...]  ← 이 object를 참조하는 관계
```

### ProcessConfig (프로세스 정의)

`configs/processes/loan-origination.json`에서 로드. 18개 stage의 구조와 metrics.

```
ProcessConfig
  ├── process_key: "loan-origination"
  ├── source_object: "LLC_BI__Loan__c"
  ├── stage_field: "LLC_BI__Stage__c"
  ├── domain: "loan-origination"
  └── stages: [StageConfig, ...]
        ├── name: "Qualification"
        ├── stage_type: SEQUENTIAL | PARALLEL | POST_CLOSE
        ├── order: 1
        ├── predecessors/successors: ["proposal"]
        ├── involved_entities: [EntityInvolvement, ...]
        └── metrics: StageMetrics
              ├── avg_days, p50_days, p90_days
              ├── entry_count, exit_count
              ├── error_rate, rework_rate
              ├── sla_target_days, sla_met_pct
              └── bottleneck_severity: NONE | LOW | MEDIUM | HIGH | CRITICAL
```

### OntologyGraph (통합 그래프)

모든 entity, process, stage, domain을 하나의 그래프로 통합. `_meta/graph.json`으로 출력.

```
OntologyGraph
  ├── nodes: [Node, ...]
  │     ├── ENTITY   → entity::LLC_BI__Loan__c
  │     ├── PROCESS  → process::loan-origination
  │     ├── STAGE    → stage::loan-origination::qualification
  │     └── DOMAIN   → domain::loan-origination
  │
  └── edges: [Edge, ...]
        ├── SF_RELATIONSHIP      → entity 간 Lookup/MasterDetail
        ├── STAGE_TRANSITION     → stage 간 순서 (qualification → proposal)
        ├── STAGE_INVOLVEMENT    → stage ↔ entity 참여 관계
        ├── DOMAIN_MEMBERSHIP    → entity → domain 소속
        └── PROCESS_CONTAINS     → process → stage 포함
```

Metrics는 별도 파일 (`_meta/metrics/{process_key}.json`)로 분리. Graph 구조 변경 없이 metrics만 갱신 가능.

---

## CLI 사용법

### 기본: Vault 생성

```bash
# Tier 2까지 (107 entities) vault 생성
python -m scripts.ontology.main \
    --output output/vault

# 전체 LLC_BI 네임스페이스
python -m scripts.ontology.main \
    --all-objects --namespace LLC_BI \
    --output output/vault
```

### LLM으로 domain/tier 자동 분류

```bash
python -m scripts.ontology.main \
    --all-objects --namespace LLC_BI \
    --agent \
    --context "commercial banking loan origination" \
    --save-config output/vault_config_agent.json \
    --output output/vault_agent
```

### Process bottleneck 분석 생성

```bash
python -m scripts.ontology.main \
    --all-objects --namespace LLC_BI \
    --config output/vault_config_agent.json \
    --processes \
    --output output/vault_agent
```

### 통합 Graph 생성

```bash
python -m scripts.ontology.main \
    --all-objects --namespace LLC_BI \
    --config output/vault_config_agent.json \
    --processes --graph \
    --output output/vault_agent
```

### LLM으로 Process config 자동 생성

```bash
# SF 메타데이터에서 프로세스 후보 발견 + config 생성
python -m scripts.ontology.main \
    --all-objects --namespace LLC_BI \
    --discover-processes \
    --context "commercial banking" \
    --save-process-config /tmp/review/

# 리뷰 후 configs/processes/에 복사하면 다음 실행부터 자동 로드
```

### Query (CLI demo)

```bash
python cli_demo.py --vault output/vault entity "Loan"
python cli_demo.py --vault output/vault traverse "Loan" --depth 2
python cli_demo.py --vault output/vault domains
python cli_demo.py --vault output/vault bottlenecks loan-origination
```

---

## 출력 디렉토리 구조

```
output/vault/
├── entities/
│   ├── Loan.md                    # entity 상세 (frontmatter + relationships + key fields)
│   ├── Account.md
│   └── ... (285개)
├── domains/
│   ├── loan-origination.md        # domain별 entity 목록
│   └── ... (39개)
├── processes/
│   └── loan-origination.md        # bottleneck 분석 노트 (Mermaid flow, charts, metrics tables)
├── _meta/
│   ├── index.json                 # entity 조회 인덱스
│   ├── process_index.json         # process 메타데이터 + stage 상세
│   ├── graph.json                 # 통합 그래프 (343 nodes, 902 edges)
│   └── metrics/
│       └── loan-origination.json  # stage별 metrics overlay
└── .obsidian/                     # Obsidian 설정 (graph colors, CSS, plugins)
```

---

## 확장 포인트

### 새 프로세스 추가

1. `configs/processes/{process-key}.json` 파일 하나 추가
2. 또는 `--discover-processes`로 LLM이 SF 메타데이터에서 자동 생성
3. 다음 `--processes --graph` 실행 시 자동 반영

### Metrics Adapter 교체

`scripts/ontology/metrics.py`의 `MetricsAdapter` ABC 구현:
- `SyntheticMetricsAdapter` — 현재 사용 (JSON config의 synthetic_metrics)
- `SalesforceMetricsAdapter` — SF API에서 실제 stage duration 조회 (미구현)
- Custom adapter — 어떤 데이터 소스든 가능

### Graph Consumer 추가

`_meta/graph.json`은 portable format:
- **Obsidian** — 현재 `process-flow.ts` 플러그인이 process_index.json 소비
- **neo4j** — `graph.json` → Cypher LOAD 변환기 (향후)
- **Cytoscape standalone** — 동일 JSON 직접 로드 가능
- **API** — gateway repo의 Lambda가 `ontology_query/` 라이브러리로 조회

---

## 테스트

```bash
# 전체 테스트 (140개)
python -m pytest tests/ -v

# 모듈별
python -m pytest tests/test_ontology_query.py   # query 라이브러리 (29 tests)
python -m pytest tests/test_process.py           # process models + generation (25 tests)
python -m pytest tests/test_graph_model.py       # graph model + builder (24 tests)
python -m pytest tests/test_vault_config.py      # vault config (4 tests)
python -m pytest tests/test_process_agent.py     # process agent (22 tests)
```

---

## 파일 목록

### scripts/ontology/ (16 files)

| 파일 | 역할 |
|------|------|
| `main.py` | CLI 진입점 — 모든 플래그 처리 |
| `models.py` | SF 메타데이터 dataclass (SFObject, SFField, SFRelationship) |
| `config.py` | 정적 설정 (tiers, domains, namespaces) |
| `parse_sf_metadata.py` | SF XML → SFObject 파싱 |
| `vault_config.py` | VaultConfig 모델 (domain/tier 매핑) |
| `generate_vault.py` | Entity/domain markdown 생성 |
| `generate_processes.py` | Process bottleneck 노트 생성 |
| `generate_obsidian_config.py` | Obsidian 설정 생성 |
| `process_models.py` | ProcessConfig, StageConfig, StageMetrics |
| `process_config_loader.py` | JSON → ProcessConfig 로더 |
| `graph_model.py` | Node, Edge, OntologyGraph |
| `graph_builder.py` | SFObject + ProcessConfig → OntologyGraph |
| `generate_graph.py` | graph.json + metrics 출력 |
| `metrics.py` | MetricsAdapter ABC + SyntheticAdapter |
| `agent_assist.py` | LLM 보조 — domain/tier 추론 |
| `process_agent.py` | LLM 보조 — process config 자동 생성 |

### ontology_query/ (7 files)

| 파일 | 역할 |
|------|------|
| `reader.py` | VaultReader protocol + Local/S3 구현 |
| `index.py` | OntologyIndex — entity 조회 |
| `search.py` | OntologySearch — 상세 검색 + BFS traverse |
| `resolver.py` | SourceResolver — data source 매핑 |
| `process_index.py` | ProcessIndex — process 조회 |
| `process_search.py` | ProcessSearch — stage/bottleneck 검색 |
| `frontmatter.py` | YAML frontmatter 파서 (zero deps) |

### configs/processes/ (1 file)

| 파일 | 역할 |
|------|------|
| `loan-origination.json` | 18-stage loan origination config (synthetic metrics) |

### tests/ (5 files, 140 tests)

| 파일 | 테스트 대상 | 개수 |
|------|------------|------|
| `test_ontology_query.py` | reader, index, search, resolver, frontmatter | 47 |
| `test_process.py` | process models, generation, ProcessSearch, ProcessIndex | 32 |
| `test_graph_model.py` | graph model, builder, config loader, metrics | 24 |
| `test_vault_config.py` | VaultConfig save/load, agent-assisted generation | 15 |
| `test_process_agent.py` | discovery, BFS, validation, mock LLM | 22 |

### obsidian-ontology-explorer/ (TypeScript)

| 파일 | 역할 |
|------|------|
| `main.ts` | Obsidian plugin 진입점 |
| `src/process-flow.ts` | Cytoscape.js DAG 시각화 |
| `src/bottleneck-view.ts` | Bottleneck dashboard view |
