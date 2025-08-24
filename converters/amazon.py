"""
Amazon B2B & B2C Converter → Tally Voucher format
"""

import pandas as pd
from .base import TALLY_COLUMNS, parse_date, safe_float, apply_gst_split, make_row


def convert(df: pd.DataFrame, seller_state: str) -> pd.DataFrame:
    """
    Convert Amazon B2B and B2C invoices into Tally-compatible rows
    """
    # Normalize column names (lowercase, strip spaces)
    colmap = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=colmap)

    rows = []
    for idx, r in df.iterrows():
        # Voucher details
        voucher_no = r.get("invoice-id") or r.get("order-id") or f"AMZ-{idx+1}"
        voucher_date = parse_date(r.get("invoice-date") or r.get("order-date"))

        # Buyer info
        buyer_state = r.get("ship-state") or r.get("shipping state") or ""
        buyer_name = r.get("buyer-name") or "Sale through Amazon"

        # GST info
        gst_number = r.get("buyer-gstin") or r.get("gstin") or ""
        gst_type = "Registered" if gst_number else "Unregistered"

        # Item info
        item = r.get("product-name") or r.get("item name") or "Item"
        hsn = r.get("hsn") or ""
        qty = safe_float(r.get("quantity") or 1, 1)
        rate = safe_float(r.get("price") or r.get("unit-price") or 0)
        amount = safe_float(r.get("taxable-value") or r.get("amount") or rate * qty, 0)
        tax_amt = safe_float(
            r.get("tax-amount") or r.get("gst-amount") or amount * 0.18, 0
        )

        # GST split
        cgst, sgst, igst = apply_gst_split(tax_amt, seller_state, buyer_state)

        # Build Tally row
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
