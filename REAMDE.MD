# E-Commerce → Tally Converter

A simple **Flask web app** to convert Amazon, Flipkart, Meesho, and TCS invoice files into **Tally-ready Excel sheets** (Sales + Sales Return).

## Features
- Upload CSV/XLSX invoices.
- Auto-parse Amazon, Flipkart, Meesho, TCS formats.
- GST split based on Seller State.
- Download ready-to-import Tally Excel.

## 📂 Project Structure
```tally_converter/
    │── app.py # Flask entry point
    │── converters/
    │ ├── init.py
    │ ├── base.py # Shared utilities (date parsing, tax calc, tally schema)
    │ ├── amazon.py # Amazon parser
    │ ├── flipkart.py # Flipkart parser
    │ ├── meesho.py # Meesho parser
    │ ├── tcs.py # TCS parser
    │ └── generic.py # Fallback parser
    │── templates/
    │ └── index.html # Upload page (Bootstrap UI)
    │── static/
    │ └── style.css # Custom styling
    │── requirements.txt
    │── README.md
    │── .gitignore```