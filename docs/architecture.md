# Architecture

The system uses Clean Architecture boundaries: FastAPI and MCP are adapters, services coordinate use cases, repositories isolate persistence, and domain models represent durable state. Long-running workflows are represented by a checkpointed LangGraph and dispatched through Celery/Redis. Browser submission remains approval-gated.

## Supported ATS

Greenhouse, Lever, Ashby, Workday, and SmartRecruiters are represented through the generic adapter contract. Connector implementations should use runtime-discovered labels and accessibility metadata; the automation layer never depends on a fixed CSS selector.
