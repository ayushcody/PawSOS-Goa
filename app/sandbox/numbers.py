"""Invented phone numbers for public-demo sandboxes. No database imports here, so
routing code can use it without import cycles.

A sandbox number is +91001, a 6-digit sandbox id, then one digit for the persona.
It starts +91 0, which no Indian mobile does, so it can never reach a real person.
"""

import re
import secrets

PREFIX = "+91001"
ID_DIGITS = 6
# Who a visitor can be on the citizen side. A second citizen shows duplicate merging.
CITIZENS = {"c1": "1", "c2": "2"}
_NUMBER = re.compile(rf"^\{PREFIX}\d{{{ID_DIGITS + 1}}}$")


def new_id() -> str:
    return f"{secrets.randbelow(10**ID_DIGITS):0{ID_DIGITS}d}"


def number_for(sandbox_id: str, persona: str) -> str:
    return f"{PREFIX}{sandbox_id}{CITIZENS[persona]}"


def key_for(sandbox_id: str) -> str:
    return f"{PREFIX}{sandbox_id}"


def key_of(number: str | None) -> str | None:
    """The sandbox a number belongs to (the number without its last digit), or None."""
    if number and _NUMBER.match(number):
        return number[:-1]
    return None
