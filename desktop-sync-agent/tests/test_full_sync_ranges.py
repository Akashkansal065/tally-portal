"""A full voucher sync is cut into date ranges: each range is checked, the position is saved after each, a
failure or a restart carries on from there, and a Tally that ignores date ranges gets one export instead."""
import agent as agent_module
from tally_client import voucher_dates

ALPHA = {"guid": "guid-alpha", "name": "Alpha"}


def voucher(number, day):
    return (f'<VOUCHER REMOTEID="v{number}"><DATE TYPE="Date">{day}</DATE><VOUCHERNUMBER>{number}</VOUCHERNUMBER>'
            f"<ALLLEDGERENTRIES.LIST><BANKALLOCATIONS.LIST><DATE>19990101</DATE></BANKALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST></VOUCHER>")


def export(days):
    return "<ENVELOPE><BODY><DATA><COLLECTION>" + "".join(voucher(n, d) for n, d in days) + "</COLLECTION></DATA></BODY></ENVELOPE>"


class Tally:
    """Holds vouchers as (number, date). honours: which range requests it applies; the rest return everything."""

    def __init__(self, vouchers, honours=("sv", "filter"), exclusive_end=False):
        self.vouchers = list(vouchers)
        self.honours = honours
        self.exclusive_end = exclusive_end     # a Tally that leaves out the last day of a range
        self.fail_ranges = set()               # (from, to) that Tally does not answer
        self.calls = []
        self.last_export_failures = []

    def check_health(self):
        return True, "ok"

    def get_open_companies(self):
        return [ALPHA]

    def export_full_collections(self, company, min_alter_id=0, min_voucher_alter_id=None, skip_vouchers=False, only_vouchers=False):
        self.last_export_failures = []
        out = []
        if not only_vouchers and min_alter_id == 0:
            out.append(("Ledgers", "<ENVELOPE><LEDGER/><VOUCHERNUMBER>0</VOUCHERNUMBER></ENVELOPE>"))
        if not skip_vouchers and (min_voucher_alter_id in (None, 0)) and min_alter_id == 0:
            self.calls.append("whole")
            out.append(("Vouchers", export(self.vouchers)))
        return out

    def export_voucher_index(self, company):
        self.calls.append("index")
        return [d for _, d in self.vouchers]

    def export_vouchers_between(self, company, date_from, date_to, method="sv"):
        self.calls.append((method, date_from, date_to))
        if (date_from, date_to) in self.fail_ranges:
            return None
        if method not in self.honours:
            return export(self.vouchers)
        return export([(n, d) for n, d in self.vouchers
                       if date_from <= d and (d < date_to if self.exclusive_end else d <= date_to)])


class Cloud:
    auth_halt_reason = ""
    company_guid = ""

    def __init__(self):
        self.pushed = []          # (label or "vouchers", voucher numbers, forced)
        self.fail_on = set()      # voucher numbers whose push fails
        self.reports = []

    def get_last_alter_id(self):
        # Once anything has arrived the server holds a watermark, so an ordinary cycle asks only for changes
        return (5, 5) if self.pushed else (0, 0)

    def push_inbound_xml(self, xml, company_name=None, force=False):
        numbers = [int(x.split("</VOUCHERNUMBER>")[0]) for x in xml.split("<VOUCHERNUMBER>")[1:]]
        if self.fail_on & set(numbers):
            return False, {"error": "server down"}
        self.pushed.append((numbers, force))
        return True, {"imported_vouchers": len(numbers)}

    def report_state(self, reports):
        self.reports.append(reports)
        return True

    def all_numbers(self):
        return sorted(n for numbers, _ in self.pushed for n in numbers if n)   # 0 marks the masters push


def make_agent(tmp_path, tally, cloud):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = tally, cloud
    a.config.companies = [dict(ALPHA)]
    a.config.company_guid, a.config.company_name = ALPHA["guid"], ALPHA["name"]
    a.active_company_guid, a.active_company_name = ALPHA["guid"], ALPHA["name"]
    a.tally_connected = True
    return a


def many_vouchers(count=2400, per_day=40):
    """count vouchers spread over consecutive days of April to June 2025."""
    days = [f"2025{m:02d}{d:02d}" for m in (4, 5, 6) for d in range(1, 29)]
    return [(n + 1, days[(n // per_day) % len(days)]) for n in range(count)]


def range_calls(tally):
    return [c for c in tally.calls if isinstance(c, tuple)]


def test_ranges_cover_every_voucher_once_and_never_split_a_day():
    dates = [d for _, d in many_vouchers()]
    ranges = agent_module.plan_voucher_ranges(dates, per_range=500)

    assert sum(count for _, _, count in ranges) == len(dates)
    assert all(start <= end for start, end, _ in ranges)
    assert all(ranges[i][1] < ranges[i + 1][0] for i in range(len(ranges) - 1))      # no overlap, in order
    assert all(count >= 500 for _, _, count in ranges[:-1])
    assert agent_module.plan_voucher_ranges(["20250401"] * 1300, per_range=500) == [["20250401", "20250401", 1300]]
    assert agent_module.plan_voucher_ranges([]) == []


def test_a_vouchers_own_date_is_read_not_one_inside_its_entries():
    assert voucher_dates(export([(1, "20250401"), (2, "20250402")])) == ["20250401", "20250402"]
    inner_first = "<ENVELOPE><VOUCHER><ALLLEDGERENTRIES.LIST><DATE>19990101</DATE></ALLLEDGERENTRIES.LIST><DATE>20250403</DATE></VOUCHER></ENVELOPE>"
    assert voucher_dates(inner_first) == ["20250403"]


def test_a_full_sync_pulls_vouchers_range_by_range(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)

    assert "whole" not in tally.calls                                   # never everything at once
    assert len(range_calls(tally)) >= 4
    assert cloud.all_numbers() == list(range(1, 2401))                   # every voucher, once
    assert agent.config.full_sync_cursors == {}                          # finished: nothing left to carry on
    assert agent._voucher_range_method == "sv"


def test_a_small_company_is_exported_in_one_go(tmp_path):
    tally, cloud = Tally(many_vouchers(count=40)), Cloud()
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)

    assert tally.calls.count("whole") == 1 and range_calls(tally) == []
    assert cloud.all_numbers() == list(range(1, 41)) and agent.config.full_sync_cursors == {}


def test_a_tally_that_ignores_date_ranges_gets_one_export_instead(tmp_path):
    tally, cloud = Tally(many_vouchers(), honours=()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)

    assert [c[0] for c in range_calls(tally)] == ["sv", "filter"]        # both requests tried on the first range
    assert tally.calls.count("whole") == 1
    assert cloud.all_numbers() == list(range(1, 2401))                   # nothing pushed twice, nothing missing
    assert agent._voucher_ranges_work is False and agent.config.full_sync_cursors == {}

    agent.sync_inbound_cycle(is_incremental=False)                       # and it is not tried again
    assert len(range_calls(tally)) == 2


def test_the_second_request_is_used_when_only_it_is_honoured(tmp_path):
    tally, cloud = Tally(many_vouchers(), honours=("filter",)), Cloud()
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)

    assert agent._voucher_range_method == "filter" and "whole" not in tally.calls
    assert [c[0] for c in range_calls(tally)].count("sv") == 1           # tried once, then never again
    assert cloud.all_numbers() == list(range(1, 2401))


def test_a_range_that_loses_its_last_day_is_not_trusted(tmp_path):
    tally, cloud = Tally(many_vouchers(), exclusive_end=True), Cloud()
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)

    assert tally.calls.count("whole") == 1 and agent._voucher_ranges_work is False
    assert cloud.all_numbers() == list(range(1, 2401))


def test_a_failed_range_is_carried_on_from_in_the_next_cycle(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    cloud.fail_on = {1500}                                               # the server fails on the third range

    agent.sync_inbound_cycle(is_incremental=False)

    cursor = agent.config.full_sync_cursors["guid-alpha"]
    done = cursor["next"]
    assert 0 < done < len(cursor["ranges"]) and 1500 not in cloud.all_numbers()
    assert agent.config.inbound_retry_floors == {}                       # the saved position is the retry, not "everything again"
    assert agent._last_company_ok is False

    cloud.fail_on = set()
    calls_before = len(range_calls(tally))
    agent.sync_inbound_cycle(is_incremental=True)                        # an ordinary cycle picks it up

    assert range_calls(tally)[calls_before][1] == cursor["ranges"][done][0]   # from the failed range, not the first
    assert cloud.all_numbers() == list(range(1, 2401)) and "whole" not in tally.calls
    assert agent.config.full_sync_cursors == {} and agent._last_company_ok is True


def test_ranges_are_the_size_set_in_settings(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    assert agent.config.vouchers_per_range == 50                         # the size unless Settings says otherwise
    agent.config.vouchers_per_range = 200
    cloud.fail_on = {1}                                                  # stop at once, to read the plan

    agent.sync_inbound_cycle(is_incremental=False)

    cursor = agent.config.full_sync_cursors["guid-alpha"]
    assert cursor["per_range"] == 200 and [count for _, _, count in cursor["ranges"]] == [200] * 12


def test_changing_the_size_plans_the_rest_again_and_keeps_what_is_done(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    agent.config.vouchers_per_range = 500
    cloud.fail_on = {1500}                                               # stops in the third range
    agent.sync_inbound_cycle(is_incremental=False)
    cursor = agent.config.full_sync_cursors["guid-alpha"]
    done, kept, arrived = cursor["next"], [list(r) for r in cursor["ranges"][:cursor["next"]]], cloud.all_numbers()
    assert done == 2
    cursor.pop("per_range")                                              # as an older agent saved it

    cloud.fail_on = set()
    agent.config.vouchers_per_range = 50
    agent.sync_inbound_cycle(is_incremental=True)

    assert cloud.all_numbers() == list(range(1, 2401)) and agent.config.full_sync_cursors == {}
    sizes = [len(numbers) for numbers, _ in cloud.pushed if numbers != [0]]
    assert sizes[:done] == [520, 520] and max(sizes[done:]) == 80        # two days of 40: the rest in small ranges
    assert arrived == list(range(1, 1041))                               # the first two ranges were not sent again


def test_a_restart_carries_on_from_the_saved_position(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    cloud.fail_on = {1500}
    agent.sync_inbound_cycle(is_incremental=False)
    done = agent.config.full_sync_cursors["guid-alpha"]["next"]

    cloud.fail_on = set()
    restarted = make_agent(tmp_path, tally, cloud)                       # a new agent reading the saved config
    assert restarted.config.full_sync_cursors["guid-alpha"]["next"] == done
    restarted.sync_inbound_cycle(is_incremental=True)

    assert cloud.all_numbers() == list(range(1, 2401)) and "whole" not in tally.calls
    assert restarted.config.full_sync_cursors == {}


def test_a_full_sync_works_in_time_slices(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_module, "FULL_SYNC_SLICE_SECONDS", 0)      # one range per cycle
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)
    total = len(agent.config.full_sync_cursors["guid-alpha"]["ranges"])
    assert agent.config.full_sync_cursors["guid-alpha"]["next"] == 1
    assert "Full sync 1 of" in agent.last_sync_status and agent._last_company_ok is True

    for _ in range(total - 1):
        agent.sync_inbound_cycle(is_incremental=True)
    assert agent.config.full_sync_cursors == {} and cloud.all_numbers() == list(range(1, 2401))


def test_tally_not_answering_a_range_keeps_the_position(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    plan = agent_module.plan_voucher_ranges([d for _, d in tally.vouchers])
    tally.fail_ranges = {(plan[1][0], plan[1][1])}

    agent.sync_inbound_cycle(is_incremental=False)

    assert agent.config.full_sync_cursors["guid-alpha"]["next"] == 1     # not treated as "ranges do not work"
    assert agent._voucher_ranges_work is not False and "whole" not in tally.calls


def test_sync_all_starts_again_and_forces_every_range(tmp_path):
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    cloud.fail_on = {1500}
    agent.sync_inbound_cycle(is_incremental=False)
    cloud.fail_on, cloud.pushed = set(), []

    agent.force_full_sync_next = True
    agent.sync_inbound_cycle(is_incremental=True)

    assert cloud.all_numbers() == list(range(1, 2401))
    assert all(forced for numbers, forced in cloud.pushed if numbers)


def test_the_standing_force_setting_does_not_restart_a_sync_that_is_under_way(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_module, "FULL_SYNC_SLICE_SECONDS", 0)      # one range per cycle
    tally, cloud = Tally(many_vouchers()), Cloud()
    agent = make_agent(tmp_path, tally, cloud)
    agent.config.force_full_sync = True

    agent.sync_inbound_cycle(is_incremental=False)
    total = len(agent.config.full_sync_cursors["guid-alpha"]["ranges"])
    for _ in range(total - 1):
        agent.sync_inbound_cycle(is_incremental=True)

    assert agent.config.full_sync_cursors == {}                          # it finished instead of starting over each cycle
    assert cloud.all_numbers() == list(range(1, 2401)) and tally.calls.count("index") == 1


def test_tallys_count_block_is_not_read_as_a_voucher():
    with_counts = ("<ENVELOPE><BODY><DESC><CMPINFO><COMPANY>0</COMPANY><VOUCHER>2</VOUCHER></CMPINFO></DESC><DATA><COLLECTION>"
                   + voucher(1, "20250401") + voucher(2, "20250402") + "</COLLECTION></DATA></BODY></ENVELOPE>")
    assert voucher_dates(with_counts) == ["20250401", "20250402"]


def test_each_cycle_reports_which_copy_is_open_and_how_far_a_full_sync_is(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_module, "FULL_SYNC_SLICE_SECONDS", 0)
    tally, cloud = Tally(many_vouchers()), Cloud()
    tally.get_open_companies = lambda: [{**ALPHA, "fingerprint": "100004|20250401"}]
    agent = make_agent(tmp_path, tally, cloud)

    agent.sync_inbound_cycle(is_incremental=False)

    assert cloud.company_fingerprint == "100004|20250401"                # sent with every sync call for this company
    report = cloud.reports[-1][0]
    assert report["fingerprint"] == "100004|20250401" and report["progress"].startswith("Full sync 1 of")

    agent.sync_inbound_cycle(is_incremental=True)
    assert cloud.reports[-1][0]["master_alter_id"] == 5 and cloud.reports[-1][0]["voucher_alter_id"] == 5
