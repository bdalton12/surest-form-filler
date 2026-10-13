"""Prepare independent claims from recurring services and service dates."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation


DAYS_PER_BATCH = 3
SERVICES_PER_DAY = 3
MAX_SERVICES_PER_BATCH = DAYS_PER_BATCH * SERVICES_PER_DAY


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid charge or payment: {value!r}") from exc
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError(f"Expected a nonnegative dollar amount with at most two decimals: {value!r}")
    return amount


def prepare_claim_batches(form_data):
    """Return separate form data copies; leave the source configuration untouched.

    Without service_dates, retain the existing explicit-entry format.
    With service_dates, repeat the three templates for three dates per claim.
    """
    if "service_dates" not in form_data:
        entries = form_data["form_6_entries"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_SERVICES_PER_BATCH:
            raise ValueError(f"The explicit-entry format supports 1 to {MAX_SERVICES_PER_BATCH} services.")
        batch = deepcopy(form_data)
        for entry in batch["form_6_entries"]:
            entry.pop("add_another", None)
        return [batch]

    dates = form_data["service_dates"]
    templates = form_data["form_6_entries"]
    if not isinstance(dates, list) or not dates:
        raise ValueError("service_dates must be a nonempty list of MM/DD/YYYY dates.")
    for date in dates:
        if not isinstance(date, str):
            raise ValueError("Each service date must be a MM/DD/YYYY string.")
        try:
            datetime.strptime(date, "%m/%d/%Y")
        except ValueError as exc:
            raise ValueError(f"Invalid service date: {date!r}; use MM/DD/YYYY.") from exc
    if len({datetime.strptime(date, "%m/%d/%Y").date() for date in dates}) != len(dates):
        raise ValueError("service_dates contains duplicate dates.")
    if not isinstance(templates, list) or len(templates) != SERVICES_PER_DAY:
        raise ValueError("Recurring claims require exactly three form_6_entries templates.")
    for service in templates:
        if not isinstance(service, dict) or any(
            not isinstance(service.get(field), str) or not service[field].strip()
            for field in ("procedure_code", "diagnosis_code", "charges")
        ):
            raise ValueError("Each service needs procedure_code, diagnosis_code, and charges strings.")
        money(service["charges"])

    batch_count = (len(dates) + DAYS_PER_BATCH - 1) // DAYS_PER_BATCH
    payments = form_data.get("batch_amounts_paid")
    if payments is None:
        # amount_paid covers one date's services, just like the service templates.
        paid_per_date = money(form_data.get("form_7", {}).get("amount_paid", "0.00"))
        payments = [
            paid_per_date * len(dates[start:start + DAYS_PER_BATCH])
            for start in range(0, len(dates), DAYS_PER_BATCH)
        ]
    if not isinstance(payments, list) or len(payments) != batch_count:
        raise ValueError(f"batch_amounts_paid must contain {batch_count} amounts, one per batch.")
    payments = [money(payment) for payment in payments]

    batches = []
    for start in range(0, len(dates), DAYS_PER_BATCH):
        batch = deepcopy(form_data)
        batch["service_dates"] = dates[start:start + DAYS_PER_BATCH]
        entries = [
            {**deepcopy(service), "date_of_service": date}
            for date in batch["service_dates"]
            for service in templates
        ]
        for entry in entries:
            entry.pop("add_another", None)
        batch["form_6_entries"] = entries
        batch.setdefault("form_7", {})["total_charge"] = format(
            sum((money(entry["charges"]) for entry in entries), Decimal("0.00")), ".2f"
        )
        batch["form_7"]["amount_paid"] = format(payments[len(batches)], ".2f")
        batches.append(batch)
    return batches
