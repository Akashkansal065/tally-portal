"""Hand-written queries name the Tally database "tally_sync"; a server that calls it something else gets its
own name swapped in."""
from app.core.database import use_configured_tally_database as swap


def test_the_written_name_becomes_the_configured_one():
    sql = "SELECT 1 FROM tally_sync.ledgers l JOIN tally_sync.account_groups g ON l.group_id = g.group_id"
    assert swap(sql, "acme_tally") == "SELECT 1 FROM acme_tally.ledgers l JOIN acme_tally.account_groups g ON l.group_id = g.group_id"
    assert swap("SELECT 1 FROM (tally_sync.vouchers v)", "acme_tally") == "SELECT 1 FROM (acme_tally.vouchers v)"


def test_other_names_and_plain_words_are_left_alone():
    for sql in ("SELECT 1 FROM my_tally_sync.ledgers", "SELECT 1 FROM `tally_sync`.`ledgers`",
                "SELECT 'tally_sync is the default' AS note", "SELECT x.tally_sync.y", "SELECT 1 FROM tally_portal.users"):
        assert swap(sql, "acme_tally") == sql


def test_the_usual_name_changes_nothing():
    sql = "SELECT 1 FROM tally_sync.ledgers"
    assert swap(sql, "tally_sync") == sql
