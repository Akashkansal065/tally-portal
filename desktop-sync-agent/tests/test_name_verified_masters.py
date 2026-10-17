"""P0.3: a master delete or rename that Tally would find by NAME is sent only after the agent has read the master
by that name in Tally and seen exactly one object whose GUID is the one MyTally stored."""
import re

import agent as agent_module
from tally_client import TallyClient

COMPANY = "Alpha"


def delete_xml(tag, name):
    return (f'<ENVELOPE><BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>{COMPANY}</SVCURRENTCOMPANY></STATICVARIABLES></DESC>'
            f'<TALLYMESSAGE><{tag} NAME="{name}" ACTION="Delete"><NAME>{name}</NAME></{tag}></TALLYMESSAGE></BODY></ENVELOPE>')


def alter_xml(tag, old, new):
    return (f'<ENVELOPE><BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>{COMPANY}</SVCURRENTCOMPANY></STATICVARIABLES></DESC>'
            f'<TALLYMESSAGE><{tag} NAME="{old}" ACTION="Alter"><NAME>{new}</NAME></{tag}></TALLYMESSAGE></BODY></ENVELOPE>')


def task(sync_id, xml, name, guid, record_type="Ledger", action="Delete", mode="name_verified"):
    address = {"mode": mode, "object_type": record_type, "name": name, "expect_guid": guid}
    return {"sync_id": sync_id, "record_type": record_type, "record_id": sync_id, "action": action,
            "xml_payload": xml, "address": address}


class World:
    """Tally's masters as (type, name) -> [guids]. verify_master reads them; send_xml deletes by the NAME attribute,
    as Tally does, so a delete that gets through really removes whatever has that name."""

    def __init__(self, masters, answers=True):
        self.masters = {k: list(v) for k, v in masters.items()}
        self.answers = answers
        self.sent = []
        self.verified = []

    def get_open_companies(self):
        return [{"name": COMPANY, "guid": "guid-alpha"}]

    def verify_master(self, company, obj_type, name):
        self.verified.append((obj_type, name))
        if not self.answers:
            return None
        return [{"name": name, "guid": g, "master_id": "1"} for g in self.masters.get((obj_type, name), [])]

    def send_xml(self, xml):
        self.sent.append(xml)
        m = re.search(r'<(LEDGER|GROUP|STOCKITEM) NAME="([^"]*)" ACTION="Delete"', xml, re.I)
        if m:
            kinds = {"LEDGER": "Ledger", "GROUP": "Group", "STOCKITEM": "StockItem"}
            self.masters.pop((kinds[m.group(1).upper()], m.group(2)), None)
        return True, "<ENVELOPE><LINEERROR></LINEERROR><CREATED>0</CREATED><ALTERED>0</ALTERED></ENVELOPE>"


class Cloud:
    auth_halt_reason = ""
    company_guid = ""

    def __init__(self, tasks):
        self.tasks, self.acked, self.reviews = tasks, [], []

    def report_state(self, reports):
        return True

    def fetch_outbound_queue(self):
        return list(self.tasks), None

    def acknowledge_queue(self, ids):
        self.acked.extend(ids)
        return True

    def report_needs_review(self, sync_id, message, guid_seen=None):
        self.reviews.append((sync_id, message, guid_seen))
        return True


def run(tmp_path, world, tasks):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    cloud = Cloud(tasks)
    a.tally, a.cloud = world, cloud
    a.active_company_name = COMPANY
    a.sync_outbound_cycle()
    return a, cloud


def test_a_delete_of_the_ledger_MyTally_means_is_sent(tmp_path):
    world = World({("Ledger", "ABC Traders"): ["g-old"]})
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "ABC Traders"), "ABC Traders", "g-old")])
    assert len(world.sent) == 1 and cloud.acked == [1] and cloud.reviews == []
    assert world.verified == [("Ledger", "ABC Traders")]


def test_a_ledger_renamed_and_recreated_in_tally_is_not_deleted(tmp_path):
    """'ABC Traders' (g-old) was renamed to 'ABC Traders (Old)' in Tally and a new 'ABC Traders' (g-new) created.
    Deleting the old party in MyTally must not delete the new one."""
    world = World({("Ledger", "ABC Traders (Old)"): ["g-old"], ("Ledger", "ABC Traders"): ["g-new"]})
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "ABC Traders"), "ABC Traders", "g-old")])
    assert world.sent == [] and cloud.acked == []
    assert world.masters[("Ledger", "ABC Traders")] == ["g-new"]            # still there
    (sync_id, message, guid_seen), = cloud.reviews
    assert sync_id == 1 and guid_seen == "g-new" and "g-new" in message and "g-old" in message


def test_a_rename_of_a_recreated_name_is_not_sent(tmp_path):
    world = World({("Ledger", "ABC Traders"): ["g-new"]})
    _, cloud = run(tmp_path, world, [task(2, alter_xml("LEDGER", "ABC Traders", "ABC Traders Pvt"), "ABC Traders", "g-old",
                                          action="Alter")])
    assert world.sent == [] and [r[0] for r in cloud.reviews] == [2]


def test_a_rename_of_the_right_object_is_sent(tmp_path):
    world = World({("Group", "Retail"): ["g-1"]})
    _, cloud = run(tmp_path, world, [task(3, alter_xml("GROUP", "Retail", "Retail Debtors"), "Retail", "g-1",
                                          record_type="Group", action="Alter")])
    assert len(world.sent) == 1 and cloud.acked == [3]


def test_nothing_in_tally_under_the_name_is_not_sent(tmp_path):
    world = World({})
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "Gone"), "Gone", "g-old")])
    assert world.sent == [] and [r[0] for r in cloud.reviews] == [1] and "0" in cloud.reviews[0][1]


def test_two_objects_under_one_name_are_never_guessed_between(tmp_path):
    world = World({("Ledger", "Twin"): ["g-old", "g-new"]})
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "Twin"), "Twin", "g-old")])
    assert world.sent == [] and [r[0] for r in cloud.reviews] == [1]


def test_a_filter_tally_ignored_returns_many_objects_and_nothing_is_sent(tmp_path):
    class Lenient(World):
        def verify_master(self, company, obj_type, name):
            return [{"name": n, "guid": g[0], "master_id": "1"} for (t, n), g in self.masters.items() if t == obj_type]
    world = Lenient({("Ledger", "ABC Traders"): ["g-old"], ("Ledger", "Other"): ["g-9"]})
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "ABC Traders"), "ABC Traders", "g-old")])
    assert world.sent == [] and [r[0] for r in cloud.reviews] == [1]


def test_no_stored_guid_means_no_send(tmp_path):
    world = World({("Ledger", "ABC Traders"): ["g-1"]})
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "ABC Traders"), "ABC Traders", None)])
    assert world.sent == [] and [r[0] for r in cloud.reviews] == [1] and world.verified == []


def test_a_tally_that_does_not_answer_holds_the_item_without_a_verdict(tmp_path):
    world = World({("Ledger", "ABC Traders"): ["g-old"]}, answers=False)
    _, cloud = run(tmp_path, world, [task(1, delete_xml("LEDGER", "ABC Traders"), "ABC Traders", "g-old")])
    assert world.sent == [] and cloud.reviews == [] and cloud.acked == []     # tried again next cycle


def test_a_delete_with_no_address_from_an_older_server_is_held(tmp_path):
    world = World({("Ledger", "ABC Traders"): ["g-old"]})
    bare = {"sync_id": 1, "record_type": "Ledger", "record_id": 1, "action": "Delete", "xml_payload": delete_xml("LEDGER", "ABC Traders")}
    _, cloud = run(tmp_path, world, [bare])
    assert world.sent == [] and [r[0] for r in cloud.reviews] == [1]


def test_every_name_addressed_delete_that_was_sent_was_checked_first(tmp_path):
    """The acceptance rule: inspect every envelope that reached Tally."""
    world = World({("Ledger", "A"): ["g-a"], ("Ledger", "B (Old)"): ["g-b"], ("Ledger", "B"): ["g-b2"],
                   ("StockItem", "Widget"): ["g-w"], ("Group", "G"): ["g-g"]})
    tasks = [task(1, delete_xml("LEDGER", "A"), "A", "g-a"),
             task(2, delete_xml("LEDGER", "B"), "B", "g-b"),
             task(3, delete_xml("STOCKITEM", "Widget"), "Widget", "g-w", record_type="StockItem"),
             task(4, delete_xml("GROUP", "G"), "G", "wrong", record_type="Group")]
    run(tmp_path, world, tasks)
    deleted = [re.search(r'NAME="([^"]*)"', xml).group(1) for xml in world.sent if 'ACTION="Delete"' in xml]
    assert deleted == ["A", "Widget"]
    assert {name for _, name in world.verified} >= set(deleted)
    assert world.masters[("Ledger", "B")] == ["g-b2"] and world.masters[("Group", "G")] == ["g-g"]


def test_the_name_is_a_declared_variable_never_part_of_the_formula(mock_tally):
    nasty = 'O\'Neil "& Sons" <[x]> $Name = 1'
    reply = ('<ENVELOPE><BODY><DATA><COLLECTION><LEDGER NAME="ok"><GUID>g-1</GUID><MASTERID>7</MASTERID></LEDGER>'
             "</COLLECTION></DATA></BODY></ENVELOPE>")
    mock_tally.respond("MyTallyVerifyMaster", reply)
    seen = TallyClient(mock_tally.url, timeout=5).verify_master(COMPANY, "Ledger", nasty)
    assert seen == [{"name": "ok", "guid": "g-1", "master_id": "7"}]
    (_, body), = [r for r in mock_tally.requests if r[0] == "MyTallyVerifyMaster"]
    formula = re.search(r'<SYSTEM TYPE="Formulae" NAME="MyTallyByName">(.*?)</SYSTEM>', body, re.S).group(1)
    assert formula == "$Name = ##MTV_NAME" and "Neil" not in formula
    assert "<MTV_NAME>O&apos;Neil &quot;&amp; Sons&quot; &lt;[x]&gt; $Name = 1</MTV_NAME>" in body
    assert 'NAME="MTV_NAME"' in body                      # declared, so Tally reads it as a variable
    assert "<![CDATA[" not in body and nasty not in body  # the raw text never appears unescaped


def test_a_tally_that_does_not_answer_gives_no_list(mock_tally):
    mock_tally.respond("MyTallyVerifyMaster", "garbage")
    assert TallyClient(mock_tally.url, timeout=5).verify_master(COMPANY, "Ledger", "x") is None
