"""Generate sample_docs/security-policy.pdf (a multi-page PDF, to exercise page citations).

Run inside the api container:  docker compose run --rm -v "$PWD:/repo" api python /repo/scripts/make_sample_pdf.py
"""

from pathlib import Path

import pymupdf

PAGES = [
    """Lumen Labs Information Security Policy
(Fictional company - sample data for DocChat)

1. Purpose and scope
This policy applies to all employees, contractors and systems of Lumen Labs. It sets the
minimum security requirements for handling company and customer data.

2. Data classification
Data is classified as Public, Internal, Confidential or Restricted. Customer content is
always Restricted. Restricted data may only be stored in approved systems and must never be
copied to personal devices or personal cloud accounts.""",
    """3. Passwords and authentication
Passwords must be at least 14 characters long. Multi-factor authentication (MFA) is mandatory
for all company accounts; hardware security keys are required for administrators.
Passwords must be stored in the company password manager and never shared.

4. Device security
Laptops must use full-disk encryption and lock automatically after 5 minutes of inactivity.
Operating system security updates must be installed within 7 days of release.
Lost or stolen devices must be reported to security@lumenlabs.example within 1 hour.""",
    """5. Access reviews
Managers review their team's access to production systems every quarter. Access for people
who leave the company is revoked on their last working day.

6. Incident response
Suspected security incidents must be reported immediately in the #security-incidents channel.
Severity 1 incidents (customer data exposure) trigger the on-call security engineer within
15 minutes. Affected customers are notified within 72 hours of a confirmed personal-data
breach, in line with GDPR.

7. Policy review
This policy is reviewed every 12 months by the Head of Security.""",
]


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "sample_docs" / "security-policy.pdf"
    doc = pymupdf.open()
    for text in PAGES:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 780), text, fontsize=11, fontname="helv")
    doc.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
