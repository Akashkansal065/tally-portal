import xml.etree.ElementTree as ET
from decimal import Decimal
import sys
import os

# Add backend and desktop-sync-agent to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../desktop-sync-agent")))

from app.services.tally_xml import x, clean_xml_str, xml_tag, wrap_tally_import_envelope
from app.routers.sync import check_tally_success, parse_tally_response_metrics
from app.schemas.voucher import VoucherEntryCreate, InventoryEntryCreate
from tally_client import escape_xml, parse_import_result


def test_tally_xml_control_char_stripping_and_escaping():
    """Verify XML 1.0 invalid control character removal and entity escaping."""
    raw = "Alpha & Beta <Gamma> \"Quotes\" 'Apos' \x00\x08\x0b\x0c\x1f Valid\t\n\r"
    escaped = x(raw)

    assert "\x00" not in escaped
    assert "\x08" not in escaped
    assert "\x0b" not in escaped
    assert "\x0c" not in escaped
    assert "\x1f" not in escaped
    assert "&amp;" in escaped
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "&quot;" in escaped
    assert "&apos;" in escaped
    assert "Valid\t\n\r" in escaped


def test_tally_xml_envelope_validity():
    """Ensure wrap_tally_import_envelope produces valid XML parsable by ElementTree."""
    payload = wrap_tally_import_envelope(
        company_name="M/S ABC & Sons",
        message_content=f"<LEDGER><NAME>{x('Test & Partner <Pvt> \"Ltd\"')}</NAME></LEDGER>"
    )
    root = ET.fromstring(payload)
    assert root.tag == "ENVELOPE"
    cmp_elem = root.find(".//STATICVARIABLES/SVCURRENTCOMPANY")
    assert cmp_elem is not None
    assert cmp_elem.text == "M/S ABC & Sons"
    
    name_elem = root.find(".//LEDGER/NAME")
    assert name_elem is not None
    assert name_elem.text == "Test & Partner <Pvt> \"Ltd\""


def test_tally_client_escape_xml():
    """Test desktop agent's escape_xml helper."""
    assert escape_xml(None) == ""
    assert escape_xml(12345) == "12345"
    s = "Item & Co <100%> \x01\x1e"
    res = escape_xml(s)
    assert res == "Item &amp; Co &lt;100%&gt; "


def test_tally_client_parse_import_result():
    """Test parse_import_result handling all response branches (F5)."""
    # 1. Empty response
    ok, msg = parse_import_result("")
    assert not ok
    assert "Empty response" in msg

    # 2. Fatal EXCEPTION envelope
    exc_xml = "<EXCEPTION>Company 'XYZ' is closed or not available</EXCEPTION>"
    ok, msg = parse_import_result(exc_xml)
    assert not ok
    assert "Tally exception:" in msg

    # 3. LINEERROR in response
    line_err_xml = """<RESPONSE>
        <LINEERROR>Ledger 'Bank Account' does not exist</LINEERROR>
    </RESPONSE>"""
    ok, msg = parse_import_result(line_err_xml)
    assert not ok
    assert "Bank Account" in msg

    # 4. ERRORS > 0
    err_count_xml = """<RESPONSE>
        <CREATED>0</CREATED>
        <ERRORS>1</ERRORS>
    </RESPONSE>"""
    ok, msg = parse_import_result(err_count_xml)
    assert not ok
    assert "1 error(s)" in msg

    # 5. EXCEPTIONS > 0
    exc_count_xml = """<RESPONSE>
        <CREATED>1</CREATED>
        <EXCEPTIONS>1</EXCEPTIONS>
    </RESPONSE>"""
    ok, msg = parse_import_result(exc_count_xml)
    assert not ok
    assert "1 exception(s)" in msg

    # 6. Multi-object batch acceptance (CREATED > 1)
    batch_xml = """<RESPONSE>
        <CREATED>3</CREATED>
        <ALTERED>0</ALTERED>
        <ERRORS>0</ERRORS>
        <EXCEPTIONS>0</EXCEPTIONS>
    </RESPONSE>"""
    ok, msg = parse_import_result(batch_xml)
    assert ok
    assert msg == "OK"

    # 7. Resend of existing record (IGNORED: 1)
    ignored_xml = """<RESPONSE>
        <CREATED>0</CREATED>
        <IGNORED>1</IGNORED>
        <ERRORS>0</ERRORS>
    </RESPONSE>"""
    ok, msg = parse_import_result(ignored_xml)
    assert ok
    assert msg == "OK"

    # 8. All counts zero
    zero_xml = """<RESPONSE>
        <CREATED>0</CREATED>
        <ALTERED>0</ALTERED>
        <ERRORS>0</ERRORS>
    </RESPONSE>"""
    ok, msg = parse_import_result(zero_xml)
    assert not ok
    assert "Tally changed nothing" in msg


def test_sync_router_check_tally_success():
    """Verify backend check_tally_success correctly parses multi-counts and rejects failures."""
    assert not check_tally_success("")
    assert not check_tally_success("<LINEERROR>Failed</LINEERROR>")
    assert not check_tally_success("<EXCEPTION>Memory Fault</EXCEPTION>")
    assert not check_tally_success("<CREATED>2</CREATED><ERRORS>1</ERRORS>")
    assert not check_tally_success("<ALTERED>1</ALTERED><EXCEPTIONS>2</EXCEPTIONS>")
    
    assert check_tally_success("<CREATED>5</CREATED><ERRORS>0</ERRORS>")
    assert check_tally_success("<ALTERED>2</ALTERED>")
    assert check_tally_success("<DELETED>1</DELETED>")
    assert check_tally_success("<CANCELLED>1</CANCELLED>")
    assert check_tally_success("<IGNORED>1</IGNORED>")

    # Read but nothing changed: stays queued for retry instead of being marked processed
    assert not check_tally_success("<STATUS>1</STATUS>")
    assert not check_tally_success("<CREATED>0</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS>")


def test_sync_router_parse_tally_response_metrics():
    """Verify parse_tally_response_metrics extracts structured metrics."""
    resp = """<RESPONSE>
        <CREATED>2</CREATED>
        <ALTERED>1</ALTERED>
        <ERRORS>0</ERRORS>
        <EXCEPTIONS>0</EXCEPTIONS>
        <VCHNUMBER>INV-2026-001</VCHNUMBER>
    </RESPONSE>"""
    metrics = parse_tally_response_metrics(resp)
    assert metrics["status"] == "SUCCESS"
    assert metrics["created"] == 2
    assert metrics["altered"] == 1
    assert metrics["vchnumber"] == "INV-2026-001"
    assert metrics["errors"] == 0

    err_resp = """<RESPONSE>
        <LINEERROR>Ledger not found</LINEERROR>
        <ERRORS>1</ERRORS>
    </RESPONSE>"""
    metrics_err = parse_tally_response_metrics(err_resp)
    assert metrics_err["status"] == "FAILED"
    assert "Ledger not found" in metrics_err["error_summary"]


def test_voucher_entry_paise_quantization():
    """Verify debit/credit amounts and inventory amounts are quantized to paise (F10)."""
    entry = VoucherEntryCreate(
        ledger_id=1,
        debit_amount=Decimal("123.456"),
        credit_amount=Decimal("0.004")
    )
    assert entry.debit_amount == Decimal("123.46")
    assert entry.credit_amount == Decimal("0.00")

    entry_half_up = VoucherEntryCreate(
        ledger_id=2,
        debit_amount="10.005",
        credit_amount="10.004"
    )
    assert entry_half_up.debit_amount == Decimal("10.01")
    assert entry_half_up.credit_amount == Decimal("10.00")

    inv = InventoryEntryCreate(
        stock_item_id=10,
        quantity=Decimal("5.0"),
        rate=Decimal("19.99"),
        amount=Decimal("99.954")
    )
    assert inv.amount == Decimal("99.95")


def test_bad_amounts_are_validation_errors_not_server_errors():
    """Text, NaN, infinity and out-of-range numbers are rejected as invalid input (422), never a crash (500)."""
    import pytest
    from pydantic import ValidationError

    for bad in ("abc", "NaN", "Infinity", "1e400", float("nan")):
        with pytest.raises(ValidationError):
            VoucherEntryCreate(ledger_id=1, debit_amount=bad)
        with pytest.raises(ValidationError):
            InventoryEntryCreate(stock_item_id=1, quantity=1, rate=1, amount=bad)


if __name__ == "__main__":
    tests = [
        test_tally_xml_control_char_stripping_and_escaping,
        test_tally_xml_envelope_validity,
        test_tally_client_escape_xml,
        test_tally_client_parse_import_result,
        test_sync_router_check_tally_success,
        test_sync_router_parse_tally_response_metrics,
        test_voucher_entry_paise_quantization,
        test_bad_amounts_are_validation_errors_not_server_errors,
    ]
    for t in tests:
        t()
        print(f"✅ PASSED: {t.__name__}")
    print(f"\n🎉 All {len(tests)} test suites passed successfully!")


def _json_import_result(**counts):
    import json
    result = {"created": 0, "altered": 0, "deleted": 0, "ignored": 0, "errors": 0, "cancelled": 0, "exceptions": 0}
    result.update(counts)
    return json.dumps({"status": "1", "data": {"import_result": result}}, indent=4)


def test_tally_json_rejections_are_not_success():
    """Tally answers status "1" even when it rejects an object; only the counters tell."""
    from app.routers.sync import check_tally_json_success, tally_json_failure_reason

    assert check_tally_json_success(_json_import_result(created=1))
    assert check_tally_json_success(_json_import_result(altered=1))
    assert check_tally_json_success(_json_import_result(deleted=1))
    # "Cannot be deleted!" / "Item does not exist!" come back as errors, a missing parent as exceptions
    assert not check_tally_json_success(_json_import_result(errors=1))
    assert not check_tally_json_success(_json_import_result(exceptions=1))
    assert not check_tally_json_success(_json_import_result())
    assert not check_tally_json_success("")
    assert not check_tally_json_success("<RESPONSE>Unknown Request, cannot be processed</RESPONSE>")
    assert "1 error(s)" in tally_json_failure_reason(_json_import_result(errors=1))


def test_group_xml_rename_and_tally_field_names():
    from types import SimpleNamespace
    from app.routers.sync import build_group_xml_envelope

    group = SimpleNamespace(
        name="North Debtors", is_addable=True, is_revenue=False, is_deemed_positive=True,
        affects_gross_profit=False, is_subledger=False, is_billwise_on=True,
        used_for_calculation=True, method_to_allocate="Appropriate by Qty",
        sort_position=1000, gst_details=[], alias_name="ND", language_id=1033,
    )
    node = lambda xml: ET.fromstring(xml.replace("&#4;", "")).find(".//GROUP")

    # A rename addresses the name Tally still has and carries the new one in the body
    renamed = node(build_group_xml_envelope(group, "Sundry Debtors", "ABC", "Alter", tally_name="Old Debtors"))
    assert renamed.get("NAME") == "Old Debtors"
    assert renamed.findtext("NAME") == "North Debtors"

    created = node(build_group_xml_envelope(group, "Sundry Debtors", "ABC", "Create"))
    assert created.get("NAME") == "North Debtors"
    assert created.findtext("PARENT") == "Sundry Debtors"
    assert created.findtext("BASICGROUPISCALCULABLE") == "Yes"
    assert created.findtext("ADDLALLOCTYPE") == "Appropriate by Qty"
    assert created.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert [n.text for n in created.findall("LANGUAGENAME.LIST/NAME.LIST/NAME")] == ["North Debtors", "ND"]

    # Tally's own spellings for "top level" and "no allocation", control character included
    group.method_to_allocate = "Not Applicable"
    top_level = build_group_xml_envelope(group, "", "ABC", "Alter")
    assert "<PARENT>&#4; Primary</PARENT>" in top_level
    assert "<ADDLALLOCTYPE>&#4; Not Applicable</ADDLALLOCTYPE>" in top_level

    deleted = node(build_group_xml_envelope(None, "", "ABC", "Delete", tally_name="Old Debtors"))
    assert deleted.attrib == {"NAME": "Old Debtors", "Action": "Delete"}
    assert [child.tag for child in deleted] == ["NAME"]


def test_group_import_primary_marker_and_nature():
    from types import SimpleNamespace
    from app.services.tally_xml_importer import tally_parent_name, apply_group_extra_data

    # Tally's top-level marker is "\x04 Primary"; sanitising leaves " Primary"
    assert tally_parent_name(" Primary") is None
    assert tally_parent_name("") is None
    assert tally_parent_name(None) is None
    assert tally_parent_name(" Current Assets ") == "Current Assets"

    group = SimpleNamespace(nature="Asset")
    apply_group_extra_data(group, {"is_revenue": True, "is_deemed_positive": False, "is_subledger": True})
    assert group.nature == "Income"
    assert group.is_subledger is True

    # Without both flags the nature is left alone
    group = SimpleNamespace(nature="Liability")
    apply_group_extra_data(group, {"is_revenue": False})
    assert group.nature == "Liability"


def test_group_members_from_tally_export():
    """The blocker list reads Tally's own verdict on what can be deleted, and skips the CMPINFO counters."""
    from app.services.group_deletion import _parse_members

    resp = """<ENVELOPE><BODY><DESC><CMPINFO><GROUP>0</GROUP><LEDGER>0</LEDGER></CMPINFO></DESC><DATA><COLLECTION>
      <GROUP NAME="Sundry Debtors" RESERVEDNAME="Sundry Debtors"><PARENT TYPE="String">Current Assets</PARENT><CANDELETE TYPE="Logical">No</CANDELETE></GROUP>
      <GROUP NAME="North Debtors" RESERVEDNAME=""><PARENT TYPE="String">Sundry Debtors</PARENT><CANDELETE TYPE="Logical">Yes</CANDELETE></GROUP>
      <GROUP NAME="Top Level" RESERVEDNAME=""><PARENT TYPE="String">&#4; Primary</PARENT><CANDELETE TYPE="Logical">Yes</CANDELETE></GROUP>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    groups = _parse_members(resp, "GROUP")
    assert set(groups) == {"sundry debtors", "north debtors", "top level"}
    assert groups["sundry debtors"]["reserved"] and not groups["sundry debtors"]["can_delete"]
    assert groups["north debtors"] == {"name": "North Debtors", "parent": "Sundry Debtors", "can_delete": True, "reserved": False}
    assert groups["top level"]["parent"] is None
    assert _parse_members("not xml", "GROUP") is None


def _ledger_for_xml(**overrides):
    from types import SimpleNamespace
    fields = dict(
        name="Acme Traders", gstin="27AAAAA0000A1Z5", pan_number=None, state="Maharashtra", country="India",
        pincode="400056", address="#89 Arcade, S.V. Road | Mobile: 9900000001", mobile=None, contact_person="Asha",
        phone="022-1234567", email="a@example.com", aadhar_number=None, credit_limit=Decimal("100000"),
        credit_period_days=30, is_billwise_on=True, gst_registration_type="Regular", ledger_type=None,
        tax_classification_name=None, opening_balance=Decimal("5000.00"), opening_balance_type="Dr",
        gst_applicable_from=None, is_bank_account=False,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _ledger_node(xml: str):
    return ET.fromstring(xml.replace("UDF:", "")).find(".//LEDGER")


def test_ledger_xml_opening_balance_sign_and_details():
    """Tally reads a negative opening balance as debit and an unsigned one as credit."""
    from app.routers.sync import build_ledger_xml_envelope

    debit = _ledger_node(build_ledger_xml_envelope(_ledger_for_xml(), "Sundry Debtors", "ABC", "Create"))
    assert debit.findtext("OPENINGBALANCE") == "-5000.00"
    assert debit.findtext("LEDGERMOBILE") == "9900000001"
    assert debit.findtext("INCOMETAXNUMBER") == "AAAAA0000A"
    assert debit.findtext("PARTYGSTIN") == "27AAAAA0000A1Z5"
    mailing = debit.findall("LEDMAILINGDETAILS.LIST")
    assert len(mailing) == 1
    assert mailing[0].findtext("APPLICABLEFROM") == "20250401"
    assert [a.text for a in mailing[0].findall("ADDRESS.LIST/ADDRESS")] == ["#89 Arcade", "S.V. Road"]

    credit = _ledger_node(build_ledger_xml_envelope(
        _ledger_for_xml(opening_balance=Decimal("7000.00"), opening_balance_type="Cr"), "Sundry Creditors", "ABC", "Create"))
    assert credit.findtext("OPENINGBALANCE") == "7000.00"


def test_ledger_xml_rename_delete_and_bank_details():
    from types import SimpleNamespace
    from app.routers.sync import build_ledger_xml_envelope

    # A rename addresses the name Tally still has and carries the new one in <NAME>
    renamed = _ledger_node(build_ledger_xml_envelope(_ledger_for_xml(), "Sundry Debtors", "ABC", "Alter", tally_name="Old Name"))
    assert renamed.get("NAME") == "Old Name"
    assert renamed.findtext("NAME") == "Acme Traders"

    deleted = _ledger_node(build_ledger_xml_envelope(_ledger_for_xml(), "Sundry Debtors", "ABC", "Delete", tally_name="Old Name"))
    assert deleted.attrib == {"NAME": "Old Name", "ACTION": "Delete"}
    assert [child.tag for child in deleted] == ["NAME"]

    account = SimpleNamespace(account_number="9876543210", ifsc_code="HDFC0000002", bank_name="HDFC Bank",
                              favouring_name=None, account_holder_name="Acme", ref_id="Primary", is_default=True,
                              transaction_type="e-Fund Transfer")
    party = _ledger_for_xml()
    party.__dict__["bank_details"] = [account]
    payment = _ledger_node(build_ledger_xml_envelope(party, "Sundry Creditors", "ABC", "Create")).find("PAYMENTDETAILS.LIST")
    assert payment.findtext("ACCOUNTNUMBER") == "9876543210"

    bank = _ledger_for_xml(is_bank_account=True, bank_account_no="1234567890", bank_ifsc="HDFC0000001")
    bank.__dict__["bank_details"] = [account]
    bank_node = _ledger_node(build_ledger_xml_envelope(bank, "Bank Accounts", "ABC", "Create"))
    assert bank_node.findtext("BANKDETAILS") == "1234567890"
    assert bank_node.find("PAYMENTDETAILS.LIST") is None


def test_unit_xml_never_sends_a_formal_name_equal_to_the_symbol():
    """Tally hangs behind an internal-error dialog when a unit's formal name duplicates its own name."""
    from app.routers.sync import build_unit_xml, compound_unit_name

    assert "<ORIGINALNAME>" not in build_unit_xml("Nos", "Create", formal_name="Nos")
    assert "<ORIGINALNAME>" not in build_unit_xml("Nos", "Create", formal_name=" nos ")
    assert "<ORIGINALNAME>" not in build_unit_xml("Nos", "Create", formal_name=None)
    simple = ET.fromstring(build_unit_xml("Nos", "Alter", target_name="Numbers", formal_name="Numbers Formal", decimal_places=2))
    assert simple.get("NAME") == "Numbers"
    assert (simple.findtext("NAME"), simple.findtext("ORIGINALNAME"), simple.findtext("ISSIMPLEUNIT"), simple.findtext("DECIMALPLACES")) == \
        ("Nos", "Numbers Formal", "Yes", "2")

    # Tally derives a compound unit's name from its parts
    assert compound_unit_name("Kg", Decimal("1000.0000"), "gm") == "Kg of 1000 gm"
    assert compound_unit_name("Box", Decimal("2.5000"), "Kg") == "Box of 2.5 Kg"
    compound = ET.fromstring(build_unit_xml("Kg of 500 gm", "Alter", target_name="Kg of 1000 gm", base_symbol="Kg",
                                            additional_symbol="gm", conversion=Decimal("500")))
    assert compound.get("NAME") == "Kg of 1000 gm"
    assert (compound.findtext("NAME"), compound.findtext("BASEUNITS"), compound.findtext("ADDITIONALUNITS"), compound.findtext("CONVERSION")) == \
        ("Kg of 500 gm", "Kg", "gm", "500")
    assert compound.find("DECIMALPLACES") is None and compound.find("ORIGINALNAME") is None

    deleted = ET.fromstring(build_unit_xml("Nos", "Delete"))
    assert deleted.attrib == {"NAME": "Nos", "Action": "Delete"}


def test_stock_group_xml_rename_top_level_and_aliases():
    from app.routers.sync import build_stock_group_xml

    top = build_stock_group_xml("Laptops", "Alter", target_name="Notebooks", parent_name=None, aliases=["LT", " ", "laptops"])
    # Tally's own marker for the top level, control character included
    assert "<PARENT>&#4; Primary</PARENT>" in top
    node = ET.fromstring(top.replace("&#4;", ""))
    assert node.get("NAME") == "Notebooks"
    assert node.findtext("NAME") == "Laptops"
    assert node.findtext("ISADDABLE") == "Yes"
    # The name first, then real aliases only (blank ones and the name itself are dropped)
    assert [n.text for n in node.findall("LANGUAGENAME.LIST/NAME.LIST/NAME")] == ["Laptops", "LT"]

    child = ET.fromstring(build_stock_group_xml("Gaming", "Create", parent_name="Laptops"))
    assert child.findtext("PARENT") == "Laptops"
    assert "Primary" in build_stock_group_xml("Gaming", "Create", parent_name=" Primary")

    deleted = ET.fromstring(build_stock_group_xml("Laptops", "Delete"))
    assert deleted.attrib == {"NAME": "Laptops", "Action": "Delete"}
    assert [c.tag for c in deleted] == ["NAME"]


def _stock_item_for_xml(**overrides):
    from types import SimpleNamespace
    ns = SimpleNamespace
    fields = dict(
        name="Steel Rod", unit=ns(symbol="Kg", name="Kg"), alt_unit=ns(symbol="gm", name="gm"),
        alt_unit_conversion=Decimal("1000.0000"), group=ns(name="Metals"), category=ns(name="Hardware"),
        tracking_type="None", description="12mm", gst_rate_percent=Decimal("18.00"), hsn_code="7214",
        opening_qty=Decimal("0"), opening_rate=Decimal("0"),
        aliases=[ns(alias="SR-12"), ns(alias=" steel rod ")],
        opening_balances=[ns(godown=ns(name="Central Warehouse"), batch_name=None, quantity=Decimal("40.000"),
                             rate=Decimal("50.00"), amount=Decimal("2000.00"))],
    )
    fields.update(overrides)
    return ns(**fields)


def test_stock_item_xml_sends_everything_tally_needs():
    from app.routers.sync import build_stock_item_xml

    xml = build_stock_item_xml(_stock_item_for_xml(), "Alter", tally_name="Steel Bar")
    node = ET.fromstring(xml.replace("&#4;", ""))
    # A rename addresses the name Tally still has
    assert node.get("NAME") == "Steel Bar" and node.findtext("NAME") == "Steel Rod"
    assert (node.findtext("PARENT"), node.findtext("CATEGORY"), node.findtext("BASEUNITS")) == ("Metals", "Hardware", "Kg")
    # "1000 gm = 1 Kg": CONVERSION counts alternate units, DENOMINATOR base units
    assert (node.findtext("ADDITIONALUNITS"), node.findtext("CONVERSION"), node.findtext("DENOMINATOR")) == ("gm", "1000", "1")
    # The pair is sent as kept, so a ratio that has no exact decimal (1 box = 3 pcs) is not rounded
    third = ET.fromstring(build_stock_item_xml(_stock_item_for_xml(alt_unit_conversion=Decimal("1"), alt_unit_denominator=Decimal("3")), "Alter").replace("&#4;", ""))
    assert (third.findtext("CONVERSION"), third.findtext("DENOMINATOR")) == ("1", "3")
    assert [n.text for n in node.findall("LANGUAGENAME.LIST/NAME.LIST/NAME")] == ["Steel Rod", "SR-12"]
    assert node.findtext("HSNDETAILS.LIST/HSNCODE") == "7214"
    rates = {r.findtext("GSTRATEDUTYHEAD"): r.findtext("GSTRATE") for r in node.findall("GSTDETAILS.LIST/STATEWISEDETAILS.LIST/RATEDETAILS.LIST")}
    assert rates == {"IGST": "18", "CGST": "9", "SGST/UTGST": "9"}
    # Opening stock goes on the batch, as a debit (negative value)
    batch = node.find("BATCHALLOCATIONS.LIST")
    assert (batch.findtext("GODOWNNAME"), batch.findtext("BATCHNAME"), batch.findtext("OPENINGBALANCE"), batch.findtext("OPENINGVALUE")) == \
        ("Central Warehouse", "Primary Batch", "40 Kg", "-2000.00")
    assert (node.findtext("OPENINGBALANCE"), node.findtext("OPENINGVALUE")) == ("40 Kg", "-2000.00")


def test_stock_item_xml_clears_opening_stock_and_handles_bare_items():
    from app.routers.sync import build_stock_item_xml

    bare = _stock_item_for_xml(alt_unit=None, alt_unit_conversion=None, group=None, category=None, aliases=[],
                               opening_balances=[], gst_rate_percent=Decimal("0"), hsn_code=None, description=None)
    xml = build_stock_item_xml(bare, "Alter")
    assert "<PARENT>&#4; Primary</PARENT>" in xml
    node = ET.fromstring(xml.replace("&#4;", ""))
    # An empty batch list is what removes opening stock in Tally; leaving it out would keep the old stock
    assert node.find("BATCHALLOCATIONS.LIST") is not None and len(node.find("BATCHALLOCATIONS.LIST")) == 0
    assert (node.findtext("OPENINGBALANCE") or "") == ""
    assert node.find("GSTDETAILS.LIST") is None and node.find("HSNDETAILS.LIST") is None
    # An item with no GST details must not have GST switched on in Tally by an unrelated edit
    assert node.find("GSTAPPLICABLE") is None and node.find("GSTTYPEOFSUPPLY") is None
    assert node.find("LANGUAGENAME.LIST/LANGUAGEID") is None
    # An edit that does not touch HSN or GST leaves an item's tax entries alone
    untouched = ET.fromstring(build_stock_item_xml(_stock_item_for_xml(), "Alter", include_gst=False).replace("&#4;", ""))
    assert untouched.find("GSTDETAILS.LIST") is None and untouched.find("HSNDETAILS.LIST") is None and untouched.find("GSTAPPLICABLE") is None
    # Batch tracking read from Tally on import is sent back
    assert ET.fromstring(build_stock_item_xml(_stock_item_for_xml(is_batch_wise=True), "Alter").replace("&#4;", "")).findtext("ISBATCHWISEON") == "Yes"

    # Tally's "Not Applicable" markers, however they were stored here, go back as markers and never as names
    from types import SimpleNamespace
    marked = _stock_item_for_xml(category=SimpleNamespace(name=" Not Applicable"), unit=SimpleNamespace(symbol="Not Applicable", name="Not Applicable"),
                                 alt_unit=None, opening_balances=[])
    marked_xml = build_stock_item_xml(marked, "Alter")
    assert "<CATEGORY>&#4; Not Applicable</CATEGORY>" in marked_xml and "<BASEUNITS>&#4; Not Applicable</BASEUNITS>" in marked_xml

    # No stored godown rows: the item's own opening quantity goes to the default batch
    simple = _stock_item_for_xml(opening_balances=[], opening_qty=Decimal("10"), opening_rate=Decimal("20"))
    batch = ET.fromstring(build_stock_item_xml(simple, "Create").replace("&#4;", "")).find("BATCHALLOCATIONS.LIST")
    assert (batch.findtext("GODOWNNAME"), batch.findtext("OPENINGBALANCE"), batch.findtext("OPENINGVALUE")) == ("Main Location", "10 Kg", "-200.00")

    deleted = ET.fromstring(build_stock_item_xml(bare, "Delete", tally_name="Old Name"))
    assert deleted.attrib == {"NAME": "Old Name", "Action": "Delete"}
