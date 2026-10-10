"""One agent, several Tally companies: each is synced in turn under its own GUID, a closed or ambiguous one is
skipped without stopping the rest, and each keeps its own retry point."""
import json

import agent as agent_module

ALPHA = {"guid": "guid-alpha", "name": "Alpha"}
BETA = {"guid": "guid-beta", "name": "Beta"}


class Tally:
    def __init__(self, open_companies, records=None):
        self.open_companies = open_companies
        self.records = records or {}          # company name -> {label: [alter ids]}
        self.fail = set()                     # (company name, label) that Tally fails to export
        self.last_export_failures = []
        self.sent = []

    def check_health(self):
        return True, "ok"

    def get_open_companies(self):
        return self.open_companies

    def export_full_collections(self, company, min_alter_id=0, min_voucher_alter_id=None):
        self.last_export_failures = []
        out = []
        for label, ids in self.records.get(company, {}).items():
            if (company, label) in self.fail:
                self.last_export_failures.append(label)
                continue
            chosen = [i for i in ids if i > min_alter_id]
            if chosen:
                out.append((label, json.dumps({"company": company, "label": label, "ids": chosen})))
        return out

    def send_xml(self, xml):
        self.sent.append(xml)
        return True, "<RESPONSE><CREATED>1</CREATED></RESPONSE>"

    def find_voucher_by_master_id(self, company, master_id):
        return None


class Cloud:
    """Keeps a separate queue and watermark per company GUID, as the server does."""
    auth_halt_reason = ""

    def __init__(self, queues=None):
        self.company_guid = ""
        self.queues = queues or {}
        self.have = {}                        # guid -> alter ids held
        self.acked, self.asked, self.pushed, self.reports = [], [], [], []

    def fetch_outbound_queue(self):
        self.asked.append(self.company_guid)
        return list(self.queues.get(self.company_guid, [])), None

    def acknowledge_queue(self, ids):
        self.acked.append((self.company_guid, ids))
        return True

    def report_voucher_identities(self, identities):
        return True

    def get_last_alter_id(self):
        m = max(self.have.get(self.company_guid, set()), default=0)
        return m, m

    def push_inbound_xml(self, xml, company_name=None, force=False):
        d = json.loads(xml)
        self.pushed.append((self.company_guid, d["company"], d["label"]))
        self.have.setdefault(self.company_guid, set()).update(d["ids"])
        return True, {"status": "success"}

    def report_state(self, reports):
        self.reports.append(reports)
        return True


def task(sync_id, company):
    return {"sync_id": sync_id, "record_type": "Ledger", "record_id": sync_id, "action": "Create", "company_guid": company["guid"],
            "xml_payload": f"<ENVELOPE><STATICVARIABLES><SVCURRENTCOMPANY>{company['name']}</SVCURRENTCOMPANY></STATICVARIABLES><LEDGER NAME='L{sync_id}'/></ENVELOPE>"}


def make_agent(tmp_path, tally, cloud, linked=(ALPHA, BETA)):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = tally, cloud
    a.config.companies = [dict(c) for c in linked]
    a.config.company_guid, a.config.company_name = linked[0]["guid"], linked[0]["name"]
    a.active_company_guid, a.active_company_name = linked[0]["guid"], linked[0]["name"]
    a.tally_connected = True
    return a


def test_each_companys_queue_goes_to_that_company(tmp_path):
    tally = Tally([ALPHA, BETA])
    cloud = Cloud({"guid-alpha": [task(1, ALPHA)], "guid-beta": [task(2, BETA)]})

    assert make_agent(tmp_path, tally, cloud).sync_outbound_cycle() == 2

    assert cloud.asked == ["guid-alpha", "guid-beta"]
    assert cloud.acked == [("guid-alpha", [1]), ("guid-beta", [2])]
    assert ["<SVCURRENTCOMPANY>Alpha<" in tally.sent[0], "<SVCURRENTCOMPANY>Beta<" in tally.sent[1]] == [True, True]


def test_a_closed_company_is_skipped_and_the_other_still_syncs(tmp_path):
    tally = Tally([BETA], {"Beta": {"Ledgers": [1, 2]}})
    cloud = Cloud({"guid-alpha": [task(1, ALPHA)], "guid-beta": [task(2, BETA)]})
    agent = make_agent(tmp_path, tally, cloud)

    assert agent.sync_outbound_cycle() == 1
    agent.sync_inbound_cycle(is_incremental=True)

    assert cloud.asked == ["guid-beta"] and not agent.company_paused
    assert cloud.pushed == [("guid-beta", "Beta", "Ledgers")]
    assert "'Alpha' is not open in Tally" in agent.last_sync_status
    report = {r["tally_guid"]: (r["state"], r["ok"]) for r in cloud.reports[-1]}
    assert report == {"guid-alpha": ("closed", False), "guid-beta": ("live", True)}


def test_two_open_companies_with_one_name_are_both_left_alone(tmp_path):
    # A restored copy of Alpha is open beside the real one: Tally can only be addressed by name, so neither is safe
    tally = Tally([ALPHA, {"guid": "guid-copy", "name": "Alpha"}, BETA])
    cloud = Cloud({"guid-alpha": [task(1, ALPHA)], "guid-beta": [task(2, BETA)]})
    agent = make_agent(tmp_path, tally, cloud)

    assert agent.sync_outbound_cycle() == 1

    assert cloud.asked == ["guid-beta"]
    assert [c["state"] for c in agent.company_states] == ["ambiguous", "open"]


def test_everything_closed_pauses_and_reports_it(tmp_path):
    tally = Tally([{"guid": "guid-other", "name": "Other"}])
    cloud = Cloud({"guid-alpha": [task(1, ALPHA)]})
    agent = make_agent(tmp_path, tally, cloud)

    assert agent.sync_outbound_cycle() == 0
    agent.sync_inbound_cycle(is_incremental=True)

    assert agent.company_paused and cloud.asked == [] and tally.sent == []
    assert {r["state"] for r in cloud.reports[-1]} == {"closed"}


def test_each_company_keeps_its_own_watermark_and_retry_point(tmp_path):
    tally = Tally([ALPHA, BETA], {"Alpha": {"Ledgers": [101, 102], "Vouchers": [103]}, "Beta": {"Ledgers": [5, 6]}})
    tally.fail.add(("Alpha", "Ledgers"))
    cloud = Cloud()
    cloud.have = {"guid-alpha": {100}, "guid-beta": {4}}
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=True)

    # Alpha's failed export leaves a retry point for Alpha only; Beta is clean and unaffected
    assert agent.config.inbound_retry_floors == {"guid-alpha": 100}
    assert ("guid-beta", "Beta", "Ledgers") in cloud.pushed
    report = {r["tally_guid"]: r["ok"] for r in cloud.reports[-1]}
    assert report == {"guid-alpha": False, "guid-beta": True}

    # Tally recovers: Alpha is re-pulled from its own retry point, not from Beta's or the server's newer watermark
    tally.fail.clear()
    agent.sync_inbound_cycle(is_incremental=True)
    assert ("guid-alpha", "Alpha", "Ledgers") in cloud.pushed
    assert agent.config.inbound_retry_floors == {}


def test_a_company_renamed_in_tally_is_followed_by_its_guid(tmp_path):
    tally = Tally([{"guid": "guid-alpha", "name": "Alpha & Sons"}, BETA])
    agent = make_agent(tmp_path, tally, Cloud())

    agent.sync_outbound_cycle()

    assert agent.config.companies[0] == {"guid": "guid-alpha", "name": "Alpha & Sons"}
    assert agent.config.company_name == "Alpha & Sons"


class LinkCloud(Cloud):
    def link_company(self, company, take_over=False):
        return True, {"company_id": 9}, ""

    def unlink_company(self, guid):
        return True


def test_linking_a_second_company_keeps_the_first_and_unlinking_drops_only_that_one(tmp_path):
    agent = make_agent(tmp_path, Tally([ALPHA, BETA]), LinkCloud(), linked=(ALPHA,))
    agent.config.companies = []          # an agent that has only ever had its one company

    assert agent.link_company({"tally_guid": "guid-beta", "name": "Beta"})[0]
    assert [c["guid"] for c in agent.config.companies] == ["guid-alpha", "guid-beta"]
    assert agent.config.company_guid == "guid-alpha"

    assert agent.unlink_company("guid-alpha")
    assert [c["guid"] for c in agent.config.companies] == ["guid-beta"]
    assert (agent.config.company_guid, agent.active_company_name) == ("guid-beta", "Beta")
