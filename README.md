# Surest Claim Form Auto-Fill Tool

## Overview
This is a Python-based tool that auto-fills the Surest claim form using data from JSON files. The tool reads form data from `form_data.json` and auto-fills the form using the logic defined in `main.py`.

## Usage
1. Ensure your form data is properly formatted in `form_data.json`
2. Make sure you have a PDF invoice available.
3. Run the main script:

```bash
python3 main.py
```

## Recurring monthly services

Add `service_dates` to `form_data.json` and keep exactly three service templates
in `form_6_entries`. Replace the example codes and charges with your invoice values:

```json
"service_dates": ["10/01/2026", "10/03/2026", "10/05/2026", "10/07/2026"],
"form_6_entries": [
    {"procedure_code": "YOUR_CODE_1", "diagnosis_code": "YOUR_DIAGNOSIS", "charges": "100.00"},
    {"procedure_code": "YOUR_CODE_2", "diagnosis_code": "YOUR_DIAGNOSIS", "charges": "50.00"},
    {"procedure_code": "YOUR_CODE_3", "diagnosis_code": "YOUR_DIAGNOSIS", "charges": "25.00"}
]
```

The script preserves date order and groups **three dates per claim**, producing nine
services. A final batch with one or two dates produces three or six services.
`date_of_service` is generated
automatically. Omit `add_another` from the JSON: the script selects Yes while services
remain in the current batch, and No on its final service, even if more dates remain
for a later claim. Each batch's `form_7.total_charge` is
calculated from its services; the configured monthly total is ignored in this mode.

Preview the batches, then submit all of them in one browser session:

```bash
python main.py --preview
python main.py
python main.py --step
```

Each batch gets a fresh claim form. After uploading the PDF, the script checks for
submission confirmation. If the claim is already submitted, it opens the next form
without clicking another button. If a review page still requires submission, it
clicks the available submit button and waits for confirmation first.
It closes the browser after the final batch. With `--step`,
it pauses on each page, before submitting each claim, and before closing the browser.

Use `python main.py --batch 3` to start at batch 3 and continue through the remaining
batches. Use `python main.py --batch 3 --single-batch` to submit only batch 3.
The console reports each confirmed batch. Submission history is not saved between
runs: keep your confirmation numbers and completed batch numbers so rerunning the
script does not repeat completed claims. If a batch fails or confirmation cannot be
detected, the script stops and keeps the browser open until you press Enter. Check
the claim status before restarting at the appropriate batch.

`form_11.pdf_path` is used for every batch. Confirm with Surest whether the same
monthly invoice can support these separate claims, or whether separate invoices
are needed.

`form_7.amount_paid` is the total paid for **one service date's three services**.
For example, `"175.00"` produces a payment of `"525.00"` for a three-date batch,
`"350.00"` for a two-date batch, and `"175.00"` for a one-date batch.
If all three services were paid in full,
enter the sum of their charges. Use `"0.00"` when nothing was paid.

If payments differ between dates, you can override this calculation with a
top-level `batch_amounts_paid` list containing one amount for each batch, for example
`["525.00", "100.00"]` for the four dates above. When present, this list takes
precedence over `amount_paid`. If you have an existing override list, update it to
match the new groups of three dates.
In the original explicit-entry format without `service_dates`, `amount_paid` is
used as entered for that single claim.

Without `service_dates`, the original explicit-entry format remains supported
(up to nine entries). Use `--data path/to/month.json` to select another data file.
