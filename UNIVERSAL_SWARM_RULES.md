# Universal & Dynamic Agentic Swarm Rules of Engagement

To enforce maximum autonomy, language-agnostic operational capabilities, and exponential token-efficiency, the Agentic Framework must abandon rigid sequential pipelines in favor of a **Topology-Driven Universal Swarm Architecture**.

The Swarm MUST adhere to the following 5 Pillars of Orchestration across any tech stack, project, or operational goal.

---

## Pillar 1: Dynamic Instantiation (The "Scout" Protocol)
* **Abandonment of Static Phases:** A project cannot force a standard 7-phase waterfall if the objective is merely a 1-line CSS change or a global Database overhaul. 
* **The Rule:** The very first agent dispatched is always the **Scout Agent**. The Scout executes read-only directory and AST mapping to deduce the stack constraints (e.g., detecting `.tf`, `Cargo.toml`, or `build.gradle`). 
* **Dynamic Router:** The Scout translates the user's intent within the scope of the detected environment and *dynamically hallucinates* the specific Swarm Graph needed for that job, dispatching sub-agents accordingly.

## Pillar 2: Contract-Driven Orchestration
* **Context Bleed Eradication:** Agents attempting to comprehend the entire project by reading cross-module peer code fundamentally halts scaling. Worker agents are forbidden from directly observing siblings in a swarm thread.
* **The Rule:** If Swarm Nodes must interoperate (e.g. Agent A builds an API endpoint, Agent B builds the React View layer), an abstract Orchestrator Agent writes a formal **API Schema/Contract** (OpenAPI JSON, gRPC Protocol buffer, or Markdown Interface Definition). 
* **Execution:** Agent A and Agent B code blindly and strictly against the Contract, completely independently, allowing for multi-threaded completion with a 90% reduction in context burn.

## Pillar 3: Context Virtualization (Hierarchical Mapping)
* **The Ban on Full-File Context:** Agents traversing project architectures inevitably drown the context window by running raw file reads on 2,000-line monolith files.
* **The Rule:** Swarm Agents must utilize a **Hierarchical Context Tree**. When traversing foreign architecture, agents rely purely on line-number boundary grepping and AST structure retrieval (parsing function names and class definitions) to build a topological map.
* **Execution:** A file payload is NEVER extracted entirely into working memory unless the agent has actively verified that the localized change requires a full-file rewrite.

## Pillar 4: Micro-Event Horizons (Token Safeguards)
* **The Problem with Phase-Based Testing:** Waiting to compile or test code only after the "Execution Phase" is fully complete results in catastrophic, unrecoverable cascading hallucination chains that obliterate the token allowance.
* **The Rule:** Every autonomous agent operates under a strict **Micro-Event Horizon**. An agent may not execute more than `N` logical state changes or isolated file-writes without explicitly triggering an isolated validation mechanism (e.g. syntax linter, compiler pipeline, or unit test runner). 
* **Execution:** Fail fast. If the Micro-Event validation catches an error, the agent isolates the single change block immediately rather than rewriting the architecture.

## Pillar 5: Asynchronous Auto-Pruning (The Watchtower Mesh)
* **Continuous Integration Native:** Security auditing and Code Reviewing do not happen "at the end."
* **The Rule:** The Swarm operates **Watchtower Agents**. These are passive, parallel-processing nodes that listen to the execution stream buffers. As soon as a worker node saves a file or proposes a diff block, the Watchtower evaluates it instantaneously for security anti-patterns or stylistic linting.
* **Execution:** If a worker injects a flawed dependency, the Watchtower rejects the specific chunk, flags the worker, and automatically spins up a localized correction loop while the rest of the Swarm continues forward unhindered.

## Pillar 6: Human-in-the-Loop (HITL) Integration Bounds
* **The Danger of Unbounded Autonomy:** While worker agents are highly autonomous, allowing a swarm to execute a globally destructive directive without human oversight leads to silent architectural drift.
* **The Rule:** The human acts as an **Apex Governor**, involved *only* during precise Escalation Traps, Blueprint Blessings, and Final Rollouts.
* **Execution Gates:**
  1. **Zero-Day Requirements Verification (The Architecture Council):** Before the Scout Agent spins up or any code is considered, the Human is presented with a strict blueprint proposed by a swarm of five specialized agents:
     * **Solution Architect:** Defines the business logic, product constraints, and user stories.
     * **System Architect:** Dictates compute environments, containerization, and orchestration infrastructure.
     * **Data Architect:** Maps state persistence, schema relationships, and data pipelines.
     * **Network Architect:** Defines API topologies, routing layers, and transit protocols.
     * **Cyber Architect:** Establishes Zero Trust perimeters, encryption standards, and threat models.
     This Executive Council aggressively crushes all subjective abstractions by **proactively generating and proposing a set of strict, unambiguous requirements and technical constraints.** The Human is only required to review, refine, or approve this proposed blueprint before it is formalized and handed to the Scout.
  2. **Contract Blessing (Post-Scout):** Before the Orchestrator unleashes the parallel worker Swarm, it presents the global AST schema and implementation plan to the User for approval.
  3. **Escalation Traps:** If an agent's Micro-Event validation fails and the localized correction loop fails `N` times in a row (ex: 3 compiler panics), the swarm physically halts that thread and escalates back to the User. Tokens are too precious to let a hallucinating agent loop indefinitely.
  4. **Final Deployment:** After the Watchtowers sign off, the Swarm collapses the PR branch and halts. The human performs the macro-level acceptance testing and dictates final CI/CD merges.
