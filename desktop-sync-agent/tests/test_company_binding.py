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
