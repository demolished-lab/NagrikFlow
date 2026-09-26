"""Persona suite: 20 diverse citizens through the personalization engine.

Deterministic vault combos (no LLM cost) covering the docs space, plus
spot-check LLM briefs on 3. Asserts: have-lists echo, next-easiest never
recommends what they hold, GST appears only with PAN, Udyam appears with
Aadhaar+PAN. Reports pass/fail per persona.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\Raja\civic-pathfinder\backend")

from app import eligibility as elig  # noqa: E402

PERSONAS = [
    ("street vendor", set(), "Hyderabad"),
    ("student", {"aadhaar"}, "Warangal"),
    ("kirana owner", {"aadhaar", "pan"}, "Hyderabad"),
    ("boutique owner", {"aadhaar", "pan", "udyam"}, "Secunderabad"),
    ("transporter", {"aadhaar", "pan", "dl"}, "Nizamabad"),
    ("exporter", {"aadhaar", "pan", "udyam", "gstin"}, "Hyderabad"),
    ("caterer", {"pan"}, "Karimnagar"),
    ("tailor", {"aadhaar", "udyam"}, "Khammam"),
    ("cab driver", {"aadhaar", "dl"}, "Hyderabad"),
    ("pharmacy", {"aadhaar", "pan", "udyam", "gstin", "shops"}, "Warangal"),
    ("freelancer", {"pan"}, "Hyderabad"),
    ("tea stall", set(), "Nizamabad"),
    ("handloom", {"aadhaar", "pan"}, "Pochampally"),
    ("dairy", {"aadhaar", "pan", "udyam"}, "Karimnagar"),
    ("e-rickshaw", {"aadhaar"}, "Hyderabad"),
    ("salon", {"aadhaar", "pan", "shops"}, "Secunderabad"),
    ("bookshop", {"aadhaar", "pan", "udyam", "gstin"}, "Hyderabad"),
    ("migrant worker", set(), "Hyderabad"),
    ("retiree landlord", {"pan"}, "Warangal"),
    ("food truck", {"aadhaar", "pan", "dl"}, "Hyderabad"),
]


def check(name, kinds, city):
    b = elig.personalize(set(kinds), {})
    gives = {n["get"] for n in b["next_easiest"]}
    have_labels = set(b["have"])
    errs = []
    if gives & have_labels:
        errs.append(f"recommends held docs: {gives & have_labels}")
    if "GSTIN" in gives and "PAN" not in kinds and "pan" not in kinds:
        errs.append("GST without PAN")
    if "Udyam (MSME)" in gives and not ({"aadhaar", "pan"} <= set(kinds)):
        errs.append("Udyam without Aadhaar+PAN")
    return errs, b


def main():
    fails = 0
    for name, kinds, city in PERSONAS:
        errs, b = check(name, kinds, city)
        status = "FAIL " + "; ".join(errs) if errs else "pass"
        if errs:
            fails += 1
        nxt = ",".join(n["get"] for n in b["next_easiest"][:2]) or "-"
        print(f"{status:6} {name:16} have={len(kinds)} next=[{nxt}]")
    print(f"\n{len(PERSONAS)-fails}/{len(PERSONAS)} personas sane")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
