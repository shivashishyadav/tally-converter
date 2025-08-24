"""
TCS (Tax Collected at Source) / Transporter reports → Tally Voucher format
"""

import pandas as pd
from .base import TALLY_COLUMNS, parse_date, safe_float, apply_gst_split, make_row


def convert(df: pd.DataFrame, seller_state: str) -> pd.DataFrame:
    """
    Convert TCS-style reports → Tally-compatible rows
    (These usually include recon reports or marketplace
     deductions with GST amounts separately.)
    """
    # Normalize column names
    colmap = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=colmap)

    rows = []
    for idx, r in df.iterrows():
        # Voucher basics
        voucher_no = (
            r.get("voucher no")
            or r.get("invoice no")
            or r.get("txn id")
            or f"TCS-{idx+1}"
        )
        voucher_date = parse_date(r.get("date") or r.get("voucher date"))

        # Buyer info
        buyer_state = r.get("state") or r.get("buyer state") or ""
        buyer_name = r.get("customer name") or r.get("party name") or "Sale through TCS"

        # GST info
        gst_number = r.get("gstin") or r.get("buyer gstin") or ""
        gst_type = "Registered" if gst_number else "Unregistered"

        # Item info
        item = r.get("item") or r.get("product") or "Item"
        hsn = r.get("hsn") or ""
        qty = safe_float(r.get("quantity") or 1, 1)
        rate = safe_float(r.get("rate") or r.get("unit price") or 0)
        amount = safe_float(r.get("taxable value") or r.get("amount") or rate * qty, 0)
        tax_amt = safe_float(r.get("tax") or r.get("gst amount") or amount * 0.18, 0)

        # GST breakup
        cgst, sgst, igst = apply_gst_split(tax_amt, seller_state, buyer_state)

        # Build row
        row = make_row(
            voucher_no,
            voucher_date,
            buyer_name,
            buyer_state,
            gst_type,
            gst_number,
            item,
            hsn,
            qty,
            rate,
            amount,
            tax_amt,
            cgst,
            sgst,
            igst,
        )
        rows.append(row)

    return pd.DataFrame(rows, columns=TALLY_COLUMNS)
