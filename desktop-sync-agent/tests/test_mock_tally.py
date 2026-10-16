"""The mock-Tally harness itself: the agent's real TallyClient talking to canned replies."""
from tally_client import TallyClient


def test_voucher_index_comes_from_the_canned_reply(mock_tally):
    client = TallyClient(mock_tally.url, timeout=5)
    assert client.export_voucher_index("Sample Co") == ["20260301", "20260302", "20260315"]
    assert mock_tally.ids == ["MyTallyVoucherIndex"]
    assert "<SVCURRENTCOMPANY>Sample Co</SVCURRENTCOMPANY>" in mock_tally.requests[0][1]


def test_replies_can_be_overridden_and_sequenced(mock_tally):
    client = TallyClient(mock_tally.url, timeout=5)
    mock_tally.respond("MyTallyVoucherIndex", [
        "<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER><DATE>20260401</DATE></VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>",
        mock_tally.EMPTY])
    assert client.export_voucher_index("Sample Co") == ["20260401"]
    assert client.export_voucher_index("Sample Co") == []


def test_unknown_ids_get_an_empty_envelope_and_exports_use_fixtures(mock_tally):
    client = TallyClient(mock_tally.url, timeout=5)
    results = dict(client.export_full_collections("Sample Co", only_vouchers=True))
    assert "sample-guid-101" in results["Vouchers"]
    assert client.last_export_failures == []
