"""
Shared base utilities for all e-commerce → Tally converters
"""

import pandas as pd
from dateutil import parser as dateparser

# ----------------------------
# Tally output schema
# ----------------------------
TALLY_COLUMNS = [
    "Voucher No",
    "Voucher Date",
    "Customer Name",
    "Group",
    "Address",
    "State",
    "GST Type",
    "GST Number",
    "Sales Ledger Name",
    "Item Name",
    "Batch No.",
    "Expiry",
    "HSN Code",
    "Quantity",
    "Rate",
    "Amount",
    "Taxes",
    "CGST Ledger Name",
    "CGST Amount",
    "SGST Ledger Name",
    "SGST Amount",
    "IGST Ledger Name",
    "IGST Amount",
    "Total Amount",
    "Other Charges Ledger",
    "Other Charges Amount",
]


# ----------------------------
# Helpers
# ----------------------------
def parse_date(val):
    """Try to parse any date-like value into YYYY-MM-DD string"""
    try:
        return dateparser.parse(str(val)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def safe_float(x, default=0.0):
    """Convert to float if possible, otherwise return default"""
    try:
        return float(x)
    except Exception:
        return default


def apply_gst_split(tax_amount, seller_state, buyer_state):
    """
    Decide GST breakup based on intra/inter state
    - If same state: CGST + SGST (9% + 9%)
    - If different state: IGST (18%)
    """
    seller_state = str(seller_state).strip().lower()
    buyer_state = str(buyer_state).strip().lower()

    intra = seller_state and buyer_state and seller_state == buyer_state

    if intra:
        cgst = round(tax_amount / 2, 2)
        sgst = round(tax_amount / 2, 2)
        igst = 0.0
    else:
        cgst = sgst = 0.0
        igst = round(tax_amount, 2)

    return cgst, sgst, igst


def make_row(
    voucher_no,
    voucher_date,
    customer,
    state,
    gst_type,
    gst_number,
    item_name,
    hsn,
    qty,
    rate,
    amount,
    tax_amt,
    cgst,
    sgst,
    igst,
):
    """Return one row dictionary in the Tally schema"""
    return {
        "Voucher No": voucher_no,
        "Voucher Date": voucher_date,
        "Customer Name": customer,
        "Group": "Sundry Debtors",
        "Address": state,
        "State": state,
        "GST Type": gst_type,
        "GST Number": gst_number,
        "Sales Ledger Name": "Sales through Ecommerce",
        "Item Name": item_name,
        "Batch No.": "",
        "Expiry": "",
        "HSN Code": hsn,
        "Quantity": qty,
        "Rate": rate,
        "Amount": amount,
        "Taxes": tax_amt,
        "CGST Ledger Name": "Output CGST",
        "CGST Amount": cgst,
        "SGST Ledger Name": "Output SGST",
        "SGST Amount": sgst,
        "IGST Ledger Name": "Output IGST",
        "IGST Amount": igst,
        "Total Amount": round(amount + tax_amt, 2),
        "Other Charges Ledger": "",
        "Other Charges Amount": "",
    }


# ----------------------------
# Generic fallback converter
# ----------------------------
def generic_convert(df: pd.DataFrame, seller_state: str) -> pd.DataFrame:
    """
    A basic converter that tries to map common columns
    from unknown marketplace formats into Tally schema.
    """
    colmap = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=colmap)
    rows = []

    for idx, r in df.iterrows():
        voucher_no = r.get("invoice id") or r.get("order id") or f"GEN-{idx+1}"
        voucher_date = parse_date(r.get("invoice date") or r.get("order date") or "")
        buyer_state = r.get("shipping state") or r.get("state") or ""
        buyer_name = (
            r.get("buyer name") or r.get("customer name") or "Sale through Generic"
        )
        gst_number = r.get("buyer gstin") or r.get("gstin") or ""
        gst_type = "Registered" if gst_number else "Unregistered"

        item = r.get("product name") or r.get("item name") or "Item"
        hsn = r.get("hsn") or ""
        qty = safe_float(r.get("quantity") or 1, 1)
        rate = safe_float(r.get("unit price") or r.get("price") or 0)
        amount = safe_float(r.get("taxable value") or r.get("amount") or rate * qty, 0)
        tax_amt = safe_float(
            r.get("tax amount") or r.get("gst amount") or amount * 0.18, 0
        )

        cgst, sgst, igst = apply_gst_split(tax_amt, seller_state, buyer_state)

        rows.append(
            make_row(
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
        )

    return pd.DataFrame(rows, columns=TALLY_COLUMNS)
