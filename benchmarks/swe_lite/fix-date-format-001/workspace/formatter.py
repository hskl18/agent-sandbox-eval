from datetime import date


def format_date(value: date) -> str:
    return value.strftime("%m/%d/%Y")

