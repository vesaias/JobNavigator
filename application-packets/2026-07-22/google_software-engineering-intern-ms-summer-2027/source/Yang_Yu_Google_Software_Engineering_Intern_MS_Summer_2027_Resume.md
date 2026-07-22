# Yang Yu

Davis, CA | devilsrocbuddhasgildedimage@gmail.com | +1-530-304-3656 | linkedin.com/in/yy030305 | github.com/eyesofish

## Education

### University of California, Davis | Davis, CA

M.S. in Computer Science, Expected Jun 2027 | Sep 2025 - Jun 2027

### Dalian University of Technology | Dalian, China

B.Eng. in Software Engineering | Aug 2021 - Aug 2025

## Technical Skills

- Languages: C++, Java, Python, JavaScript, SQL
- Core and Systems: Data Structures, Algorithms, Distributed Systems, large software systems, Raft, Protobuf/RPC, Bazel
- AI/ML and Information Retrieval: PyTorch, RAG, embeddings, vector retrieval, reranking, recommendation systems, LangChain, LangGraph
- Application and Engineering: FastAPI, REST APIs, MySQL, Docker, Git, unit testing, CI/test triage, debugging, mobile build/test workflows

## Experience

### Software Engineering Intern | Microsoft | Suzhou, Jiangsu, China

Jun 2026 - Present

- Independently established the local build-test loop for Microsoft 365 Copilot mobile in a tightly coupled monorepo, using sparse checkout and prebuilt dependencies to complete a 1,500+ step build across 100+ subprojects, run unit tests, and launch an authenticated demo in an iPhone simulator.
- Diagnosed a deterministic build failure at 96% through read-only inspection and a controlled deletion experiment, isolating four stale test frameworks and restoring two build workflows with targeted cleanup instead of a 20+ minute clean rebuild.
- Analyzed failure histories across about 30 reliability builds to distinguish six consistently failing targets from flaky tests; supported a quarantine change that stopped weeks of automated bug noise and preserved technical-debt tracking, then merged with three approvals and all checks passing.

## Projects and Open Source

### Apache Incubator ResilientDB - Raft Consensus Implementation | C++, Bazel, Protobuf/RPC

Sep 2025 - Nov 2025

- Implemented leader election, heartbeat handling, log replication, commit flow, and state-machine application in an existing distributed database codebase.
- Built persistence, snapshots, and crash recovery through `RaftLog`, `PersistentState`, and `SnapshotManager` to preserve replicated state across node restarts.

### ZhihuRec 1M Recommendation System Prototype | Python, FastAPI, MySQL, JavaScript, Docker

Apr 2026 - May 2026

- Built feed, search, event, profile, and debug REST APIs with multi-source retrieval, topic reranking, cold-start profile blending, and click-driven profile updates.
- Evaluated the search-to-feed loop across 121 replay events, raising Post-Search Topic Carryover@10 from 0.9000 to 1.0000.

### LLM + RAG Software Engineering Resource Recommender | LangChain, LangGraph, Qwen API

Jan 2026 - Present

- Built an agentic RAG workflow that decomposes technical queries into retrieval, filtering, reasoning, and result organization to return source-grounded recommendations.
