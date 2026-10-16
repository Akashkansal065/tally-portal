"""WS-10: what the agent asks Tally for. Each family lists the tags the backend importer reads and stores
(docs/Export Field Coverage Matrix.md); a tag the importer ignores is not requested."""
from tally_client import VOUCHER_FETCH


def tags(fetch):
    return set(fetch.split(","))


def test_voucher_header_fields_are_requested_once_each():
    asked = VOUCHER_FETCH.split(",")
    assert len(asked) == len(set(asked))
    for tag in ("ISPOSTDATED", "ISINVOICE", "PERSISTEDVIEW", "EFFECTIVEDATE", "REFERENCE", "REFERENCEDATE", "PLACEOFSUPPLY",
                "BASICBUYERNAME", "BASICBUYERADDRESS.LIST", "CONSIGNEEMAILINGNAME", "CONSIGNEEADDRESS.LIST", "BASICORDERREF",
                "BASICSHIPDELIVERYNOTE", "IRN", "IRNACKNO", "IRNACKDATE", "IRNQRCODE", "EWAYBILLDETAILS.LIST"):
        assert tag in asked, tag


def test_the_original_voucher_fields_are_still_requested():
    for tag in ("GUID", "MASTERID", "REMOTEALTGUID", "ALTERID", "VOUCHERTYPENAME", "VOUCHERNUMBER", "DATE", "ISCANCELLED",
                "ISOPTIONAL", "ALLLEDGERENTRIES.LIST", "INVENTORYENTRIES.LIST", "ALLINVENTORYENTRIES.LIST"):
        assert tag in tags(VOUCHER_FETCH), tag



def test_ledger_fields_are_requested():
    from tally_client import LEDGER_FETCH
    asked = tags(LEDGER_FETCH)
    for tag in ("CREDITLIMIT", "BILLCREDITPERIOD", "LEDGERCONTACT", "LEDGERMOBILE", "EMAIL", "EMAILCC", "WEBSITE",
                "LEDGERFAX", "COUNTRYNAME", "TAXCLASSIFICATIONNAME", "MSMEREGISTRATIONDETAILS.LIST",
                "LOWERDEDUCTION.LIST", "HSNDETAILS.LIST", "LEDMULTIADDRESSLIST.LIST", "OPENINGBALANCE", "CLOSINGBALANCE"):
        assert tag in asked, tag
    assert len(LEDGER_FETCH.split(",")) == len(asked)


def test_stock_item_fields_are_requested_and_unparsed_lists_are_not():
    from tally_client import STOCK_ITEM_FETCH
    asked = tags(STOCK_ITEM_FETCH)
    for tag in ("HSNDETAILS.LIST", "INFGSTHSNCODE", "INFGSTIGSTRATE", "LANGUAGENAME.LIST", "BATCHALLOCATIONS.LIST", "ALTERID"):
        assert tag in asked, tag
    # the importer reads none of these yet: asking would only make the export bigger
    for tag in ("MULTICOMPONENTLIST.LIST", "FULLPRICELIST.LIST", "MRPDETAILS.LIST", "REORDERBASE", "PARTNUMBER"):
        assert tag not in asked, tag
    assert len(STOCK_ITEM_FETCH.split(",")) == len(asked)
