# Internship Application Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a tested Spring Boot, MySQL, and React application that demonstrates authentication, REST API design, persistence, CI/CD, and measured backend performance.

**Architecture:** Use a modular Spring Boot monolith with feature-owned packages and a React SPA. Store data in MySQL with Flyway migrations, secure endpoints with JWT, test repositories against Testcontainers, and deploy through Docker and GitHub Actions.

**Tech Stack:** Java 21, Spring Boot 3, Spring Security, JWT, Spring Data JPA, MySQL 8, Flyway, React, TypeScript, JUnit 5, Testcontainers, Docker Compose, GitHub Actions, JMeter, Actuator.

---

## Week 1: Backend Foundation and Core CRUD

### Task 1: Scaffold the Repository and Health Endpoint

**Files:**
- Create: `backend/pom.xml`
- Create: `backend/src/main/java/com/example/tracker/TrackerApplication.java`
- Create: `backend/src/main/java/com/example/tracker/config/ClockConfig.java`
- Create: `backend/src/main/resources/application.yml`
- Create: `backend/src/test/java/com/example/tracker/TrackerApplicationTest.java`
- Create: `docker-compose.yml`

- [ ] Create a Spring Boot 3 project using Java 21 with Web, Validation, Security, Data JPA, MySQL, Flyway, Actuator, and springdoc-openapi dependencies.
- [ ] Write a context-load test and an Actuator health test before adding application code.
- [ ] Configure local MySQL through environment variables and Docker Compose health checks.
- [ ] Run `./mvnw test`; expect zero failures.
- [ ] Run `docker compose up -d mysql`; expect MySQL to become healthy.
- [ ] Commit with `chore: scaffold internship tracker backend`.

### Task 2: Add Users, Registration, and Login

**Files:**
- Create: `backend/src/main/java/com/example/tracker/auth/`
- Create: `backend/src/main/java/com/example/tracker/user/`
- Create: `backend/src/main/java/com/example/tracker/common/security/`
- Create: `backend/src/main/resources/db/migration/V1__users_and_refresh_tokens.sql`
- Create: `backend/src/test/java/com/example/tracker/auth/AuthApiTest.java`

- [ ] Write API tests for successful registration, duplicate email, login, wrong password, protected endpoint without a token, refresh, and logout.
- [ ] Implement BCrypt password hashing and unique normalized email storage.
- [ ] Implement short-lived access tokens and hashed refresh-token records.
- [ ] Configure stateless Spring Security and exact public endpoint rules.
- [ ] Run `./mvnw test -Dtest=AuthApiTest`; expect all authentication tests to pass.
- [ ] Commit with `feat: add JWT authentication`.

### Task 3: Implement Companies and Opportunities

**Files:**
- Create: `backend/src/main/java/com/example/tracker/company/`
- Create: `backend/src/main/java/com/example/tracker/opportunity/`
- Create: `backend/src/main/resources/db/migration/V2__companies_and_opportunities.sql`
- Create: `backend/src/test/java/com/example/tracker/company/CompanyApiTest.java`
- Create: `backend/src/test/java/com/example/tracker/opportunity/OpportunityApiTest.java`

- [ ] Write owner-isolation tests proving one user cannot read or update another user's data.
- [ ] Implement DTO validation, services, repositories, mappers, and CRUD endpoints.
- [ ] Add pagination, sorting, company filter, and keyword search.
- [ ] Run the focused API tests; expect zero failures.
- [ ] Commit with `feat: manage companies and opportunities`.

### Task 4: Implement Applications and Status History

**Files:**
- Create: `backend/src/main/java/com/example/tracker/application/`
- Create: `backend/src/main/resources/db/migration/V3__applications_and_status_history.sql`
- Create: `backend/src/test/java/com/example/tracker/application/ApplicationWorkflowTest.java`

- [ ] Write tests for creating an application, listing by status and date, valid transitions, invalid transitions, and immutable history.
- [ ] Implement the status enum and transition policy in one domain service.
- [ ] Create a history row in the same transaction as every accepted transition.
- [ ] Return HTTP 409 with `INVALID_STATUS_TRANSITION` for forbidden changes.
- [ ] Run the workflow tests; expect zero failures.
- [ ] Commit with `feat: add application status workflow`.

## Week 2: Scheduling, Errors, Documentation, and Frontend

### Task 5: Add Interviews and Reminders

**Files:**
- Create: `backend/src/main/java/com/example/tracker/interview/`
- Create: `backend/src/main/java/com/example/tracker/reminder/`
- Create: `backend/src/main/resources/db/migration/V4__interviews_and_reminders.sql`
- Create: `backend/src/test/java/com/example/tracker/interview/InterviewApiTest.java`

- [ ] Write tests for scheduling, updating, deleting, wrong-owner access, and upcoming reminder queries.
- [ ] Store interview times with timezone-safe instant values and a display timezone.
- [ ] Implement reminder completion and upcoming reminder filters.
- [ ] Run focused tests; expect zero failures.
- [ ] Commit with `feat: add interviews and reminders`.

### Task 6: Standardize Errors and OpenAPI

**Files:**
- Create: `backend/src/main/java/com/example/tracker/common/error/ApiError.java`
- Create: `backend/src/main/java/com/example/tracker/common/error/GlobalExceptionHandler.java`
- Create: `backend/src/main/java/com/example/tracker/config/OpenApiConfig.java`
- Create: `backend/src/test/java/com/example/tracker/common/error/ErrorContractTest.java`

- [ ] Write tests for validation, missing resource, conflict, unauthorized, forbidden, and unexpected errors.
- [ ] Implement the shared error JSON contract from `docs/Backend_Project_Design.md`.
- [ ] Add bearer-auth documentation and examples to OpenAPI.
- [ ] Verify `/v3/api-docs` and `/swagger-ui.html` load in the local application.
- [ ] Commit with `feat: document and standardize API errors`.

### Task 7: Build the React Dashboard

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/auth/`
- Create: `frontend/src/applications/`
- Create: `frontend/src/interviews/`
- Create: `frontend/src/components/`

- [ ] Scaffold React with TypeScript and configure the backend base URL from environment variables.
- [ ] Write component tests for login, application form validation, filter changes, expired-session handling, and API error display.
- [ ] Implement login, dashboard, application table, status update, interview form, and reminder views.
- [ ] Run `npm test -- --run` and `npm run build`; expect both to exit 0.
- [ ] Commit with `feat: add internship tracker dashboard`.

## Week 3: Integration, Containers, and CI/CD

### Task 8: Add Testcontainers Integration Tests

**Files:**
- Create: `backend/src/test/java/com/example/tracker/support/MySqlIntegrationTest.java`
- Create: `backend/src/test/java/com/example/tracker/ApplicationJourneyTest.java`

- [ ] Start MySQL 8 through Testcontainers and apply all Flyway migrations.
- [ ] Test register, login, create company, create opportunity, create application, transition status, and schedule interview as one workflow.
- [ ] Verify database constraints and owner isolation with real MySQL queries.
- [ ] Run `./mvnw verify`; expect zero failures.
- [ ] Commit with `test: cover end-to-end application journey`.

### Task 9: Containerize the Full Stack

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`
- Create: `.env.example`

- [ ] Build a multi-stage Spring Boot image and a production frontend image.
- [ ] Configure Compose services for MySQL, backend, and frontend with health checks.
- [ ] Run `docker compose up --build`; expect all services healthy and the frontend able to complete the smoke workflow.
- [ ] Commit with `build: containerize internship tracker`.

### Task 10: Add GitHub Actions CI/CD

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/deploy.yml`

- [ ] Configure CI jobs for backend tests, frontend tests/build, and Docker image build.
- [ ] Publish the backend image to GitHub Container Registry only after tests pass on `main`.
- [ ] Trigger the selected hosting provider deployment using repository secrets.
- [ ] Add a post-deployment request to `/actuator/health` and fail deployment when health is not `UP`.
- [ ] Verify the workflow on a pull request and a merge to `main`.
- [ ] Commit with `ci: test build and deploy full stack`.

## Week 4: Performance, Observability, and Portfolio Evidence

### Task 11: Add Actuator and Structured Request Logs

**Files:**
- Create: `backend/src/main/java/com/example/tracker/common/logging/RequestLoggingFilter.java`
- Modify: `backend/src/main/resources/application.yml`
- Create: `backend/src/test/java/com/example/tracker/common/logging/RequestLoggingFilterTest.java`

- [ ] Write tests proving request logs contain request ID, method, path, status, and duration but not authorization headers.
- [ ] Enable health and metrics endpoints while restricting sensitive Actuator endpoints.
- [ ] Verify production logs during the complete application workflow.
- [ ] Commit with `feat: add backend health and request telemetry`.

### Task 12: Create and Run JMeter Load Tests

**Files:**
- Create: `load-tests/internship-tracker.jmx`
- Create: `load-tests/datasets/users.csv.example`
- Create: `load-tests/README.md`

- [ ] Record login, list, create, status update, and dashboard API requests in one reusable test plan.
- [ ] Externalize base URL, user count, ramp-up, duration, and credentials as JMeter properties.
- [ ] Run smoke, 20-user baseline, and 50-user load stages.
- [ ] Export HTML reports and record throughput, median, P95 latency, error rate, CPU, memory, and connection-pool behavior.
- [ ] Fix functional errors found under load, rerun the same saved plan, and retain both before and after reports.
- [ ] Commit with `perf: add reproducible API load tests`.

### Task 13: Publish and Update the Resume

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/performance-results.md`
- Modify: `E:/my-CV/tools/build_backend_resumes.py`

- [ ] Document local setup, API usage, architecture, security model, tests, deployment URLs, and limitations.
- [ ] Add GitHub Actions badges, Swagger URL, live demo URL, and JMeter methodology.
- [ ] Record a 90-second demo covering login, application workflow, filters, interview scheduling, and CI evidence.
- [ ] Replace Java resume coursework-only positioning with measured project bullets.
- [ ] Regenerate DOCX/PDF and verify both remain one page.
- [ ] Commit with `docs: publish internship tracker portfolio evidence`.

