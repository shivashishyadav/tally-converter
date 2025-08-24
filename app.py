import os
import io
import traceback
from datetime import datetime

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    send_file,
    abort,
)
import pandas as pd

# ---------------------------
# Configuration
# ---------------------------
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_EXTENSIONS = {".csv", ".xls", ".xlsx"}
ALLOWED_MIMES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# ---------------------------
# App init
# ---------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB uploads


# ---------------------------
# Dynamic import helpers
# ---------------------------
def import_parser(module_name: str):
    """
    Try to import converters.<module_name>.convert
    Return the convert function or None.
    """
    try:
        module_path = f"converters.{module_name}"
        module = __import__(module_path, fromlist=["convert"])
        convert_fn = getattr(module, "convert", None)
        if callable(convert_fn):
            app.logger.debug(f"Loaded parser converters.{module_name}")
            return convert_fn
    except Exception as e:
        app.logger.debug(f"No parser converters.{module_name}: {e}")
    return None


# Preload known parser functions if available
PARSERS = {
    "amazon": import_parser("amazon"),
    "flipkart": import_parser("flipkart"),
    "meesho": import_parser("meesho"),
    "tcs": import_parser("tcs"),
    "generic": import_parser("generic"),  # fallback
}


# If generic parser missing, we'll use an inline fallback converter defined below.
def inline_generic_convert(df: pd.DataFrame, seller_state: str):
    """
    Minimal generic converter used if converters.generic isn't present.
    It attempts to map common columns to the Tally schema using heuristics.
    """
    from converters.base import TALLY_COLUMNS, parse_date, apply_gst_split

    # lower and strip column names
    colmap = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=colmap)
    rows = []

    for idx, row in df.iterrows():
        # heuristics for common columns
        voucher_no = (
            row.get("invoice id") or row.get("order id") or row.get("id") or f"R{idx+1}"
        )
        voucher_date = parse_date(
            row.get("invoice date") or row.get("order date") or row.get("date") or ""
        )
        buyer_state = (
            row.get("shipping state") or row.get("state") or row.get("ship state") or ""
        )
        buyer_name = (
            row.get("buyer name") or row.get("customer name") or f"Sale via Marketplace"
        )
        is_b2b = bool(
            row.get("buyer gstin")
            or row.get("gstin")
            or row.get("gst number")
            or row.get("gst no")
        )
        gst_type = "Registered" if is_b2b else "Unregistered"
        gst_number = (
            row.get("buyer gstin") or row.get("gstin") or row.get("gst number") or ""
        )

        item_name = (
            row.get("product title")
            or row.get("item name")
            or row.get("product")
            or "Item"
        )
        hsn = row.get("hsn") or row.get("hsn code") or ""
        qty = row.get("quantity") or row.get("qty") or 1
        try:
            qty = float(qty)
        except Exception:
            qty = 1.0
        rate = row.get("unit price") or row.get("price") or row.get("rate") or ""
        try:
            rate = float(rate)
        except Exception:
            rate = None
        amount = (
            row.get("taxable value")
            or row.get("amount")
            or row.get("item value")
            or 0.0
        )
        try:
            amount = float(amount)
        except Exception:
            # fallback compute
            try:
                amount = float(qty) * float(rate) if rate is not None else 0.0
            except Exception:
                amount = 0.0

        tax_amt = (
            row.get("tax amount") or row.get("tax") or row.get("gst amount") or None
        )
        try:
            tax_amt = float(tax_amt) if tax_amt not in (None, "") else None
        except Exception:
            tax_amt = None

        if not tax_amt:
            tax_amt = round(amount * 0.18, 2)

        cgst, sgst, igst = apply_gst_split(tax_amt, seller_state, buyer_state)
        total_amount = round(amount + tax_amt, 2)

        r = {
            "Voucher No": voucher_no,
            "Voucher Date": voucher_date,
            "Customer Name": buyer_name,
            "Group": "Sundry Debtors",
            "Address": buyer_state,
            "State": buyer_state,
            "GST Type": gst_type,
            "GST Number": gst_number if is_b2b else "",
            "Sales Ledger Name": "Sales through Ecommerce",
            "Item Name": item_name,
            "Batch No.": "",
            "Expiry": "",
            "HSN Code": hsn,
            "Quantity": qty,
            "Rate": rate if rate is not None else "",
            "Amount": amount,
            "Taxes": tax_amt,
            "CGST Ledger Name": "Output CGST",
            "CGST Amount": cgst,
            "SGST Ledger Name": "Output SGST",
            "SGST Amount": sgst,
            "IGST Ledger Name": "Output IGST",
            "IGST Amount": igst,
            "Total Amount": total_amount,
            "Other Charges Ledger": "",
            "Other Charges Amount": "",
        }
        rows.append(r)

    df_out = pd.DataFrame(
        rows,
        columns=__import__("converters.base", fromlist=["TALLY_COLUMNS"]).TALLY_COLUMNS,
    )
    return df_out


# ---------------------------
# Routes
# ---------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            seller_state = request.form.get("seller_state", "").strip()
            if not seller_state:
                flash(
                    "Seller state is required to correctly split GST (CGST/SGST vs IGST).",
                    "warning",
                )
                return redirect(url_for("index"))

            if "files" not in request.files:
                flash("No files uploaded. Please attach CSV/XLSX files.", "danger")
                return redirect(url_for("index"))

            files = request.files.getlist("files")
            parsed_dfs = []
            parsed_sources = []

            for file in files:
                if file.filename == "":
                    continue

                fn_lower = file.filename.lower()
                ext = os.path.splitext(file.filename)[1].lower()
                if ext not in UPLOAD_EXTENSIONS:
                    flash(
                        f"Skipping {file.filename}: unsupported extension {ext}",
                        "warning",
                    )
                    continue

                # read file safely
                try:
                    file.stream.seek(0)
                    if ext == ".csv":
                        # try common encodings and separators; best-effort
                        df = pd.read_csv(file, low_memory=False)
                    else:
                        df = pd.read_excel(file)
                except Exception as e:
                    # try alternative read for messy CSVs
                    try:
                        file.stream.seek(0)
                        df = pd.read_csv(
                            file, encoding="utf-8", engine="python", low_memory=False
                        )
                    except Exception as e2:
                        app.logger.error(f"Failed to read {file.filename}: {e2}")
                        flash(f"Failed to read {file.filename}: {e2}", "danger")
                        continue

                # choose parser by filename hint or fallback
                parser_fn = None
                if "amazon" in fn_lower and PARSERS.get("amazon"):
                    parser_fn = PARSERS["amazon"]
                    source_tag = "Amazon"
                elif "flipkart" in fn_lower and PARSERS.get("flipkart"):
                    parser_fn = PARSERS["flipkart"]
                    source_tag = "Flipkart"
                elif "meesho" in fn_lower and PARSERS.get("meesho"):
                    parser_fn = PARSERS["meesho"]
                    source_tag = "Meesho"
                elif "tcs" in fn_lower and PARSERS.get("tcs"):
                    parser_fn = PARSERS["tcs"]
                    source_tag = "TCS"
                else:
                    # fallback to generic parser module if present, otherwise inline
                    parser_fn = PARSERS.get("generic") or inline_generic_convert
                    source_tag = "Generic"

                # ensure parser signature is df, seller_state
                try:
                    out_df = parser_fn(df, seller_state)
                except TypeError:
                    # some parsers might expect (df, seller_state)
                    out_df = parser_fn(df, seller_state)

                if out_df is None or out_df.empty:
                    app.logger.info(f"Parser returned no rows for {file.filename}")
                else:
                    parsed_dfs.append(out_df)
                    parsed_sources.append(file.filename)

            if not parsed_dfs:
                flash(
                    "No valid data parsed from uploaded files. Check file formats or column names.",
                    "danger",
                )
                return redirect(url_for("index"))

            combined = pd.concat(parsed_dfs, ignore_index=True)

            # create an (empty) Sales Return sheet
            sales_return = combined.head(0).copy()

            # Add a small metadata sheet
            meta = pd.DataFrame(
                {
                    "Generated On": [
                        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    ],
                    "Source Files": [", ".join(parsed_sources)],
                    "Seller State": [seller_state],
                }
            )

            # write to in-memory excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                combined.to_excel(writer, sheet_name="Sales", index=False)
                sales_return.to_excel(writer, sheet_name="Sales Return", index=False)
                meta.to_excel(writer, sheet_name="_metadata", index=False)
            output.seek(0)

            fname = f"tally_vouchers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return send_file(
                output,
                as_attachment=True,
                download_name=fname,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except Exception as e:
            app.logger.error(
                "Unhandled exception in upload/convert: %s\n%s",
                e,
                traceback.format_exc(),
            )
            flash(f"An error occurred during conversion: {e}", "danger")
            return redirect(url_for("index"))

    # GET
    return render_template("index.html")


# ---------------------------
# Health / debug
# ---------------------------
@app.route("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ---------------------------
# CLI friendly run
# ---------------------------
if __name__ == "__main__":
    # show which parsers are available
    available = {k: bool(v) for k, v in PARSERS.items()}
    app.logger.info("Available parsers: %s", available)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
