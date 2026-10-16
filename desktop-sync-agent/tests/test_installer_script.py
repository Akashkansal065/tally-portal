"""WS-15: the installer script keeps the promises made for it (checked as text; Inno Setup runs in CI)."""
import os

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "installer", "MyTallyBridge.iss")


def uncommented():
    return "\n".join(l for l in open(SCRIPT, encoding="utf-8").read().splitlines() if not l.strip().startswith(";"))


def test_per_user_and_no_admin():
    text = uncommented()
    assert "PrivilegesRequired=lowest" in text
    assert "HKLM" not in text and "{pf}" not in text and "{cf}" not in text


def test_no_scheduled_task_service_or_autostart_entry():
    text = uncommented().lower()
    for forbidden in ("schtasks", "[registry]", "currentversion\\run", "sc create", "[ini]"):
        assert forbidden not in text


def test_it_installs_only_the_exe_and_leaves_user_data_on_uninstall():
    text = uncommented()
    assert text.count("Source:") == 1 and "SnehDistribuorsSync.exe" in text
    assert "[UninstallDelete]" not in text
