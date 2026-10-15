import pytest

from tally_client import decode_tally_reply

XML = "<ENVELOPE><NAME>Ünï ₹</NAME></ENVELOPE>"


@pytest.mark.parametrize("body", [
    XML.encode("utf-8"),
    XML.encode("utf-16"),               # little-endian BOM
    b"\xfe\xff" + XML.encode("utf-16-be"),
])
def test_reply_decoding(body):
    assert decode_tally_reply(body) == XML


def test_invalid_utf8_is_replaced_not_raised():
    assert "<A>" in decode_tally_reply(b"<A>\xff\xfa</A>")
