#!/usr/bin/env python3
"""
Бенчмарк AI-провайдеров Free AI Selector.

Тестирует каждый доступный провайдер на 3 типах промптов × 2 формата.
Запускается внутри контейнера business-api:
  docker compose exec free-ai-selector-business-api python3 /app/scripts/provider_benchmark.py
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional

# Добавляем путь к приложению
sys.path.insert(0, "/app")

from app.infrastructure.ai_providers.registry import PROVIDER_CLASSES


# =============================================================================
# Промпты
# =============================================================================

PROMPT_SHORT = "What is 2+2? Answer in one word."

# ~1000 токенов (~4000 символов)
PROMPT_MEDIUM = """You are a senior software engineer conducting a comprehensive code review. Please analyze the following scenario and provide detailed feedback.

A development team has built a REST API using Python FastAPI framework. The API handles user authentication, data processing, and real-time notifications. The codebase has grown to approximately 50,000 lines of code across 200 files.

Current architecture issues that have been identified:
1. Authentication middleware is tightly coupled with business logic, making it difficult to test individual components in isolation.
2. Database queries are scattered throughout the codebase instead of being centralized in a repository layer, leading to code duplication and inconsistent error handling.
3. The notification system uses synchronous HTTP calls to external services, causing request latency spikes during peak hours.
4. Configuration management relies on hardcoded values mixed with environment variables, making deployment across different environments error-prone.
5. Error handling follows no consistent pattern — some endpoints return detailed error messages while others return generic 500 responses.
6. The test suite covers only 35% of the codebase, with most tests being integration tests that require a running database.
7. API versioning was not implemented from the start, and now breaking changes affect all consumers simultaneously.
8. Logging is inconsistent — some modules use print statements, others use the logging module with different formatters and levels.
9. Background tasks for data processing run in the same process as the API server, competing for CPU and memory resources.
10. The codebase lacks type annotations in approximately 60% of functions, making static analysis tools ineffective.

For each issue, please provide:
- A severity rating (Critical, High, Medium, Low)
- Root cause analysis explaining why this became a problem
- Specific refactoring steps with code examples where appropriate
- Estimated effort to fix (in developer-days)
- Potential risks of the refactoring
- How to prevent this issue from recurring

Additionally, propose a prioritized roadmap for addressing all issues, considering dependencies between them and the team's capacity of 4 developers. Include milestones and success criteria for each phase.

Finally, recommend specific tools, libraries, and practices that would help maintain code quality going forward, including CI/CD pipeline improvements, pre-commit hooks, and monitoring solutions."""

# ~7500 токенов (~30000 символов)
PROMPT_LONG = """You are a distinguished software architect with 25 years of experience across distributed systems, cloud-native applications, and enterprise architecture. You have been hired as a consultant to perform a thorough architectural review and produce a comprehensive transformation plan.

## Company Context

TechFlow Inc. is a mid-size SaaS company (Series C, $45M ARR) that provides a project management and collaboration platform used by 2,500 enterprise customers and approximately 180,000 daily active users worldwide. The engineering team consists of 65 developers organized into 8 cross-functional squads, plus a platform team of 12 engineers.

## Current Technical Landscape

### Monolithic Application (Legacy Core)
The original application was built 7 years ago as a Ruby on Rails monolith. It has grown to approximately 450,000 lines of Ruby code with 2,800 database tables in a single PostgreSQL instance (currently 4.2TB). The monolith handles:

1. **User Management & Authentication**: Custom session-based auth with LDAP/SAML integration for enterprise customers. Password hashing uses bcrypt with work factor 12. Session tokens stored in Redis with 24-hour TTL. Role-based access control with 47 distinct permission types across organization, workspace, project, and task levels.

2. **Project Management Core**: Hierarchical project structure (Organization → Workspace → Project → Board → List → Task → Subtask) with complex permission inheritance. Tasks support 23 custom field types including computed fields, dependencies (finish-to-start, start-to-start, finish-to-finish, start-to-finish), and automated workflows triggered by state transitions.

3. **Real-time Collaboration**: WebSocket connections managed by Action Cable, supporting concurrent editing of task descriptions (basic operational transform), live cursor tracking, presence indicators, and instant notifications. Currently handles approximately 45,000 concurrent WebSocket connections during peak hours.

4. **File Management**: File uploads stored on AWS S3 with metadata in PostgreSQL. Supports versioning, inline preview generation (PDF, images, Office documents), and virus scanning via ClamAV. Current storage: 28TB across 15 million files. Thumbnail generation and document preview run synchronously during upload, causing timeout issues for large files.

5. **Search Engine**: Elasticsearch cluster (3 nodes, version 7.10) indexing tasks, projects, comments, and files. The search index is rebuilt nightly via a 6-hour batch job because incremental updates have reliability issues. Users frequently report stale search results, especially for recently created or modified items.

6. **Reporting & Analytics**: Custom reporting engine that generates complex aggregation queries directly against the primary PostgreSQL database. Report generation for large organizations (10,000+ tasks) can take 5-15 minutes and has been observed causing database lock contention that affects the entire application.

7. **Integration Hub**: 34 third-party integrations (Slack, Jira, GitHub, GitLab, Figma, Google Drive, Microsoft Teams, Salesforce, etc.) implemented as Rails concerns mixed into various models. Each integration has its own webhook handler, OAuth flow, and data sync logic scattered across the codebase.

8. **Email System**: Transactional emails (registration, password reset, task assignments, mentions) and digest emails (daily/weekly summaries) processed through Sidekiq background jobs. The email templating system has 87 templates with significant HTML/CSS duplication. Delivery rate monitoring shows 94.2% inbox placement.

9. **Billing & Subscription**: Stripe integration handling 2,500 active subscriptions across 4 plan tiers. Usage-based billing for API calls and storage overage. Invoice generation, proration calculations, and dunning management implemented in a 15,000-line billing module with complex state machine logic.

10. **API Layer**: REST API (v2) serving mobile apps and third-party developers. Approximately 340 endpoints with inconsistent authentication (mix of API keys, OAuth2, and session cookies). API documentation is auto-generated but frequently out of date. Rate limiting implemented at the nginx level with fixed windows per IP.

### Microservices (Newer Components)
Over the past 2 years, the team has extracted some functionality into microservices:

1. **Notification Service** (Node.js/Express): Handles push notifications, in-app notifications, and notification preferences. Uses MongoDB for notification storage and Firebase Cloud Messaging for mobile push. Deployed on Kubernetes but still reads user preferences from the monolith's database via a shared connection.

2. **Analytics Service** (Python/FastAPI): Collects event data via Kafka, processes it through Apache Spark jobs, and stores aggregated metrics in ClickHouse. Provides dashboard data for customer-facing analytics. Currently processes approximately 50 million events per day with a 15-minute processing lag.

3. **Media Processing Service** (Go): Handles image resizing, video transcoding, and document preview generation. Uses worker pools with RabbitMQ for job queuing. Processes approximately 200,000 media items daily. This service was the most successful extraction and operates independently.

### Infrastructure
- **Hosting**: AWS us-east-1 (primary), with disaster recovery setup in us-west-2 that has never been tested
- **Compute**: Mix of EC2 instances (monolith: 8x r5.4xlarge) and EKS cluster (microservices: 24 nodes)
- **Database**: RDS PostgreSQL 13.8 (primary: db.r5.8xlarge, 1 read replica), Redis Cluster (6 nodes), MongoDB Atlas (M40), ClickHouse Cloud
- **Message Queue**: Self-managed RabbitMQ cluster (3 nodes), Amazon MSK (Kafka) for analytics pipeline
- **CDN/Load Balancing**: CloudFront + ALB, nginx as reverse proxy
- **CI/CD**: Jenkins (monolith) with 45-minute build times, GitHub Actions (microservices) with 8-minute builds
- **Monitoring**: Datadog APM + logs, PagerDuty for alerting, custom health check dashboard
- **Monthly AWS bill**: $127,000 (growing 12% quarter-over-quarter)

### Known Pain Points (from engineering survey, 89% response rate)

1. **Deployment velocity**: The monolith deploys once per week (Wednesday 2pm ET) with a manual QA gate. Hotfixes require VP approval and a separate deployment process. Average lead time from merge to production: 4.3 days.

2. **Incident frequency**: Average of 3.2 SEV-2 incidents per month, with mean time to resolution of 2.4 hours. Top causes: database lock contention (28%), memory leaks in WebSocket handling (22%), third-party API failures cascading (19%), deployment-related issues (31%).

3. **Developer experience**: New developer onboarding takes 3-4 weeks to become productive. Local development environment setup requires 12 manual steps and frequently breaks after OS/dependency updates. Running the full test suite locally takes 47 minutes.

4. **Scaling challenges**: The monolith cannot scale horizontally because of in-memory session state and background job scheduling that assumes single-instance execution. During product launches (approximately monthly), the team manually scales vertically and provisions additional read replicas.

5. **Technical debt**: SonarQube reports 4,200 code smells, 340 bugs, and 89 security vulnerabilities. Test coverage is 41% overall (62% for core business logic, 18% for integrations). Approximately 30% of dependencies are more than 2 major versions behind.

6. **Data consistency**: Several race conditions in the task dependency engine cause phantom circular dependencies. The billing system occasionally double-charges due to webhook retry handling. Elasticsearch and PostgreSQL frequently have divergent data.

## Your Deliverables

Produce a comprehensive architectural transformation plan covering:

### Part 1: Strategic Assessment
- Current architecture maturity evaluation (use TOGAF ADM or similar framework)
- Risk register with probability and impact ratings
- Stakeholder impact analysis

### Part 2: Target Architecture
- Domain-driven design analysis: identify bounded contexts, aggregates, and context mapping
- Service decomposition plan with clear service boundaries
- Data architecture: database-per-service strategy, event sourcing where appropriate, CQRS patterns
- Integration architecture: synchronous vs asynchronous communication patterns, API gateway design
- Security architecture: zero-trust principles, service mesh, secrets management

### Part 3: Migration Strategy
- Strangler fig pattern application plan with specific seams to cut
- Phase-by-phase migration roadmap (6 phases over 18 months)
- Database decomposition strategy with data synchronization during transition
- Feature flag strategy for gradual rollouts
- Rollback procedures for each phase

### Part 4: Infrastructure & Operations
- Kubernetes architecture with namespace strategy, resource quotas, and auto-scaling policies
- Observability stack: distributed tracing, metrics, logging, SLO/SLI definitions
- CI/CD pipeline redesign targeting 15-minute deployments
- Disaster recovery and business continuity improvements
- Cost optimization opportunities (target: 25% reduction in 12 months)

### Part 5: Team & Process
- Team topology recommendations (stream-aligned, platform, enabling, complicated-subsystem)
- RFC and ADR processes for architectural decisions
- Migration team staffing and skill gap analysis
- Success metrics and KPIs for the transformation

### Part 6: Risk Mitigation
- Identify top 10 risks with mitigation strategies
- Define circuit breakers and fallback mechanisms
- Create a decision framework for build vs buy vs open-source

Format your response with clear headers, numbered lists, tables where appropriate, and specific technology recommendations with justification. Include rough effort estimates in person-months for each phase."""

PROMPTS = {
    "SHORT": PROMPT_SHORT,
    "MEDIUM": PROMPT_MEDIUM,
    "LONG": PROMPT_LONG,
}

# Токены max_tokens для ответа: SHORT -> мало, MEDIUM -> средне, LONG -> много
MAX_TOKENS_MAP = {
    "SHORT": 64,
    "MEDIUM": 1024,
    "LONG": 2048,
}


# =============================================================================
# Результат теста
# =============================================================================

@dataclass
class TestResult:
    provider: str
    prompt_type: str       # SHORT, MEDIUM, LONG
    response_format: str   # PLAIN, JSON
    status: str            # success, error, skipped
    response_time_sec: float
    response_length: int   # символы
    json_valid: Optional[bool]  # None для PLAIN
    error_message: str
    attempts: int
    response_preview: str  # первые 200 символов ответа


# =============================================================================
# Бенчмарк
# =============================================================================

async def test_provider(
    provider_name: str,
    prompt_type: str,
    prompt_text: str,
    use_json: bool,
    max_tokens: int,
) -> TestResult:
    """Тестирует один провайдер с одним промптом."""

    format_name = "JSON" if use_json else "PLAIN"

    # Получаем класс провайдера
    provider_class = PROVIDER_CLASSES.get(provider_name)
    if not provider_class:
        return TestResult(
            provider=provider_name, prompt_type=prompt_type,
            response_format=format_name, status="error",
            response_time_sec=0, response_length=0,
            json_valid=None, error_message=f"Provider class not found: {provider_name}",
            attempts=0, response_preview="",
        )

    # Проверяем JSON support
    supports_json = getattr(provider_class, "SUPPORTS_RESPONSE_FORMAT", False)
    if use_json and not supports_json:
        return TestResult(
            provider=provider_name, prompt_type=prompt_type,
            response_format=format_name, status="skipped",
            response_time_sec=0, response_length=0,
            json_valid=None,
            error_message=f"JSON response_format not supported by {provider_name}",
            attempts=0, response_preview="",
        )

    # Проверяем наличие API key
    api_key_env = getattr(provider_class, "API_KEY_ENV", "")
    api_key = os.getenv(api_key_env, "")
    if not api_key:
        return TestResult(
            provider=provider_name, prompt_type=prompt_type,
            response_format=format_name, status="skipped",
            response_time_sec=0, response_length=0,
            json_valid=None,
            error_message=f"API key not configured: {api_key_env}",
            attempts=0, response_preview="",
        )

    # Инициализация провайдера
    try:
        provider = provider_class()
    except Exception as e:
        return TestResult(
            provider=provider_name, prompt_type=prompt_type,
            response_format=format_name, status="error",
            response_time_sec=0, response_length=0,
            json_valid=None, error_message=f"Init failed: {e}",
            attempts=0, response_preview="",
        )

    # Формируем kwargs
    kwargs = {"max_tokens": max_tokens, "temperature": 0.7}

    if use_json:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["system_prompt"] = "You must respond with valid JSON only."

    # Вызываем generate
    start = time.monotonic()
    try:
        response_text = await provider.generate(prompt_text, **kwargs)
        elapsed = time.monotonic() - start

        # Проверяем JSON валидность
        json_valid = None
        if use_json:
            try:
                json.loads(response_text)
                json_valid = True
            except (json.JSONDecodeError, TypeError):
                json_valid = False

        return TestResult(
            provider=provider_name, prompt_type=prompt_type,
            response_format=format_name, status="success",
            response_time_sec=round(elapsed, 3),
            response_length=len(response_text),
            json_valid=json_valid,
            error_message="",
            attempts=1,
            response_preview=response_text[:200],
        )

    except Exception as e:
        elapsed = time.monotonic() - start
        err_str = str(e)
        # Извлекаем HTTP status code если есть
        status_code = ""
        if hasattr(e, "response") and hasattr(e.response, "status_code"):
            status_code = f" [HTTP {e.response.status_code}]"

        return TestResult(
            provider=provider_name, prompt_type=prompt_type,
            response_format=format_name, status="error",
            response_time_sec=round(elapsed, 3),
            response_length=0,
            json_valid=None,
            error_message=f"{err_str[:300]}{status_code}",
            attempts=1,
            response_preview="",
        )


async def run_benchmark():
    """Запуск полного бенчмарка."""

    providers = list(PROVIDER_CLASSES.keys())
    results: list[TestResult] = []

    print("=" * 80)
    print("PROVIDER BENCHMARK — Free AI Selector")
    print(f"Провайдеров: {len(providers)}")
    print(f"Промптов: {len(PROMPTS)} (SHORT / MEDIUM / LONG)")
    print(f"Форматов: 2 (PLAIN / JSON)")
    print("=" * 80)

    # Проверяем доступность API keys
    print("\n--- Проверка API keys ---")
    available_providers = []
    for name in providers:
        cls = PROVIDER_CLASSES[name]
        env_var = getattr(cls, "API_KEY_ENV", "")
        key = os.getenv(env_var, "")
        status = "OK" if key else "MISSING"
        print(f"  {name:15s} | {env_var:25s} | {status}")
        if key:
            available_providers.append(name)

    print(f"\nДоступно провайдеров: {len(available_providers)}/{len(providers)}")

    # Health checks
    print("\n--- Health Checks ---")
    for name in available_providers:
        try:
            provider = PROVIDER_CLASSES[name]()
            healthy = await provider.health_check()
            print(f"  {name:15s} | {'HEALTHY' if healthy else 'UNHEALTHY'}")
        except Exception as e:
            print(f"  {name:15s} | ERROR: {str(e)[:80]}")

    # Основные тесты
    total_tests = len(available_providers) * len(PROMPTS) * 2  # 2 формата
    test_num = 0

    print(f"\n--- Запуск {total_tests} тестов ---\n")

    for name in available_providers:
        for prompt_type, prompt_text in PROMPTS.items():
            for use_json in [False, True]:
                test_num += 1
                fmt = "JSON" if use_json else "PLAIN"
                max_tok = MAX_TOKENS_MAP[prompt_type]

                print(f"[{test_num:3d}/{total_tests}] {name:15s} | {prompt_type:6s} | {fmt:5s} ... ",
                      end="", flush=True)

                result = await test_provider(name, prompt_type, prompt_text, use_json, max_tok)
                results.append(result)

                if result.status == "success":
                    jv = ""
                    if result.json_valid is not None:
                        jv = f" json_valid={result.json_valid}"
                    print(f"OK  {result.response_time_sec:6.2f}s  {result.response_length:6d} chars{jv}")
                elif result.status == "skipped":
                    print(f"SKIP  ({result.error_message[:60]})")
                else:
                    print(f"ERR  {result.response_time_sec:6.2f}s  {result.error_message[:60]}")

                # Пауза между запросами (rate limit protection)
                await asyncio.sleep(2)

    # Сохранение результатов
    output_path = "/app/scripts/benchmark_results.json"
    results_dicts = [asdict(r) for r in results]
    with open(output_path, "w") as f:
        json.dump(results_dicts, f, indent=2, ensure_ascii=False)
    print(f"\nРезультаты сохранены в {output_path}")

    # Сводная таблица
    print("\n" + "=" * 120)
    print("СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print("=" * 120)
    print(f"{'Provider':15s} | {'Prompt':6s} | {'Fmt':5s} | {'Status':7s} | {'Time':>7s} | {'Chars':>7s} | {'JSON?':>5s} | Error/Preview")
    print("-" * 120)

    for r in results:
        jv = ""
        if r.json_valid is True:
            jv = "YES"
        elif r.json_valid is False:
            jv = "NO"

        info = r.error_message[:50] if r.status != "success" else r.response_preview[:50]
        time_str = f"{r.response_time_sec:.2f}s" if r.response_time_sec > 0 else "-"

        print(f"{r.provider:15s} | {r.prompt_type:6s} | {r.response_format:5s} | "
              f"{r.status:7s} | {time_str:>7s} | {r.response_length:>7d} | {jv:>5s} | {info}")

    # Статистика по провайдерам
    print("\n" + "=" * 100)
    print("СТАТИСТИКА ПО ПРОВАЙДЕРАМ")
    print("=" * 100)
    print(f"{'Provider':15s} | {'Tests':>5s} | {'OK':>3s} | {'Err':>3s} | {'Skip':>4s} | "
          f"{'Avg Time':>8s} | {'JSON OK':>7s} | {'JSON Fail':>9s}")
    print("-" * 100)

    for name in providers:
        prov_results = [r for r in results if r.provider == name]
        ok = [r for r in prov_results if r.status == "success"]
        err = [r for r in prov_results if r.status == "error"]
        skip = [r for r in prov_results if r.status == "skipped"]

        avg_time = sum(r.response_time_sec for r in ok) / len(ok) if ok else 0
        json_ok = sum(1 for r in ok if r.json_valid is True)
        json_fail = sum(1 for r in ok if r.json_valid is False)

        print(f"{name:15s} | {len(prov_results):5d} | {len(ok):3d} | {len(err):3d} | "
              f"{len(skip):4d} | {avg_time:7.2f}s | {json_ok:7d} | {json_fail:9d}")

    print("\n" + "=" * 100)
    print("СТАТИСТИКА ПО ТИПУ ПРОМПТА")
    print("=" * 100)
    print(f"{'Prompt':6s} | {'Fmt':5s} | {'Tests':>5s} | {'OK':>3s} | {'Avg Time':>8s} | {'Avg Chars':>9s}")
    print("-" * 60)

    for pt in ["SHORT", "MEDIUM", "LONG"]:
        for fmt in ["PLAIN", "JSON"]:
            pr = [r for r in results if r.prompt_type == pt and r.response_format == fmt and r.status == "success"]
            avg_t = sum(r.response_time_sec for r in pr) / len(pr) if pr else 0
            avg_c = sum(r.response_length for r in pr) / len(pr) if pr else 0
            total = len([r for r in results if r.prompt_type == pt and r.response_format == fmt])
            print(f"{pt:6s} | {fmt:5s} | {total:5d} | {len(pr):3d} | {avg_t:7.2f}s | {avg_c:9.0f}")

    print("\nБенчмарк завершён.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
