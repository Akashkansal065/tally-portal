"""
Payroll masters and Tally: attendance types, pay heads, employee groups and employees. A change Tally refuses
is not kept, a change made while Tally is away is kept and queued, a repeat never makes a second record, and
a rename on either side is followed by Tally's GUID.

Tally is replaced by FakeMasters, which keeps masters by name the way TallyPrime does.
"""
import re

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.portal_core import SyncQueue
from app.models.tally_core import MstAttendanceType, MstCostCategory, MstCostCentre, MstGroup, MstLedger, MstPayHead
from app.routers import auth, payroll_masters, sync
from app.services import payroll_masters as pm
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import bearer, login, run

TAGS = {"AttendanceType": "ATTENDANCETYPE", "Ledger": "LEDGER", "CostCentre": "COSTCENTRE"}


class FakeMasters:
    def __init__(self):
        self.held = {tag: {} for tag in TAGS.values()}   # tag -> name -> {"guid", "master_id", "xml"}
        self.next_master = 400
        self.down = False
        self.refuse = None
        self.imports = []

    def __call__(self, url, xml, timeout=5):
        if self.down:
            raise ConnectionError("Tally is not running")
        if "<TALLYREQUEST>Export</TALLYREQUEST>" in xml:
            tag = TAGS[re.search(r"<TYPE>(\w+)</TYPE><FETCH>", xml).group(1)]
            by_guid, by_name = re.search(r'\$GUID = &quot;([^&]*)&quot;', xml), re.search(r'\$Name = &quot;([^&]*)&quot;', xml)
            for name, rec in self.held[tag].items():
                if (by_guid and rec["guid"] == by_guid.group(1)) or (by_name and name == by_name.group(1)):
                    return f'<ENVELOPE><{tag} NAME="{name}"><GUID>{rec["guid"]}</GUID><MASTERID> {rec["master_id"]}</MASTERID></{tag}></ENVELOPE>'
            return "<ENVELOPE></ENVELOPE>"
        self.imports.append(xml)
        tag, name, action = re.search(r'<(ATTENDANCETYPE|LEDGER|COSTCENTRE) NAME="([^"]*)" ACTION="(\w+)">', xml).groups()
        if self.refuse:
            return f"<RESPONSE><LINEERROR>{self.refuse}</LINEERROR><CREATED>0</CREATED><ERRORS>1</ERRORS></RESPONSE>"
        if action == "Delete":
            del self.held[tag][name]
            return "<RESPONSE><CREATED>0</CREATED><ALTERED>0</ALTERED><DELETED>1</DELETED><ERRORS>0</ERRORS></RESPONSE>"
        new_name = re.search(r"<NAME>([^<]*)</NAME>", xml).group(1)
        if action == "Create":
            if new_name in self.held[tag]:
                return "<RESPONSE><LINEERROR>Already exists!</LINEERROR><CREATED>0</CREATED><ERRORS>1</ERRORS></RESPONSE>"
            self.next_master += 1
            self.held[tag][new_name] = {"guid": f"guid-{self.next_master}", "master_id": self.next_master, "xml": xml}
            return "<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS></RESPONSE>"
        rec = self.held[tag].pop(name)
        self.held[tag][new_name] = {**rec, "xml": xml}
        return "<RESPONSE><CREATED>0</CREATED><ALTERED>1</ALTERED><ERRORS>0</ERRORS></RESPONSE>"


@pytest.fixture
def setup(harness, monkeypatch):
    tally = FakeMasters()
    monkeypatch.setattr(settings, "TALLY_URL", "http://tally.test:9000")
    monkeypatch.setattr(sync, "_post_to_tally_sync", tally)
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    cid = company.company_id
    expenses = harness.add(MstGroup(company_id=cid, name="Indirect Expenses", nature="Expense"))
    category = harness.add(MstCostCategory(company_id=cid, name="Primary Cost Category"))
    client = harness.app(auth.router, payroll_masters.router, sync.router)

    class Setup:
        pass
    s = Setup()
    s.harness, s.tally, s.client, s.headers, s.company_id = harness, tally, client, bearer(login(client, admin.email)), cid
    s.group_id, s.category_id = expenses.group_id, category.category_id
    s.pending = lambda: [(r.record_type, r.action) for (r,) in harness.query(select(SyncQueue).where(SyncQueue.is_processed == False))]  # noqa: E712
    s.replay = lambda: run(_replay(harness))
    return s


async def _replay(harness):
    async for db in harness._get_db():
        for item in (await db.execute(select(SyncQueue).where(SyncQueue.is_processed == False))).scalars().all():  # noqa: E712
            await pm.replay_queued(db, item)


def test_an_attendance_type_reaches_tally_and_takes_its_guid(setup):
    reply = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present", "type_of_attendance": "Attendance / Leave with Pay"})

    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert (body["tally_status"], body["tally_guid"], body["tally_master_id"]) == ("SUCCESS", "guid-401", 401)
    assert "<ATTENDANCEPERIOD>Days</ATTENDANCEPERIOD>" in setup.tally.held["ATTENDANCETYPE"]["Present"]["xml"]
    assert setup.pending() == []


def test_a_production_type_needs_its_unit_and_sends_it(setup):
    bad = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Overtime", "type_of_attendance": "Production"})
    good = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Overtime", "type_of_attendance": "Production", "unit_name": "Hrs"})

    assert bad.status_code == 400 and good.status_code == 201
    assert "<BASEUNITS>Hrs</BASEUNITS>" in setup.tally.held["ATTENDANCETYPE"]["Overtime"]["xml"]


def test_a_master_tally_refuses_is_not_kept(setup):
    setup.tally.refuse = "Unit 'Hrs' does not exist!"

    reply = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Overtime", "type_of_attendance": "Production", "unit_name": "Hrs"})

    assert reply.status_code == 400 and "Hrs" in reply.json()["detail"]
    assert setup.harness.query(select(MstAttendanceType)) == [] and setup.pending() == []


def test_a_rename_alters_the_same_record_in_tally(setup):
    made = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present"}).json()

    reply = setup.client.put(f"/payroll-masters/attendance-types/{made['attendance_type_id']}", headers=setup.headers, json={"name": "At Work"})

    assert reply.status_code == 200 and reply.json()["tally_guid"] == "guid-401"
    assert list(setup.tally.held["ATTENDANCETYPE"]) == ["At Work"]


def test_a_rename_made_in_tally_is_addressed_by_guid(setup):
    made = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present"}).json()
    held = setup.tally.held["ATTENDANCETYPE"]
    held["Present (Tally)"] = held.pop("Present")   # a Tally user renames it

    reply = setup.client.put(f"/payroll-masters/attendance-types/{made['attendance_type_id']}", headers=setup.headers, json={"name": "On Duty"})

    assert reply.status_code == 200 and list(held) == ["On Duty"]


def test_made_while_tally_is_away_is_kept_and_sent_once_later(setup):
    setup.tally.down = True
    made = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present"})
    changed = setup.client.put(f"/payroll-masters/attendance-types/{made.json()['attendance_type_id']}", headers=setup.headers, json={"name": "At Work"})

    assert (made.status_code, made.json()["tally_status"], changed.status_code) == (201, "NO_RESPONSE", 200)
    assert setup.pending() == [("AttendanceType", "Create")]

    setup.tally.down = False
    setup.replay()
    setup.replay()

    assert list(setup.tally.held["ATTENDANCETYPE"]) == ["At Work"] and len(setup.tally.imports) == 1
    assert setup.pending() == []
    assert setup.harness.scalar(select(MstAttendanceType.tally_guid)) == "guid-401"


def test_made_and_deleted_while_tally_is_away_tells_tally_nothing(setup):
    setup.tally.down = True
    made = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present"}).json()

    reply = setup.client.delete(f"/payroll-masters/attendance-types/{made['attendance_type_id']}", headers=setup.headers)

    assert reply.status_code == 200 and setup.pending() == [] and setup.harness.query(select(MstAttendanceType)) == []


def test_deleted_while_tally_is_away_is_deleted_in_tally_later(setup):
    made = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present"}).json()
    setup.tally.down = True
    setup.client.delete(f"/payroll-masters/attendance-types/{made['attendance_type_id']}", headers=setup.headers)

    assert setup.pending() == [("AttendanceType", "Delete")]
    setup.tally.down = False
    setup.replay()

    assert setup.tally.held["ATTENDANCETYPE"] == {} and setup.pending() == []


def test_a_delete_tally_refuses_keeps_the_record(setup):
    made = setup.client.post("/payroll-masters/attendance-types", headers=setup.headers, json={"name": "Present"}).json()
    setup.tally.refuse = "Cannot delete: in use"

    reply = setup.client.delete(f"/payroll-masters/attendance-types/{made['attendance_type_id']}", headers=setup.headers)

    assert reply.status_code == 400 and len(setup.harness.query(select(MstAttendanceType))) == 1


def test_a_pay_head_is_a_ledger_with_a_pay_type(setup):
    reply = setup.client.post("/payroll-masters/pay-heads", headers=setup.headers,
                              json={"name": "PF", "pay_head_type": "Deductions from Employees", "under_group_id": setup.group_id})

    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert body["is_deduction"] and body["tally_guid"] == "guid-401"
    sent = setup.tally.held["LEDGER"]["PF"]["xml"]
    assert "<PAYTYPE>Deductions from Employees</PAYTYPE>" in sent and "<PARENT>Indirect Expenses</PARENT>" in sent
    ledger = setup.harness.query(select(MstLedger))[0][0]
    assert (ledger.name, ledger.tally_guid, body["ledger_id"]) == ("PF", "guid-401", ledger.ledger_id)


def test_a_refused_pay_head_leaves_no_ledger_behind(setup):
    setup.tally.refuse = "Group does not exist!"

    reply = setup.client.post("/payroll-masters/pay-heads", headers=setup.headers, json={"name": "PF", "under_group_id": setup.group_id})

    assert reply.status_code == 400
    assert setup.harness.query(select(MstLedger)) == [] and setup.harness.query(select(MstPayHead)) == []


def test_a_calculated_pay_head_cannot_be_set_up_here(setup):
    reply = setup.client.post("/payroll-masters/pay-heads", headers=setup.headers,
                              json={"name": "Basic", "under_group_id": setup.group_id, "calculation_type": "On Attendance"})

    assert reply.status_code == 400 and setup.tally.imports == []


def _employee(setup, **over):
    return {"name": "Ravi", "category_id": setup.category_id, "employee_number": "E01", "date_of_join": "2025-04-01", "designation": "Clerk", "gender": "Male", **over}


def test_an_employee_goes_to_tally_with_group_and_salary_details(setup):
    setup.client.post("/payroll-masters/pay-heads", headers=setup.headers, json={"name": "Bonus", "under_group_id": setup.group_id})
    group = setup.client.post("/payroll-masters/employees", headers=setup.headers, json={"name": "Office Staff", "category_id": setup.category_id, "is_employee_group": True}).json()

    reply = setup.client.post("/payroll-masters/employees", headers=setup.headers, json=_employee(
        setup, parent_id=group["cost_centre_id"], salary_rates=[{"effective_from": "2025-04-01", "pay_head_name": "Bonus", "rate": 1000}]))

    assert reply.status_code == 201, reply.text
    sent = setup.tally.held["COSTCENTRE"]["Ravi"]["xml"]
    assert "<ISEMPLOYEEGROUP>Yes</ISEMPLOYEEGROUP>" in setup.tally.held["COSTCENTRE"]["Office Staff"]["xml"]
    for part in ("<PARENT>Office Staff</PARENT>", "<FORPAYROLL>Yes</FORPAYROLL>", "<DATEOFJOIN>20250401</DATEOFJOIN>", "<MAILINGNAME>E01</MAILINGNAME>",
                 "<PERIODFROM>20250401</PERIODFROM><EMPLOYEERATE.LIST><NAME>Bonus</NAME><EMPTIMERATE>1000"):
        assert part in sent
    assert reply.json()["salary_rates"][0]["pay_head_name"] == "Bonus"


def test_an_employee_with_an_unknown_pay_head_is_turned_down_before_tally(setup):
    reply = setup.client.post("/payroll-masters/employees", headers=setup.headers, json=_employee(
        setup, salary_rates=[{"effective_from": "2025-04-01", "pay_head_name": "Nope", "rate": 1}]))

    assert reply.status_code == 400 and setup.tally.imports == []


def test_a_group_with_employees_cannot_be_deleted(setup):
    group = setup.client.post("/payroll-masters/employees", headers=setup.headers, json={"name": "Office Staff", "category_id": setup.category_id, "is_employee_group": True}).json()
    setup.client.post("/payroll-masters/employees", headers=setup.headers, json=_employee(setup, parent_id=group["cost_centre_id"]))

    reply = setup.client.delete(f"/payroll-masters/employees/{group['cost_centre_id']}", headers=setup.headers)

    assert reply.status_code == 400 and "Office Staff" in setup.tally.held["COSTCENTRE"]


def test_payroll_masters_are_read_from_tally_with_their_details(setup):
    xml = """<ENVELOPE><BODY><DATA><COLLECTION>
<COSTCATEGORY NAME="Primary Cost Category"></COSTCATEGORY>
<COSTCENTRE NAME="Staff"><GUID>g-1</GUID><MASTERID> 11</MASTERID><CATEGORY>Primary Cost Category</CATEGORY><FORPAYROLL>Yes</FORPAYROLL><ISEMPLOYEEGROUP>Yes</ISEMPLOYEEGROUP></COSTCENTRE>
<COSTCENTRE NAME="Ashish"><GUID>g-2</GUID><MASTERID> 12</MASTERID><PARENT>Staff</PARENT><CATEGORY>Primary Cost Category</CATEGORY><FORPAYROLL>Yes</FORPAYROLL><ISEMPLOYEEGROUP>No</ISEMPLOYEEGROUP>
<DATEOFJOIN>20250401</DATEOFJOIN><DESIGNATION>Accountant</DESIGNATION><GENDER>Male</GENDER><MAILINGNAME.LIST><MAILINGNAME>0001</MAILINGNAME></MAILINGNAME.LIST>
<EMPLOYEEPERIOD.LIST><PERIODFROM>20250401</PERIODFROM><EMPLOYEERATE.LIST><NAME>Basic Salary</NAME><EMPTIMERATE> 5000</EMPTIMERATE></EMPLOYEERATE.LIST>
<EMPLOYEERATE.LIST><NAME>DA</NAME></EMPLOYEERATE.LIST></EMPLOYEEPERIOD.LIST></COSTCENTRE>
<ATTENDANCETYPE NAME="Overtime"><GUID>g-3</GUID><MASTERID> 13</MASTERID><ATTENDANCEPRODUCTIONTYPE>Production</ATTENDANCEPRODUCTIONTYPE><BASEUNITS>Hrs</BASEUNITS></ATTENDANCETYPE>
</COLLECTION></DATA></BODY></ENVELOPE>"""

    async def go():
        async for db in setup.harness._get_db():
            await import_tally_xml(xml, db, 1, override_company_name="Alpha")
    run(go())
    # read again after a rename in Tally: the same employee, not a second one
    run_again = xml.replace('NAME="Ashish"', 'NAME="Ashish K"')

    async def again():
        async for db in setup.harness._get_db():
            await import_tally_xml(run_again, db, 1, override_company_name="Alpha")
    run(again())

    staff = setup.client.get("/payroll-masters/employees", headers=setup.headers).json()
    assert [(e["name"], e["is_employee_group"], e["parent_name"]) for e in staff] == [("Staff", True, None), ("Ashish K", False, "Staff")]
    ashish = staff[1]
    assert (ashish["employee_number"], ashish["date_of_join"], ashish["designation"], ashish["tally_guid"]) == ("0001", "2025-04-01", "Accountant", "g-2")
    assert [(r["pay_head_name"], r["rate"]) for r in ashish["salary_rates"]] == [("Basic Salary", "5000.00"), ("DA", None)]
    overtime = setup.client.get("/payroll-masters/attendance-types", headers=setup.headers).json()[0]
    assert (overtime["type_of_attendance"], overtime["unit_name"], overtime["tally_guid"]) == ("Production", "Hrs", "g-3")


def test_a_pay_head_calculated_in_tally_keeps_its_calculation_when_edited_here(setup):
    ledger = setup.harness.add(MstLedger(company_id=setup.company_id, name="Basic", group_id=setup.group_id, tally_guid="guid-basic"))
    setup.tally.held["LEDGER"]["Basic"] = {"guid": "guid-basic", "master_id": 9, "xml": ""}
    for calculation in ("On Attendance", None):   # read from Tally as calculated / not read yet
        head = setup.harness.add(MstPayHead(company_id=setup.company_id, name="Basic", ledger_id=ledger.ledger_id, under_group_id=setup.group_id,
                                            pay_head_type="Earnings for Employees", calculation_type=calculation))

        reply = setup.client.put(f"/payroll-masters/pay-heads/{head.pay_head_id}", headers=setup.headers,
                                 json={"name": "Basic", "under_group_id": setup.group_id, "payslip_name": "Basic Pay", "calculation_type": "As User Defined Value"})

        assert reply.status_code == 200, reply.text
        sent = setup.tally.held["LEDGER"]["Basic"]["xml"]
        assert "<PAYSLIPNAME>Basic Pay</PAYSLIPNAME>" in sent and "CALCULATIONTYPE" not in sent
        assert reply.json()["calculation_type"] == calculation and not reply.json()["calculation_editable"]
        setup.harness.execute(__import__("sqlalchemy").delete(MstPayHead))
