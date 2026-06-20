# AI Engineer Resume and Study Coach Agent Design

## Objective

Produce an ATS-friendly, one-page English resume for Singapore AI Engineer internship applications and define a credible one-month upgrade of `final-agent` from a RAG study assistant into a tool-using adaptive study coach.

## Resume Positioning

- Target title: **AI Engineer Intern**.
- Target market: Singapore internship and entry-level roles.
- Availability: full-time internship from September 2026 through 22 January 2027.
- Format: one-page, single-column, ATS-friendly DOCX and PDF.
- Content order: Header, Summary, Technical Skills, Projects, Competition, Education.
- Current claims must describe implemented work only. Future Agent capabilities must not appear until they are implemented and measured.

## Resume Content Rules

- Link the RAG project title to `https://github.com/ybh1291747665/final-agent`.
- Treat Java and Spring Boot as coursework exposure rather than project-ready skills.
- Treat ChromaDB, BM25, RRF, Streamlit, and PaddlePaddle as project exposure.
- Do not claim Jetson Nano deployment because it was completed by a teammate.
- Do not publish unmeasured RAG accuracy or latency values.
- Present the intelligent-car award as a China national final to avoid geographic ambiguity.
- Keep contact information as editable placeholders except for the public GitHub URL.

## Current Evidence

### RAG-Powered Study Assistant

Implemented multimodal PDF ingestion, page-aware chunking, dense and BM25 retrieval, RRF fusion, cross-encoder reranking, citation-grounded generation, semantic hallucination checks, course filtering, and five study modes. The repository currently has no automated tests or measured evaluation suite.

### Federated Learning Platform

Personal graduation project using a PC coordinator and three Raspberry Pi clients. Supports CIFAR-10 and ECG tasks, PyTorch training, Flask administration, TCP model exchange, Chart.js monitoring, FedAvg, and the custom Fed-ADP aggregation method. Recorded final accuracy was about 63% versus 58% for FedAvg on CIFAR-10 and 94% versus 91% on ECG.

### Intelligent Car Competition

First Prize at the China National Finals. Personal contributions include PP-YOLOE+ object-detector training with 99% validation mAP, collection of about 30,000 labeled track images, ResNet-18 regression training for continuous steering deviation, the C-based vision baseline, positional PID steering, and detection-triggered state-machine logic.

## Agent Upgrade Scope

Build one LangGraph-based agent rather than a multi-agent system. The agent will plan a review workflow, invoke typed tools, pause for a learner response, grade the answer, update persistent mastery, and adapt the next task.

### Architecture

```text
Streamlit UI
    -> FastAPI agent service
        -> LangGraph orchestrator
            -> search_course_material
            -> summarize_course
            -> generate_quiz
            -> grade_answer
            -> get_learning_profile
            -> update_mastery
        -> existing RAG pipeline
        -> SQLite learner memory and run traces
```

### Agent State

The graph state contains a session identifier, learning goal, generated plan, current step, selected course identifiers, retrieved context, quiz, learner answer, grading result, mastery updates, tool trace, and terminal status.

### Safety and Control

- Maximum six tool calls per run.
- Typed Pydantic inputs and outputs for every tool.
- Explicit error results instead of uncaught tool exceptions.
- Human-in-the-loop pause before grading.
- Persistent tool trace for debugging and evaluation.
- No multi-agent delegation in the first release.

## Evaluation

Create a fixed dataset of 30 scenarios:

- 10 retrieval and citation-grounding tasks.
- 10 tool-selection and workflow tasks.
- 10 adaptive-review and memory tasks.

Report task completion rate, tool-selection accuracy, citation-grounding rate, grading agreement, response latency, and automated-test pass count. Only measured values may be added to the resume.

## Definition of Done

- The current one-page resume renders without clipping or overflow.
- The Agent can create a plan, select tools, pause for an answer, grade it, persist mastery, and choose a next task.
- Core RAG and Agent behavior has automated tests.
- The repository contains an English README, architecture diagram, example workflow, evaluation results, and a short demonstration.
- The revised resume uses `Adaptive Study Coach Agent` only after these criteria are met.

