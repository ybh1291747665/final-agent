# Internship Application Tracker - Backend Project Design

## 1. Purpose

Build a production-style portfolio project that demonstrates traditional backend engineering skills for Singapore internship applications. The application helps students track internship opportunities, applications, interviews, reminders, and status changes.

The project must prove backend competence through implemented behavior, automated tests, deployment, CI/CD, and measured load-test results. Technologies that appear only in coursework must remain labeled as coursework until this project is complete.

## 2. Scope

### In Scope

- User registration, login, password hashing, and JWT authentication.
- User-owned companies, job opportunities, applications, interviews, and reminders.
- Application status workflow and immutable status history.
- Pagination, filtering, sorting, and keyword search.
- Validation and consistent error responses.
- OpenAPI documentation.
- React dashboard consuming REST APIs.
- MySQL persistence and schema migrations.
- Unit, integration, repository, security, and API tests.
- Docker Compose local environment.
- GitHub Actions CI/CD.
- Public deployment and health monitoring.
- JMeter load tests with recorded throughput, P95 latency, and error rate.

### Out of Scope for Version 1

- Multi-tenant organizations.
- Social login.
- Email delivery infrastructure.
- Native mobile applications.
- Microservices, Kafka, Kubernetes, and distributed tracing.
- AI-based job matching.

## 3. Architecture

```text
React SPA (Vercel)
    |
    | HTTPS / JSON
    v
Spring Boot REST API (Render or Railway)
    |-- Spring Security + JWT
    |-- User and Authentication
    |-- Company and Job Opportunity
    |-- Application and Status History
    |-- Interview and Reminder
    |-- Search, Pagination, Validation
    |-- OpenAPI + Actuator
    v
MySQL (managed database)

Engineering pipeline:
GitHub -> GitHub Actions -> Test -> Build -> Docker Image -> Deploy
                                      |
                                      -> JMeter test environment
```

Use a modular monolith. Each feature owns its controller, DTOs, service, repository, entities, mapper, and tests. Keep cross-cutting security, error handling, configuration, and audit behavior in shared packages.

## 4. Repository Layout

```text
internship-tracker/
|-- backend/
|   |-- src/main/java/com/example/tracker/
|   |   |-- auth/
|   |   |-- user/
|   |   |-- company/
|   |   |-- opportunity/
|   |   |-- application/
|   |   |-- interview/
|   |   |-- reminder/
|   |   |-- common/error/
|   |   |-- common/security/
|   |   `-- config/
|   |-- src/main/resources/
|   |   |-- db/migration/
|   |   |-- application.yml
|   |   `-- application-test.yml
|   `-- src/test/java/com/example/tracker/
|-- frontend/
|   `-- src/
|       |-- api/
|       |-- auth/
|       |-- applications/
|       |-- interviews/
|       `-- components/
|-- load-tests/
|   |-- internship-tracker.jmx
|   `-- datasets/
|-- docker-compose.yml
|-- .github/workflows/ci.yml
`-- README.md
```

## 5. Domain Model

### User

- `id`
- `email` unique
- `passwordHash`
- `displayName`
- `role`: `USER` or `ADMIN`
- `createdAt`, `updatedAt`

### Company

- `id`
- `ownerId`
- `name`
- `website`
- `location`
- `notes`

### Opportunity

- `id`
- `ownerId`
- `companyId`
- `title`
- `jobUrl`
- `source`
- `location`
- `employmentType`
- `deadline`
- `description`

### Application

- `id`
- `ownerId`
- `opportunityId`
- `status`
- `appliedAt`
- `priority`
- `resumeVersion`
- `coverLetterVersion`
- `notes`
- `createdAt`, `updatedAt`

Allowed statuses:

```text
SAVED -> APPLIED -> ONLINE_ASSESSMENT -> INTERVIEW -> OFFER
                                             |          |
                                             v          v
                                          REJECTED   WITHDRAWN
```

Every transition creates an `ApplicationStatusHistory` row with old status, new status, timestamp, and optional note.

### Interview

- `id`
- `applicationId`
- `type`
- `scheduledAt`
- `timeZone`
- `locationOrMeetingUrl`
- `interviewer`
- `notes`
- `result`

### Reminder

- `id`
- `applicationId`
- `remindAt`
- `message`
- `completed`

## 6. REST API

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh

GET    /api/v1/companies
POST   /api/v1/companies
GET    /api/v1/companies/{id}
PUT    /api/v1/companies/{id}
DELETE /api/v1/companies/{id}

GET    /api/v1/opportunities
POST   /api/v1/opportunities
GET    /api/v1/opportunities/{id}
PUT    /api/v1/opportunities/{id}
DELETE /api/v1/opportunities/{id}

GET    /api/v1/applications
POST   /api/v1/applications
GET    /api/v1/applications/{id}
PUT    /api/v1/applications/{id}
PATCH  /api/v1/applications/{id}/status
DELETE /api/v1/applications/{id}
GET    /api/v1/applications/{id}/history

GET    /api/v1/applications/{id}/interviews
POST   /api/v1/applications/{id}/interviews
PUT    /api/v1/interviews/{id}
DELETE /api/v1/interviews/{id}

GET    /api/v1/reminders
POST   /api/v1/applications/{id}/reminders
PATCH  /api/v1/reminders/{id}/complete
DELETE /api/v1/reminders/{id}

GET    /actuator/health
GET    /v3/api-docs
GET    /swagger-ui.html
```

List endpoints support `page`, `size`, `sort`, `status`, `companyId`, `keyword`, `from`, and `to` where appropriate.

## 7. Security

- Hash passwords with BCrypt.
- Issue short-lived access tokens and longer-lived refresh tokens.
- Store refresh tokens as hashed records so they can be revoked.
- Derive the current user from the JWT; never accept `ownerId` from client payloads.
- Scope every repository query by current user.
- Return HTTP 401 for unauthenticated requests, 403 for forbidden ownership access, and 404 where revealing resource existence would leak data.
- Configure exact production CORS origins.
- Keep secrets in environment variables and GitHub repository secrets.

## 8. Error Contract

All errors use one shape:

```json
{
  "timestamp": "2026-06-13T10:00:00Z",
  "status": 400,
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "path": "/api/v1/applications",
  "fieldErrors": {
    "opportunityId": "must not be null"
  },
  "traceId": "b547..."
}
```

Use `@RestControllerAdvice` for validation, domain conflicts, authentication failures, missing resources, and unexpected errors.

## 9. Testing Strategy

- JUnit 5 for domain and service tests.
- Mockito only for true external boundaries.
- `@DataJpaTest` with Testcontainers MySQL for repository queries.
- `@SpringBootTest` and MockMvc for authentication and API workflows.
- Security tests for missing, invalid, expired, and wrong-owner tokens.
- Frontend component tests for authentication, filters, forms, and error states.
- One end-to-end smoke test covering register, login, create application, change status, and schedule interview.

Minimum release gate:

- All tests pass in CI.
- No application endpoint can access another user's records.
- OpenAPI describes all public endpoints.
- Database migrations apply to an empty MySQL instance.

## 10. Docker and CI/CD

Local `docker-compose.yml` runs:

- MySQL with a health check.
- Spring Boot API waiting for a healthy database.
- Optional frontend container for full-stack local testing.

GitHub Actions stages:

1. Backend formatting and compilation.
2. Backend tests with Testcontainers.
3. Frontend lint, tests, and build.
4. Docker image build.
5. Push image to GitHub Container Registry on `main`.
6. Trigger Render/Railway deployment after all checks pass.
7. Run a health-check smoke test against the deployed API.

## 11. Performance Testing

Use JMeter only after functional correctness is stable.

Scenarios:

- Login and token acquisition.
- Paginated application listing with filters.
- Create application.
- Update application status.
- Dashboard summary query.

Test stages:

- Smoke: 1 user for 1 minute.
- Baseline: 20 concurrent users for 5 minutes.
- Load: 50 concurrent users for 10 minutes.

Record:

- Requests per second.
- Median and P95 response latency.
- Error rate.
- CPU and memory during the run.
- Database connection-pool saturation.

Do not place performance numbers on the resume until they are reproduced from a saved `.jmx` file and exported report.

## 12. Observability

- Spring Boot Actuator health and metrics endpoints.
- Structured logs containing request ID, user ID where appropriate, method, path, status, and duration.
- Never log passwords, access tokens, refresh tokens, or full request bodies containing sensitive data.
- Add Prometheus/Grafana only after the core project, CI/CD, and load tests are complete.

## 13. Deployment

- React: Vercel.
- Spring Boot container: Render or Railway.
- MySQL: managed database on the selected backend platform.
- Production profile reads all credentials and CORS origins from environment variables.
- Flyway runs migrations during application startup.

## 14. Resume Evidence Gate

Before listing this as a project, the repository must contain:

- Public GitHub source.
- Live frontend and API health URL.
- Swagger/OpenAPI URL.
- Automated-test results in GitHub Actions.
- Docker Compose setup.
- Saved JMeter plan and exported summary.
- README architecture diagram and setup instructions.

Only then may the Java resume replace `Coursework Exposure` with a core project entry.

