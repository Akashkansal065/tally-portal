"""
Entry settings per voucher type (the app's "Voucher Configuration" screen).

These live in the app only: Tally keeps its own F12 entry settings outside the company data, so they
cannot be read from or written to Tally.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.tally_core import MstVoucherConfiguration


def default_configuration(parent_type: str) -> dict:
    """What a voucher type uses until someone saves its configuration."""
    parent = (parent_type or "").lower()
    is_purchase = "purchase" in parent or "receipt note" in parent
    is_sales = "sales" in parent or "delivery note" in parent
    is_payment_receipt = "payment" in parent or "receipt" in parent or "contra" in parent
    return dict(
        use_cr_dr=True,
        provide_supplier_ref=is_purchase,
        warn_negative_cash=True,
        preallocate_bills=False,
        show_bill_wise_details=True,
        show_bill_wise_multiple_lines=True,
        show_list_of_bills=True,
        show_final_bill_balances=True,
        skip_date_field=False,
        show_inventory_details=(is_sales or is_purchase),
        show_ledger_current_balance=True,
        warn_voucher_number_length=True,
        enable_stripe_view=False,
        use_default_bank_allocations=is_payment_receipt,
        auto_cheque_numbering=True,
        select_cheque_range=True,
        set_ledger_bank_allocations=False,
        print_cheque_after_saving=False,
        show_cheque_details_before_printing=True,
        provide_cash_denominations=("contra" in parent),
        provide_buyer_details=is_sales,
        provide_dispatch_order_export=is_sales,
        provide_order_details=is_sales,
        select_common_sales_ledger=is_sales,
        use_vch_no_as_bill_ref=is_sales,
        warn_negative_stock=True,
        provide_trade_discount=False,
        rate_inclusive_of_tax=False,
        show_party_turnover=False,
        use_default_pg_allocations=False,
        set_ledger_pg_allocations=False,
        provide_party_gst_details=False,
        modify_gst_hsn_details=False,
        send_eway_bill_details=is_sales,
    )


async def configuration_setting(db: AsyncSession, vtype, name: str) -> bool:
    """One setting of a voucher type: the saved value, or the default for its kind."""
    if vtype is None:
        return bool(default_configuration("").get(name))
    saved = (await db.execute(select(MstVoucherConfiguration).where(
        MstVoucherConfiguration.voucher_type_id == vtype.voucher_type_id))).scalars().first()
    if saved is not None and getattr(saved, name, None) is not None:
        return bool(getattr(saved, name))
    return bool(default_configuration(vtype.parent_type or vtype.name).get(name))


def auto_bill_reference(voucher_number, reference_number, use_voucher_number: bool, previous_bill=None, previous_reference=None) -> str:
    """
    The name of the bill a sales or purchase voucher raises for its party.

    A voucher being edited keeps the bill name it already has, so receipts and payments settled against that
    bill stay attached; only a bill that was named after the reference number follows a change of reference.
    """
    if previous_bill and previous_bill != (previous_reference or None):
        return previous_bill
    if previous_bill:
        return reference_number or voucher_number
    if use_voucher_number:
        return voucher_number or reference_number
    return reference_number or voucher_number
