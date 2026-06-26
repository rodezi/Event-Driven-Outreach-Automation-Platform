from outreach_system.cli import EXIT_SUCCESS, main
from outreach_system.models import ExecutionSummary


def test_cli_respects_max_emails(monkeypatch, settings) -> None:
    captured: dict[str, int] = {}

    def fake_run_pipeline(*, max_emails: int, settings):
        del settings
        captured["max_emails"] = max_emails
        return ExecutionSummary(max_emails=max_emails)

    monkeypatch.setattr("outreach_system.cli.get_settings", lambda: settings)
    monkeypatch.setattr("outreach_system.cli.run_pipeline", fake_run_pipeline)

    exit_code = main(["--run-now", "--max-emails", "20"])

    assert exit_code == EXIT_SUCCESS
    assert captured["max_emails"] == 20
