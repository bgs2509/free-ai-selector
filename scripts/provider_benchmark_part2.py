#!/usr/bin/env python3
"""
Бенчмарк часть 2 — оставшиеся провайдеры.
Таймаут 60с на запрос, без длинных пауз.
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional

sys.path.insert(0, "/app")

from app.infrastructure.ai_providers.registry import PROVIDER_CLASSES

# Промпты
PROMPT_SHORT = "What is 2+2? Answer in one word."

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

Provide a comprehensive transformation plan with:
1. Strategic assessment and risk register
2. Target architecture with DDD bounded contexts
3. Migration strategy using strangler fig pattern (6 phases, 18 months)
4. Infrastructure and observability redesign
5. Team topology recommendations
6. Top 10 risks with mitigation strategies

Format with clear headers, numbered lists, and tables."""

PROMPTS = {
    "SHORT": PROMPT_SHORT,
    "MEDIUM": PROMPT_MEDIUM,
    "LONG": PROMPT_LONG,
}

MAX_TOKENS_MAP = {"SHORT": 64, "MEDIUM": 1024, "LONG": 2048}

# Провайдеры для дотестирования
REMAINING_PROVIDERS = ["GitHubModels", "Fireworks", "Hyperbolic", "Novita", "Scaleway"]

# Тесты GitHubModels которые уже прошли: SHORT PLAIN, SHORT JSON, MEDIUM PLAIN, MEDIUM JSON
GITHUB_DONE = {("SHORT", False), ("SHORT", True), ("MEDIUM", False), ("MEDIUM", True)}


@dataclass
class TestResult:
    provider: str
    prompt_type: str
    response_format: str
    status: str
    response_time_sec: float
    response_length: int
    json_valid: Optional[bool]
    error_message: str
    attempts: int
    response_preview: str


async def test_provider(provider_name, prompt_type, prompt_text, use_json, max_tokens):
    format_name = "JSON" if use_json else "PLAIN"
    provider_class = PROVIDER_CLASSES.get(provider_name)
    if not provider_class:
        return TestResult(provider_name, prompt_type, format_name, "error", 0, 0, None, "Not found", 0, "")

    supports_json = getattr(provider_class, "SUPPORTS_RESPONSE_FORMAT", False)
    if use_json and not supports_json:
        return TestResult(provider_name, prompt_type, format_name, "skipped", 0, 0, None,
                          f"JSON not supported by {provider_name}", 0, "")

    api_key_env = getattr(provider_class, "API_KEY_ENV", "")
    if not os.getenv(api_key_env, ""):
        return TestResult(provider_name, prompt_type, format_name, "skipped", 0, 0, None,
                          f"No API key: {api_key_env}", 0, "")

    try:
        provider = provider_class()
    except Exception as e:
        return TestResult(provider_name, prompt_type, format_name, "error", 0, 0, None, f"Init: {e}", 0, "")

    kwargs = {"max_tokens": max_tokens, "temperature": 0.7}
    if use_json:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["system_prompt"] = "You must respond with valid JSON only."

    start = time.monotonic()
    try:
        response_text = await asyncio.wait_for(
            provider.generate(prompt_text, **kwargs),
            timeout=90.0
        )
        elapsed = time.monotonic() - start

        json_valid = None
        if use_json:
            try:
                json.loads(response_text)
                json_valid = True
            except (json.JSONDecodeError, TypeError):
                json_valid = False

        return TestResult(provider_name, prompt_type, format_name, "success",
                          round(elapsed, 3), len(response_text), json_valid, "", 1,
                          response_text[:200])

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        return TestResult(provider_name, prompt_type, format_name, "error",
                          round(elapsed, 3), 0, None, "TIMEOUT (90s)", 1, "")
    except Exception as e:
        elapsed = time.monotonic() - start
        status_code = ""
        if hasattr(e, "response") and hasattr(e.response, "status_code"):
            status_code = f" [HTTP {e.response.status_code}]"
        return TestResult(provider_name, prompt_type, format_name, "error",
                          round(elapsed, 3), 0, None, f"{str(e)[:300]}{status_code}", 1, "")


async def run():
    results = []
    test_num = 0

    for name in REMAINING_PROVIDERS:
        for prompt_type, prompt_text in PROMPTS.items():
            for use_json in [False, True]:
                # Пропускаем уже сделанные тесты GitHubModels
                if name == "GitHubModels" and (prompt_type, use_json) in GITHUB_DONE:
                    continue

                test_num += 1
                fmt = "JSON" if use_json else "PLAIN"
                max_tok = MAX_TOKENS_MAP[prompt_type]

                print(f"[{test_num:2d}] {name:15s} | {prompt_type:6s} | {fmt:5s} ... ",
                      end="", flush=True)

                result = await test_provider(name, prompt_type, prompt_text, use_json, max_tok)
                results.append(result)

                if result.status == "success":
                    jv = f" json_valid={result.json_valid}" if result.json_valid is not None else ""
                    print(f"OK  {result.response_time_sec:6.2f}s  {result.response_length:6d} chars{jv}")
                elif result.status == "skipped":
                    print(f"SKIP  ({result.error_message[:60]})")
                else:
                    print(f"ERR  {result.response_time_sec:6.2f}s  {result.error_message[:60]}")

                await asyncio.sleep(1)

    # Сохранение
    output_path = "/app/benchmark_results_part2.json"
    with open(output_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
    print(f"\nСохранено: {output_path}")

    # Таблица
    print("\n" + "=" * 110)
    print(f"{'Provider':15s} | {'Prompt':6s} | {'Fmt':5s} | {'Status':7s} | {'Time':>7s} | {'Chars':>7s} | {'JSON?':>5s} | Info")
    print("-" * 110)
    for r in results:
        jv = "YES" if r.json_valid is True else ("NO" if r.json_valid is False else "")
        info = r.error_message[:50] if r.status != "success" else r.response_preview[:50]
        t = f"{r.response_time_sec:.2f}s" if r.response_time_sec > 0 else "-"
        print(f"{r.provider:15s} | {r.prompt_type:6s} | {r.response_format:5s} | {r.status:7s} | {t:>7s} | {r.response_length:>7d} | {jv:>5s} | {info}")


if __name__ == "__main__":
    asyncio.run(run())
