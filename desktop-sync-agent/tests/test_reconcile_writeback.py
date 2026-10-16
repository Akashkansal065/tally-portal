"""WS-14: the write-back reads the voucher first, changes only the two bank tags, and stops when unsure."""
import agent as agent_module
import reconcile_writeback as rwb
from tally_client import TallyClient

GUID = "guid-sample"
BLOCK = ('<VOUCHER REMOTEID="x" VCHTYPE="Receipt" ACTION="Create"><DATE>20260301</DATE><GUID>g-1</GUID>'
         '<MASTERID> 301</MASTERID><ALTERID> 9</ALTERID><VOUCHERNUMBER>7</VOUCHERNUMBER><NARRATION>Rent &amp; co</NARRATION>'
         '<ALLLEDGERENTRIES.LIST><LEDGERNAME>Sample Bank</LEDGERNAME><AMOUNT>-1000.00</AMOUNT>'
         '<BANKALLOCATIONS.LIST><INSTRUMENTNUMBER>000123</INSTRUMENTNUMBER><AMOUNT>-1000.00</AMOUNT></BANKALLOCATIONS.LIST>'
         '</ALLLEDGERENTRIES.LIST>'
         '<ALLLEDGERENTRIES.LIST><LEDGERNAME>Customer</LEDGERNAME><AMOUNT>1000.00</AMOUNT></ALLLEDGERENTRIES.LIST></VOUCHER>')


def test_only_the_two_bank_tags_change():
    new, outcome, _ = rwb.apply_bank_dates(BLOCK, "000123", "1000.00", "20260305", "Yes")
    assert outcome == rwb.DONE
    assert "<BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS></BANKALLOCATIONS.LIST>" in new
    # everything else is byte for byte what Tally exported
    assert new.replace("<BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS>", "") == BLOCK


def test_existing_values_are_replaced_and_the_same_values_are_a_no_op():
    first, _, _ = rwb.apply_bank_dates(BLOCK, "000123", "1000.00", "20260305", "Yes")
    again, outcome, _ = rwb.apply_bank_dates(first, "000123", "1000.00", "20260305", "Yes")
    assert again is None and outcome == rwb.ALREADY
    moved, outcome, _ = rwb.apply_bank_dates(first, "000123", "1000.00", "20260310", "Yes")
    assert outcome == rwb.DONE and moved.count("<BANKERSDATE>") == 1 and "<BANKERSDATE>20260310</BANKERSDATE>" in moved


def test_an_allocation_that_is_not_exactly_one_is_never_guessed():
    none, outcome, _ = rwb.apply_bank_dates(BLOCK, "999", "1000.00", "20260305", "Yes")
    assert none is None and outcome == rwb.FAILED
    two = BLOCK.replace("</ALLLEDGERENTRIES.LIST><ALLLEDGERENTRIES.LIST><LEDGERNAME>Customer",
                        '<BANKALLOCATIONS.LIST><INSTRUMENTNUMBER>000123</INSTRUMENTNUMBER><AMOUNT>-1000.00</AMOUNT></BANKALLOCATIONS.LIST>'
                        "</ALLLEDGERENTRIES.LIST><ALLLEDGERENTRIES.LIST><LEDGERNAME>Customer")
    assert rwb.apply_bank_dates(two, "000123", "1000.00", "20260305", "Yes")[1] == rwb.FAILED


def test_the_alter_is_addressed_by_master_id_and_date():
    new, _, _ = rwb.apply_bank_dates(BLOCK, "000123", "1000.00", "20260305", "Yes")
    xml = rwb.alter_envelope("Sample & Co", new, 301, "20260301")
    assert '<VOUCHER DATE="20260301" TAGNAME="MASTERID" TAGVALUE="301" VCHTYPE="Receipt" ACTION="Alter">' in xml
    assert "REMOTEID" not in xml and "<SVCURRENTCOMPANY>Sample &amp; Co</SVCURRENTCOMPANY>" in xml
    assert "<NARRATION>Rent &amp; co</NARRATION>" in xml


def test_the_server_directive_is_read():
    marker = ('<MYTALLYRECONCILE VERSION="1" VOUCHERID="5"><SVCURRENTCOMPANY>Sample Co</SVCURRENTCOMPANY>'
              "<MASTERID>301</MASTERID><DATE>20260301</DATE><ALTERID>9</ALTERID><ALLOCATION><INSTRUMENTNUMBER>000123</INSTRUMENTNUMBER>"
              "<AMOUNT>1000.00</AMOUNT><BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS></ALLOCATION></MYTALLYRECONCILE>")
    job = rwb.parse_marker(marker)
    assert job == {"master_id": "301", "date": "20260301", "alter_id": "9", "instrument_number": "000123",
                   "amount": "1000.00", "bankers_date": "20260305", "manual_status": "Yes"}
    assert rwb.parse_marker("<ENVELOPE/>") is None and rwb.parse_marker("<MYTALLYRECONCILE><MASTERID>x</MASTERID></MYTALLYRECONCILE>") is None


# ── through the agent, against the mock Tally ──

class Cloud:
    auth_halt_reason = ""
    company_fingerprint = "10001|20260401"

    def __init__(self):
        self.company_guid = GUID
        self.results = []

    def report_reconcile_result(self, sync_id, outcome, alter_id="", message=""):
        self.results.append((sync_id, outcome, alter_id, message))
        return True


MARKER = ('<MYTALLYRECONCILE VERSION="1" VOUCHERID="5"><SVCURRENTCOMPANY>Sample Co</SVCURRENTCOMPANY>'
          "<MASTERID>301</MASTERID><DATE>20260301</DATE><ALTERID>{alter}</ALTERID><ALLOCATION><INSTRUMENTNUMBER>000123</INSTRUMENTNUMBER>"
          "<AMOUNT>1000.00</AMOUNT><BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS></ALLOCATION></MYTALLYRECONCILE>")
IMPORT_OK = "<ENVELOPE><BODY><DATA><IMPORTRESULT><CREATED>0</CREATED><ALTERED>1</ALTERED><ERRORS>0</ERRORS></IMPORTRESULT></DATA></BODY></ENVELOPE>"


def agent(tmp_path, mock_tally):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = TallyClient(mock_tally.url, timeout=5), Cloud()
    a.active_company_guid, a.active_company_name = GUID, "Sample Co"
    return a


def envelope(block):
    return f"<ENVELOPE><BODY><DATA><COLLECTION>{block}</COLLECTION></DATA></BODY></ENVELOPE>"


def test_a_voucher_that_changed_in_tally_is_not_touched(tmp_path, mock_tally):
    mock_tally.respond("MyTallyFullVchById", envelope(BLOCK))
    a = agent(tmp_path, mock_tally)
    a._write_back_reconcile(11, 5, MARKER.format(alter="8"))           # MyTally last saw AlterID 8, Tally has 9
    assert a.cloud.results[0][:2] == (11, rwb.STALE)
    assert "MyTallyFullVchById" in mock_tally.ids and len(mock_tally.ids) == 1      # nothing was sent


def test_a_matching_voucher_is_altered_once_and_reported(tmp_path, mock_tally):
    after = BLOCK.replace("<ALTERID> 9<", "<ALTERID> 10<").replace(
        "</BANKALLOCATIONS.LIST>", "<BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS></BANKALLOCATIONS.LIST>")
    mock_tally.respond("MyTallyFullVchById", [envelope(BLOCK), envelope(after)])
    sent = []

    def import_reply(body):
        sent.append(body)
        return IMPORT_OK
    mock_tally.respond("Vouchers", import_reply)
    a = agent(tmp_path, mock_tally)
    a._write_back_reconcile(12, 5, MARKER.format(alter="9"))
    assert a.cloud.results == [(12, rwb.DONE, "10", "Changed BANKERSDATE/BANKMANUALSTATUS only.")]
    (body,) = sent
    assert 'TAGNAME="MASTERID" TAGVALUE="301"' in body and 'ACTION="Alter"' in body
    assert body.count("<BANKERSDATE>20260305</BANKERSDATE>") == 1


def test_values_already_in_tally_send_nothing(tmp_path, mock_tally):
    already = BLOCK.replace("</BANKALLOCATIONS.LIST>",
                            "<BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS></BANKALLOCATIONS.LIST>")
    mock_tally.respond("MyTallyFullVchById", envelope(already))
    a = agent(tmp_path, mock_tally)
    a._write_back_reconcile(13, 5, MARKER.format(alter="9"))
    assert a.cloud.results[0][1] == rwb.ALREADY and "Vouchers" not in mock_tally.ids


def test_a_voucher_tally_does_not_return_fails_cleanly(tmp_path, mock_tally):
    a = agent(tmp_path, mock_tally)
    a._write_back_reconcile(14, 5, MARKER.format(alter="9"))
    assert a.cloud.results[0][1] == rwb.FAILED
