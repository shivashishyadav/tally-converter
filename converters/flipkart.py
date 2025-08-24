"""
Flipkart Converter → Tally Voucher format
"""

import pandas as pd
from .base import TALLY_COLUMNS, parse_date, safe_float, apply_gst_split, make_row


def convert(df: pd.DataFrame, seller_state: str) -> pd.DataFrame:
    """
    Convert Flipkart sales report → Tally-compatible rows
    """
    # Normalize columns
    colmap = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=colmap)

    rows = []
    for idx, r in df.iterrows():
        # Voucher details
        voucher_no = r.get("invoice number") or r.get("invoice-no") or f"FK-{idx+1}"
        voucher_date = parse_date(r.get("invoice date") or r.get("order date"))

        # Buyer info
        buyer_state = r.get("shipping state") or r.get("ship-to-state") or ""
        buyer_name = (
            r.get("customer name") or r.get("buyer name") or "Sale through Flipkart"
        )

        # GST
        gst_number = r.get("buyer gstin") or r.get("gstin") or ""
        gst_type = "Registered" if gst_number else "Unregistered"

        # Item info
        item = r.get("item name") or r.get("product name") or r.get("sku") or "Item"
        hsn = r.get("hsn") or r.get("hsn code") or ""
        qty = safe_float(r.get("quantity") or 1, 1)
        rate = safe_float(r.get("unit price") or r.get("price") or 0)
        amount = safe_float(r.get("taxable value") or r.get("amount") or rate * qty, 0)
        tax_amt = safe_float(
            r.get("tax amount") or r.get("gst amount") or amount * 0.18, 0
        )

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
