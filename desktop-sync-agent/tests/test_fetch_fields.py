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
