#!/usr/bin/env python3
"""Repeatable single-node mixed-load benchmark without model execution."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai_agent_core import ResourceScheduler, ResourceSchedulerError


POOLS = {"control":"control", "text":"accelerator", "audit":"accelerator", "image":"accelerator", "audio":"cpu-media", "video":"accelerator", "3d":"accelerator", "upscale":"accelerator"}


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def _latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms":round(_percentile(values, 0.50) * 1000, 3),
        "p95_ms":round(_percentile(values, 0.95) * 1000, 3),
        "p99_ms":round(_percentile(values, 0.99) * 1000, 3),
        "max_ms":round(max(values, default=0) * 1000, 3),
    }


def run_benchmark(*, control_requests: int = 80, media_requests: int = 24, accelerator_requests: int = 8) -> dict[str, object]:
    benchmark_threads_before = sum(thread.name.startswith("single-node-benchmark") for thread in threading.enumerate())
    scheduler = ResourceScheduler(
        resource_pools=POOLS,
        pool_capacities={"accelerator":1, "cpu-media":2, "control":4},
        pool_queue_limits={"accelerator":16, "cpu-media":32, "control":128},
        tenant_queue_limits={"accelerator":8, "cpu-media":16, "control":64},
        project_queue_limits={"accelerator":4, "cpu-media":8, "control":32},
        serialized_pools=set(),
    )
    latencies: dict[str, list[float]] = {"control":[], "cpu-media":[], "accelerator":[]}
    peak = {"active":0, "queued":0}
    peak_lock = threading.Lock()

    def request(resource_class: str, index: int, duration: float, tenant: str, project: str) -> None:
        started = time.perf_counter()
        with scheduler.claim(resource_class, f"{resource_class}-{index}", timeout=3, tenant_id=tenant, user_id="benchmark", project_id=project):
            elapsed = time.perf_counter() - started
            pool = POOLS[resource_class]
            latencies[pool].append(elapsed)
            snapshot = scheduler.snapshot()
            with peak_lock:
                peak["active"] = max(peak["active"], len(snapshot["active_items"]))
                peak["queued"] = max(peak["queued"], len(snapshot["queued"]))
            time.sleep(duration)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=32, thread_name_prefix="single-node-benchmark") as executor:
        futures = []
        for index in range(accelerator_requests):
            futures.append(executor.submit(request, "image", index, 0.012, f"tenant-{index % 2}", f"gpu-{index % 4}"))
        for index in range(media_requests):
            futures.append(executor.submit(request, "audio", index, 0.003, f"tenant-{index % 4}", f"media-{index % 8}"))
        for index in range(control_requests):
            futures.append(executor.submit(request, "control", index, 0.0005, f"tenant-{index % 8}", f"control-{index % 16}"))
        for future in as_completed(futures):
            future.result()
    elapsed = time.perf_counter() - started

    cancellation = ResourceScheduler(resource_pools=POOLS, pool_capacities={"accelerator":1,"cpu-media":1,"control":1}, serialized_pools=set())
    holder_entered = threading.Event(); holder_release = threading.Event(); cancelled = []
    def holder() -> None:
        with cancellation.claim("image", "holder", timeout=1):
            holder_entered.set(); holder_release.wait(2)
    def waiter() -> None:
        try:
            with cancellation.claim("image", "cancel-me", timeout=2):
                raise AssertionError("cancelled waiter was admitted")
        except ResourceSchedulerError as error:
            cancelled.append(str(error))
    holder_thread = threading.Thread(target=holder); holder_thread.start(); holder_entered.wait(1)
    waiter_thread = threading.Thread(target=waiter); waiter_thread.start()
    deadline = time.monotonic() + 1
    while not cancellation.snapshot()["queued"] and time.monotonic() < deadline:
        time.sleep(0.001)
    cancel_started = time.perf_counter(); cancelled_count = cancellation.cancel_job("cancel-me"); waiter_thread.join(2)
    cancel_latency_ms = (time.perf_counter() - cancel_started) * 1000
    holder_release.set(); holder_thread.join(2)

    pressure_snapshots = {}
    backpressure = {}
    for boundary, limits, queued_scope, rejected_scope in (
        ("pool", (1, 4, 4), ("tenant-a", "project-a"), ("tenant-b", "project-b")),
        ("tenant", (4, 1, 4), ("tenant-a", "project-a"), ("tenant-a", "project-b")),
        ("project", (4, 4, 1), ("tenant-a", "project-a"), ("tenant-a", "project-a")),
    ):
        pool_limit, tenant_limit, project_limit = limits
        pressure = ResourceScheduler(
            resource_pools=POOLS, pool_capacities={"accelerator":1,"cpu-media":1,"control":1},
            pool_queue_limits={"accelerator":pool_limit,"cpu-media":4,"control":4},
            tenant_queue_limits={"accelerator":tenant_limit,"cpu-media":4,"control":4},
            project_queue_limits={"accelerator":project_limit,"cpu-media":4,"control":4}, serialized_pools=set(),
        )
        pressure_entered = threading.Event(); pressure_release = threading.Event()
        def pressure_holder(current=pressure) -> None:
            with current.claim("image", f"{boundary}-holder", timeout=1, tenant_id="holder", user_id="benchmark", project_id="holder"):pressure_entered.set();pressure_release.wait(2)
        def pressure_waiter(current=pressure, scope=queued_scope) -> None:
            with current.claim("image", f"{boundary}-waiter", timeout=2, tenant_id=scope[0], user_id="benchmark", project_id=scope[1]):pass
        first = threading.Thread(target=pressure_holder); second = threading.Thread(target=pressure_waiter); first.start(); pressure_entered.wait(1); second.start()
        deadline = time.monotonic() + 1
        while not pressure.snapshot()["queued"] and time.monotonic() < deadline:time.sleep(0.001)
        backpressure[boundary] = 0
        try:
            with pressure.claim("image", f"{boundary}-rejected", timeout=0.01, tenant_id=rejected_scope[0], user_id="benchmark", project_id=rejected_scope[1]):pass
        except ResourceSchedulerError as error:
            backpressure[boundary] = int("backpressure" in str(error))
        pressure_release.set(); first.join(2); second.join(2); pressure_snapshots[boundary] = pressure.snapshot()

    final = scheduler.snapshot(); cancellation_final = cancellation.snapshot()
    benchmark_threads_after = sum(thread.name.startswith("single-node-benchmark") for thread in threading.enumerate())
    return {
        "environment":{"system":os.uname().sysname, "machine":os.uname().machine, "python":sys.version.split()[0]},
        "parameters":{"control_requests":control_requests, "media_requests":media_requests, "accelerator_requests":accelerator_requests, "capacities":{"control":4,"cpu-media":2,"accelerator":1}},
        "elapsed_seconds":round(elapsed, 4),
        "throughput_per_second":round((control_requests + media_requests + accelerator_requests) / elapsed, 2),
        "latency":{"control":_latency_summary(latencies["control"]), "cpu_media":_latency_summary(latencies["cpu-media"]), "accelerator":_latency_summary(latencies["accelerator"])},
        "queue_age_ms":{"accelerator_max":round(max(latencies["accelerator"], default=0) * 1000, 3), "cpu_media_max":round(max(latencies["cpu-media"], default=0) * 1000, 3)},
        "cancel":{"requested":cancelled_count, "latency_ms":round(cancel_latency_ms, 3), "result":cancelled},
        "backpressure_rejections":backpressure,
        "peak":peak,
        "threads":{"before":benchmark_threads_before, "after":benchmark_threads_after},
        "final":{"main":final, "cancellation":cancellation_final, **{f"pressure_{key}":value for key,value in pressure_snapshots.items()}},
    }


def validate(report: dict[str, object]) -> None:
    latency = report["latency"]
    final = report["final"]
    if latency["control"]["p99_ms"] >= 500:
        raise SystemExit("CONTROL_PLANE_STARVATION")
    if report["cancel"]["requested"] != 1 or report["cancel"]["latency_ms"] >= 500:
        raise SystemExit("CANCELLATION_LATENCY_REGRESSION")
    if report["backpressure_rejections"] != {"pool":1, "tenant":1, "project":1}:
        raise SystemExit("BACKPRESSURE_NOT_ENFORCED")
    if report["threads"]["after"] != report["threads"]["before"]:
        raise SystemExit("BENCHMARK_THREAD_LEAK")
    if report["peak"]["active"] > sum(report["parameters"]["capacities"].values()):
        raise SystemExit("RESOURCE_POOL_OVERSUBSCRIPTION")
    if any(snapshot["active_items"] or snapshot["queued"] for snapshot in final.values()):
        raise SystemExit("RESOURCE_TICKETS_NOT_RELEASED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", type=int, default=80)
    parser.add_argument("--media", type=int, default=24)
    parser.add_argument("--accelerator", type=int, default=8)
    arguments = parser.parse_args()
    report = run_benchmark(control_requests=arguments.control, media_requests=arguments.media, accelerator_requests=arguments.accelerator)
    validate(report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
