"""Data Protection Officer Appointment Letter Template.

This document formally appoints the DPO as required under India's DPDP Act 2023.
Replace bracketed values with actual information before signing.
"""

from datetime import date


def generate_dpo_appointment(
    organization_name: str,
    dpo_name: str,
    dpo_contact: str,
    appointment_date: str,
    term_years: int = 3,
    section_number: str = "10",
    termination_notice: int = 30,
) -> str:
    """Generate formal DPO appointment letter."""
    expiry = date.fromisoformat(appointment_date).year + term_years
    
    return f"""OFFICE OF THE DATA PROTECTION OFFICER
{organization_name}

APPOINTMENT LETTER

Date: {appointment_date}

Subject: Appointment of Data Protection Officer under the Digital Personal Data Protection Act, 2023

1. APPOINTMENT

This letter confirms the appointment of Mr./Ms. {dpo_name} as the Data Protection Officer (DPO) of {organization_name} (hereinafter referred to as "the Organization").

This appointment is made pursuant to Section {section_number} of the Digital Personal Data Protection Act, 2023, and rules made thereunder.

2. TERM OF APPOINTMENT

The term of this appointment shall be for a period of {term_years} years, commencing from {appointment_date} and ending on {expiry}-09-27 (unless terminated earlier in accordance with the terms herein).

3. RESPONSIBILITIES

The DPO shall be responsible for:

a) Overseeing the Organization's compliance with the DPDP Act and rules thereunder;
b) Advising the Organization on its obligations under the Act;
c) Dealing with grievances from data principals and coordinating with the Data Protection Board of India;
d) Conducting Data Protection Impact Assessments (DPIAs) where required;
e) Maintaining records of data processing activities;
f) Acting as the point of contact for regulatory inquiries;
g) Ensuring timely breach notification to the Board and affected data principals.

4. ACCESS AND AUTHORITY

The DPO shall have:

a) Full access to all information and premises necessary to perform their duties;
b) Direct access to the highest level of management;
c) Authority to engage external consultants and auditors as needed;
d) Protection from retaliation or adverse action for performing their duties.

5. REPORTING STRUCTURE

The DPO shall report directly to the Chief Executive Officer / Board of Directors and shall have the authority to escalate matters directly to the Board in cases of serious compliance concerns.

6. COMPENSATION

The DPO shall receive compensation as mutually agreed upon between the parties, payable [monthly/quarterly/anually].

7. TERMINATION

This appointment may be terminated:

a) By mutual agreement;
b) By either party with {termination_notice} days written notice;
c) Immediately for cause, including but not limited to:
   - Material breach of this agreement;
   - Loss of required qualifications;
   - Criminal conviction;
   - Determination by the Data Protection Board.

Upon termination, the DPO shall cooperate in the transition of responsibilities.

8. CONFIDENTIALITY

The DPO shall maintain strict confidentiality regarding all data processing activities, personal data, and organizational information encountered in the performance of their duties, except where disclosure is required by law or with appropriate authorization.

9. INDEPENDENCE

The DPO shall perform their duties independently and without instruction from data controllers or processors, except as required by law or this appointment letter.

10. GOVERNING LAW

This appointment shall be governed by and construed in accordance with the laws of India, particularly the Digital Personal Data Protection Act, 2023.

IN WITNESS WHEREOF, the parties have executed this Appointment Letter on the date first above written.

___________________________
[Authorized Signatory]
[Name]
[Title]
{organization_name}

Acknowledged and Accepted:

___________________________
{dpo_name}
Data Protection Officer
Date: {appointment_date}

---
DPO Contact Information:
Name: {dpo_name}
Email: {dpo_contact}
Phone: [Insert Phone]
Address: [Insert Office Address]

Registered Grievance Email: grievance@[organization-domain].in
"""


if __name__ == "__main__":
    # Example usage
    letter = generate_dpo_appointment(
        organization_name="Civic Path Navigator",
        dpo_name="[DPO Name]",
        dpo_contact="[dpo@email.com]",
        appointment_date="2026-09-27",
        term_years=3,
    )
    print(letter)
    
    # Save to file
    with open("docs/DPO_APPOINTMENT_LETTER.md", "w", encoding="utf-8") as f:
        f.write(letter)
    print("\nAppointment letter saved to docs/DPO_APPOINTMENT_LETTER.md")
