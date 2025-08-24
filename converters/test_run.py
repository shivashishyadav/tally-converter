"""
Quick test runner for E-Commerce → Tally converters
Run without Flask: `python test_run.py input.xlsx seller_state parser`
Example:
    python test_run.py ./samples/Amazon_B2B.csv "Uttar Pradesh" amazon
"""

import sys
import os
import pandas as pd

# Import converters
from converters import amazon, flipkart, meesho, tcs, base


PARSERS = {
    "amazon": amazon.convert,
    "flipkart": flipkart.convert,
    "meesho": meesho.convert,
    "tcs": tcs.convert,
    "generic": base.generic_convert
}


def run(file_path: str, seller_state: str, parser_name: str):
    if parser_name not in PARSERS:
        print(f"Unknown parser: {parser_name}")
        print(f"Available: {list(PARSERS.keys())}")
        return

    parser_fn = PARSERS[parser_name]

    # Load input file
    if file_path.lower().endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # Convert
    out = parser_fn(df, seller_state)

    # Save as Excel
    out_file = f"tally_output_{parser_name}.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        out.to_excel(writer, sheet_name="Sales", index=False)
        pd.DataFrame(columns=out.columns).to_excel(writer, sheet_name="Sales Return", index=False)

    print(f"Converted {file_path} using {parser_name} parser → {out_file}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python test_run.py <input_file> <seller_state> <parser>")
        print("Example: python test_run.py Amazon_B2B.csv 'Uttar Pradesh' amazon")
        sys.exit(1)

    file_path = sys.argv[1]
    seller_state = sys.argv[2]
    parser_name = sys.argv[3].lower()

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    run(file_path, seller_state, parser_name)
