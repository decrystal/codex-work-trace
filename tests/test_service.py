from csgs.service import SessionGraphService
from csgs.store import RunStore


def test_log_run_generates_summary_and_id(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))

    run = service.log_run(
        prompt="Please add search for runs",
        output="Implemented search over prompt and summary.",
        project="csgs",
        tags=["idea", "search"],
    )

    assert run.id.startswith("R_")
    assert "search" in run.summary.lower()
    assert len([s for s in run.summary.split(".") if s.strip()]) <= 5
    assert service.get_run(run.id).summary == run.summary
