#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

BASE_TEST_TYPES: tuple[str, ...] = ("smoke", "unit", "integration", "e2e")
ALL_TEST_TYPES: tuple[str, ...] = BASE_TEST_TYPES + ("other",)
TYPE_LABELS: dict[str, str] = {
    "smoke": "smoke",
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
    "other": "other",
}

IGNORED_DIR_NAMES: set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".git",
}


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    path: Path


@dataclass
class TypeStats:
    total: int = 0
    ok: int = 0
    fail: int = 0
    skip: int = 0
    files: set[str] = field(default_factory=set)


@dataclass
class ServiceResult:
    service: ServiceConfig
    stats: dict[str, TypeStats]
    discovered_files_count: int = 0
    exit_code: int = 0
    message: str = ""


REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICES: tuple[ServiceConfig, ...] = (
    ServiceConfig(
        name="free-ai-selector-data-postgres-api",
        path=REPO_ROOT / "services" / "free-ai-selector-data-postgres-api",
    ),
    ServiceConfig(
        name="free-ai-selector-business-api",
        path=REPO_ROOT / "services" / "free-ai-selector-business-api",
    ),
    ServiceConfig(
        name="free-ai-selector-telegram-bot",
        path=REPO_ROOT / "services" / "free-ai-selector-telegram-bot",
    ),
    ServiceConfig(
        name="free-ai-selector-health-worker",
        path=REPO_ROOT / "services" / "free-ai-selector-health-worker",
    ),
)

# Ждем, пока контейнеры перейдут в ожидаемое состояние перед запуском тестов.
WAIT_TARGETS: dict[str, str] = {
    "free-ai-selector-postgres": "healthy",
    "free-ai-selector-data-postgres-api": "healthy",
    "free-ai-selector-business-api": "healthy",
    "free-ai-selector-telegram-bot": "running",
    "free-ai-selector-health-worker": "running",
}


def run_command(command: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=capture_output,
        check=False,
    )


def compose_command() -> list[str]:
    raw_command = os.getenv("COMPOSE_CMD", "docker compose").strip()
    parsed = shlex.split(raw_command)
    if not parsed:
        raise ValueError("COMPOSE_CMD пустой.")
    return parsed


def is_path_ignored(relative_path: Path) -> bool:
    for part in relative_path.parts[:-1]:
        if part in IGNORED_DIR_NAMES or part.startswith("."):
            return True
    return False


def discover_test_files(service_path: Path) -> list[Path]:
    test_files: list[Path] = []
    for file_path in service_path.rglob("*.py"):
        relative_path = file_path.relative_to(service_path)
        if is_path_ignored(relative_path):
            continue
        file_name = file_path.name
        if file_name.startswith("test_") or file_name.endswith("_test.py"):
            test_files.append(relative_path)
    return sorted(test_files, key=lambda item: item.as_posix())


def classify_test_type(test_path: str) -> str:
    normalized = f"/{test_path.lower().replace('\\', '/').strip('/')}/"
    if "/tests/smoke/" in normalized:
        return "smoke"
    if "/tests/unit/" in normalized:
        return "unit"
    if "/tests/integration/" in normalized:
        return "integration"
    if "/tests/e2e/" in normalized:
        return "e2e"
    return "other"


def initial_stats() -> dict[str, TypeStats]:
    return {test_type: TypeStats() for test_type in ALL_TEST_TYPES}


def inspect_container_status(container_name: str) -> str:
    result = run_command(
        [
            "docker",
            "inspect",
            "--format",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
            container_name,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip().lower()


def is_status_ready(current_status: str, expected_status: str) -> bool:
    if expected_status == "healthy":
        return current_status == "healthy"
    return current_status in {"running", "healthy"}


def wait_for_containers(timeout_seconds: int = 240) -> bool:
    deadline = time.time() + timeout_seconds
    remaining = dict(WAIT_TARGETS)

    while time.time() < deadline:
        ready_now: list[str] = []
        for container_name, expected_status in remaining.items():
            current_status = inspect_container_status(container_name)
            if is_status_ready(current_status, expected_status):
                ready_now.append(container_name)
        for container_name in ready_now:
            remaining.pop(container_name, None)
        if not remaining:
            return True
        time.sleep(2)
    return False


def module_path_map(test_files: list[Path]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for file_path in test_files:
        module_name = file_path.with_suffix("").as_posix().replace("/", ".")
        mapping[module_name] = file_path.as_posix()
    return mapping


def infer_file_from_classname(classname: str, modules: dict[str, str]) -> str:
    if not classname:
        return ""
    parts = classname.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        file_path = modules.get(candidate)
        if file_path:
            return file_path
    return ""


def parse_junit_report(report_path: Path, modules: dict[str, str]) -> list[tuple[str, str]]:
    if not report_path.exists():
        return []

    root = ET.parse(report_path).getroot()
    parsed_cases: list[tuple[str, str]] = []

    for testcase in root.iter("testcase"):
        file_path = testcase.attrib.get("file", "").strip().replace("\\", "/")
        classname = testcase.attrib.get("classname", "").strip()
        if not file_path:
            file_path = infer_file_from_classname(classname, modules)

        status = "ok"
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            status = "fail"
        elif testcase.find("skipped") is not None:
            status = "skip"

        parsed_cases.append((file_path, status))

    return parsed_cases


def run_tests_for_service(compose: list[str], service: ServiceConfig) -> ServiceResult:
    stats = initial_stats()
    test_files = discover_test_files(service.path)
    result = ServiceResult(
        service=service,
        stats=stats,
        discovered_files_count=len(test_files),
    )

    for file_path in test_files:
        stats[classify_test_type(file_path.as_posix())].files.add(file_path.as_posix())

    if not test_files:
        result.message = "Тестовые файлы не найдены."
        return result

    report_dir = service.path / ".test-report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "junit.xml"
    if report_path.exists():
        report_path.unlink()

    print(f"\n=== {service.name}: запуск тестов ({len(test_files)} файлов) ===")
    pytest_command = compose + [
        "exec",
        "-T",
        service.name,
        "pytest",
        "-o",
        "addopts=--verbose --strict-markers",
        "--junitxml=/app/.test-report/junit.xml",
        *[file_path.as_posix() for file_path in test_files],
    ]
    pytest_result = run_command(pytest_command)
    result.exit_code = pytest_result.returncode

    modules = module_path_map(test_files)
    parsed_cases = parse_junit_report(report_path, modules)
    for file_path, status in parsed_cases:
        test_type = classify_test_type(file_path) if file_path else "other"
        type_stats = stats[test_type]
        type_stats.total += 1
        if status == "ok":
            type_stats.ok += 1
        elif status == "fail":
            type_stats.fail += 1
        else:
            type_stats.skip += 1
        if file_path:
            type_stats.files.add(file_path)

    # Удаляем временные артефакты отчета, чтобы не засорять рабочее дерево.
    shutil.rmtree(report_dir, ignore_errors=True)

    if result.exit_code == 5 and not parsed_cases:
        # pytest code 5 = no tests collected; для сервиса без кейсов не считаем это ошибкой.
        result.exit_code = 0

    if result.exit_code == 0:
        result.message = "OK"
    else:
        result.message = f"pytest завершился с кодом {result.exit_code}"

    return result


def table_rows(results: list[ServiceResult]) -> tuple[list[tuple[str, str, int, int, int, int, int]], tuple[int, int, int, int, int]]:
    rows: list[tuple[str, str, int, int, int, int, int]] = []
    total_tests = 0
    total_ok = 0
    total_fail = 0
    total_skip = 0
    total_files = 0

    for service_result in results:
        for test_type in BASE_TEST_TYPES:
            stats = service_result.stats[test_type]
            row = (
                service_result.service.name,
                TYPE_LABELS[test_type],
                stats.total,
                stats.ok,
                stats.fail,
                stats.skip,
                len(stats.files),
            )
            rows.append(row)
            total_tests += stats.total
            total_ok += stats.ok
            total_fail += stats.fail
            total_skip += stats.skip
            total_files += len(stats.files)

        other_stats = service_result.stats["other"]
        if other_stats.total > 0 or len(other_stats.files) > 0:
            row = (
                service_result.service.name,
                TYPE_LABELS["other"],
                other_stats.total,
                other_stats.ok,
                other_stats.fail,
                other_stats.skip,
                len(other_stats.files),
            )
            rows.append(row)
            total_tests += other_stats.total
            total_ok += other_stats.ok
            total_fail += other_stats.fail
            total_skip += other_stats.skip
            total_files += len(other_stats.files)

    totals = (total_tests, total_ok, total_fail, total_skip, total_files)
    return rows, totals


def format_report(results: list[ServiceResult]) -> str:
    headers = ("Микросервис", "Тип", "Тестов", "OK", "FAIL", "SKIP", "Файлов")
    rows, totals = table_rows(results)

    widths = [len(header) for header in headers]
    for row in rows:
        widths[0] = max(widths[0], len(row[0]))
        widths[1] = max(widths[1], len(row[1]))
        widths[2] = max(widths[2], len(str(row[2])))
        widths[3] = max(widths[3], len(str(row[3])))
        widths[4] = max(widths[4], len(str(row[4])))
        widths[5] = max(widths[5], len(str(row[5])))
        widths[6] = max(widths[6], len(str(row[6])))

    def format_row(values: tuple[str, str, str, str, str, str, str]) -> str:
        return (
            f"{values[0]:<{widths[0]}} | "
            f"{values[1]:<{widths[1]}} | "
            f"{values[2]:>{widths[2]}} | "
            f"{values[3]:>{widths[3]}} | "
            f"{values[4]:>{widths[4]}} | "
            f"{values[5]:>{widths[5]}} | "
            f"{values[6]:>{widths[6]}}"
        )

    report_lines: list[str] = []
    report_lines.append("")
    report_lines.append("========================================")
    report_lines.append("Отчет о тестировании в контейнерах")
    report_lines.append("========================================")
    report_lines.append(
        format_row(
            (
                headers[0],
                headers[1],
                headers[2],
                headers[3],
                headers[4],
                headers[5],
                headers[6],
            )
        )
    )
    report_lines.append("-" * (sum(widths) + 18))

    for row in rows:
        report_lines.append(
            format_row(
                (
                    row[0],
                    row[1],
                    str(row[2]),
                    str(row[3]),
                    str(row[4]),
                    str(row[5]),
                    str(row[6]),
                )
            )
        )

    report_lines.append("-" * (sum(widths) + 18))
    report_lines.append(
        format_row(
            (
                "ИТОГО",
                "all",
                str(totals[0]),
                str(totals[1]),
                str(totals[2]),
                str(totals[3]),
                str(totals[4]),
            )
        )
    )
    report_lines.append("")

    for service_result in results:
        report_lines.append(
            f"{service_result.service.name}: {service_result.message} "
            f"(файлов: {service_result.discovered_files_count})"
        )

    return "\n".join(report_lines)


def main() -> int:
    compose = compose_command()
    results: list[ServiceResult] = []
    overall_exit_code = 0

    print("[setup] Поднимаю контейнеры и пересобираю образы...")
    up_result = run_command(compose + ["up", "-d", "--build"])
    if up_result.returncode != 0:
        overall_exit_code = up_result.returncode or 1

    if overall_exit_code == 0:
        print("[setup] Ожидаю готовность контейнеров...")
        if not wait_for_containers():
            print("[warning] Не дождались healthy/running статусов до таймаута.", file=sys.stderr)
            overall_exit_code = 1

    if overall_exit_code == 0:
        for service in SERVICES:
            service_result = run_tests_for_service(compose, service)
            results.append(service_result)
            if service_result.exit_code != 0:
                overall_exit_code = 1
    else:
        for service in SERVICES:
            results.append(
                ServiceResult(
                    service=service,
                    stats=initial_stats(),
                    message="Тесты не запускались из-за ошибки setup.",
                )
            )

    print("\n[teardown] Останавливаю контейнеры...")
    down_result = run_command(compose + ["down"])
    if down_result.returncode != 0:
        print("[warning] Не удалось корректно остановить контейнеры.", file=sys.stderr)
        overall_exit_code = 1

    print(format_report(results))
    return overall_exit_code


if __name__ == "__main__":
    sys.exit(main())
