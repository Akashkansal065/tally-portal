"""The agent tells the server which Tally company it is syncing, and sends Tally nothing meant for another one."""
from cloud_client import CloudClient
from tests.test_tally_safety import OutboundCloud, OutboundTally, make_agent

OK = (True, "<RESPONSE><CREATED>1</CREATED></RESPONSE>")


class RecordingTally(OutboundTally):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent = []

    def send_xml(self, xml):
        self.sent.append(xml)
        return self.reply

    def find_voucher_by_master_id(self, company, master_id):
        return None


def run_task(tmp_path, tally, **task_fields):
    cloud = OutboundCloud()
    cloud.task.update(task_fields)
    agent = make_agent(tmp_path, tally, cloud)
    agent.sync_outbound_cycle()
    return agent, cloud


def test_every_cloud_call_names_the_company():
    client = CloudClient(token="t")
    assert "X-Tally-Company-GUID" not in client._get_headers()
    client.company_guid = "guid-alpha"
    assert client._get_headers()["X-Tally-Company-GUID"] == "guid-alpha"


def test_agent_passes_its_company_guid_to_the_cloud_client(tmp_path):
    agent, cloud = run_task(tmp_path, RecordingTally(OK))
    assert agent.active_company_guid == "guid-alpha" and cloud.company_guid == "guid-alpha"


def test_task_for_another_tally_company_is_not_sent(tmp_path):
    tally = RecordingTally(OK)
    _, cloud = run_task(tmp_path, tally, company_guid="guid-beta")
    assert tally.sent == [] and cloud.acked == []


def test_task_for_this_company_is_sent_under_the_name_tally_shows_now(tmp_path):
    # Renamed in Tally since the server last heard: the GUID matches, so the payload follows the new name
    tally = RecordingTally(OK, open_companies=[{"name": "Alpha & Sons", "guid": "guid-alpha"}])
    cloud = OutboundCloud()
    cloud.task["company_guid"] = "guid-alpha"
    agent = make_agent(tmp_path, tally, cloud)
    agent.active_company_guid = "guid-alpha"
    agent.sync_outbound_cycle()
    assert "<SVCURRENTCOMPANY>Alpha &amp; Sons</SVCURRENTCOMPANY>" in tally.sent[0] and cloud.acked == [1]


def test_older_server_payload_naming_another_company_is_not_sent(tmp_path):
    tally = RecordingTally(OK)
    _, cloud = run_task(tmp_path, tally, xml_payload="<ENVELOPE><STATICVARIABLES><SVCURRENTCOMPANY>Beta</SVCURRENTCOMPANY>"
                                                     "</STATICVARIABLES><LEDGER NAME=\"X\"/></ENVELOPE>")
    assert tally.sent == [] and cloud.acked == []


def test_payload_that_names_no_company_is_not_sent(tmp_path):
    tally = RecordingTally(OK)
    _, cloud = run_task(tmp_path, tally, xml_payload="<ENVELOPE><LEDGER NAME=\"X\"/></ENVELOPE>")
    assert tally.sent == [] and cloud.acked == []


# ── Signed in as this PC (a device token) ──

def test_a_signed_in_pc_uses_its_device_token_and_keeps_no_password(tmp_path):
    agent = make_agent(tmp_path, RecordingTally(OK), OutboundCloud())
    agent.config.device_token, agent.config.password, agent.config.email = "mta_abc", "old-password", "owner@example.com"

    client = agent._new_cloud_client()

    assert client.device_mode and client.token == "mta_abc"
    assert client.password == "" and client.email == ""


def test_a_signed_out_pc_stops_instead_of_retrying_with_a_password():
    halted = []
    client = CloudClient(token="mta_abc", email="owner@example.com", password="pw", on_auth_halted=halted.append)

    assert client.reauthenticate("invalid") is False
    assert halted == ["device_signed_out"] and client.auth_halt_reason == "device_signed_out"

    revoked = CloudClient(token="mta_abc", on_auth_halted=halted.append)
    revoked.reauthenticate("admin_revoke")
    assert halted[-1] == "admin_revoke"


class LinkingCloud(OutboundCloud):
    def __init__(self, answer):
        super().__init__()
        self.answer, self.linked = answer, []

    def link_company(self, company, take_over=False):
        self.linked.append((company, take_over))
        return self.answer


def test_linking_sends_the_open_companys_guid_and_pins_it(tmp_path):
    tally = RecordingTally(OK, open_companies=[{"name": "Alpha", "guid": "guid-alpha", "starting_from": "20250401"}])
    cloud = LinkingCloud((True, {"company_id": 5}, ""))
    agent = make_agent(tmp_path, tally, cloud)

    assert agent.link_active_company() == (True, "", "")

    company, take_over = cloud.linked[0]
    assert (company["tally_guid"], company["name"], company["books_from"], take_over) == ("guid-alpha", "Alpha", "20250401", False)
    assert agent.active_company_guid == "guid-alpha" and agent.config.company_guid == "guid-alpha"


def test_linking_reports_when_another_pc_syncs_the_company_or_it_is_closed(tmp_path):
    cloud = LinkingCloud((False, "already synced from another PC", "linked_to_another_device"))
    agent = make_agent(tmp_path, RecordingTally(OK), cloud)
    assert agent.link_active_company() == (False, "already synced from another PC", "linked_to_another_device")

    closed = make_agent(tmp_path, RecordingTally(OK, open_companies=[{"name": "Other", "guid": "guid-other"}]), cloud)
    ok, _, reason = closed.link_active_company()
    assert (ok, reason) == (False, "not_open")
