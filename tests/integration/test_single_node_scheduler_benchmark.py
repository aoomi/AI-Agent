from scripts.maintenance.benchmark_single_node_scheduler import run_benchmark, validate


def test_single_node_mixed_load_preserves_control_backpressure_cancel_and_release():
    report = run_benchmark(control_requests=24, media_requests=8, accelerator_requests=4)
    validate(report)
    assert report["parameters"]["capacities"] == {"control":4, "cpu-media":2, "accelerator":1}
    assert report["latency"]["control"]["p99_ms"] < 500
    assert report["cancel"]["result"] == ["resource request cancelled"]
    assert report["backpressure_rejections"] == {"pool":1, "tenant":1, "project":1}
    assert report["threads"]["after"] == report["threads"]["before"]
    assert all(not snapshot["active_items"] and not snapshot["queued"] for snapshot in report["final"].values())
