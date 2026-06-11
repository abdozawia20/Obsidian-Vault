---
tags: [legal, dpa, data-processing, gdpr, gatom]
document-type: Data Processing Agreement
version: "1.0"
effective-date: 2026-06-11
parent: License-Agreement-v1.0
governing-regulation: [GDPR Art. 28, international data protection standards]
---

# SCHEDULE 1 — DATA PROCESSING AGREEMENT (DPA)
**Attached to License Agreement v1.0 | Effective: [DATE]**

---

## 1. PURPOSE AND SCOPE

This Data Processing Agreement ("DPA") forms part of the Software License Agreement between Gatom ("Processor") and Licensee ("Controller") and governs the processing of personal data by Gatom on behalf of Licensee in connection with the Software.

---

## 2. ROLES

| Role | Party | Description |
|---|---|---|
| **Data Controller** | Licensee | Determines the purposes and means of processing personal data |
| **Data Processor** | Gatom | Processes personal data on behalf of the Controller |

---

## 3. SUBJECT MATTER OF PROCESSING

**Nature:** Hosting, storage, access management, backup, and processing of Client Data within the Software platform.

**Purpose:** To provide the Software services as described in the License Agreement.

**Duration:** For the term of the License Agreement plus the 30-day Post-Termination Export Window.

**Types of Personal Data Processed:**

| Category | Examples |
|---|---|
| Identification data | Full name, national ID (where required by platform function) |
| Contact data | Email address, phone number, mailing address |
| Business data | Company name, job title, role |
| Transactional data | Rental records, invoices, payment status |
| Usage data | Login timestamps, feature usage logs, IP addresses |

**Data Subjects:** Licensee's employees, contractors, customers, and tenants/clients managed through the platform.

---

## 4. PROCESSOR OBLIGATIONS

Gatom as Processor shall:

4.1 Process personal data only on documented instructions from Licensee (the License Agreement and this DPA constitute such instructions), unless required to do so by applicable law;

4.2 Ensure that personnel authorized to process personal data are bound by appropriate confidentiality obligations;

4.3 Implement appropriate technical and organizational security measures as described in Section 6 of this DPA;

4.4 Not engage any sub-processor without Licensee's prior written authorization (general authorization is granted via the Sub-Processor List in Appendix 1);

4.5 Assist Licensee in responding to data subject rights requests (access, rectification, deletion, portability) to the extent technically feasible;

4.6 Assist Licensee in meeting obligations under applicable data protection laws including data breach notification requirements;

4.7 Upon termination, delete or return all personal data as specified in Section 12 of the License Agreement;

4.8 Make available all information reasonably necessary to demonstrate compliance with this DPA.

---

## 5. CONTROLLER OBLIGATIONS

Licensee as Controller shall:

5.1 Ensure it has a valid legal basis for processing all personal data submitted to the Software;

5.2 Provide accurate instructions to Gatom and ensure such instructions comply with applicable law;

5.3 Be responsible for obtaining any consents required from data subjects;

5.4 Notify Gatom of any applicable data protection requirements that may affect Gatom's processing activities.

---

## 6. SECURITY MEASURES

Gatom implements the following technical and organizational measures:

| Measure | Implementation |
|---|---|
| Encryption in Transit | TLS 1.2+ for all data transmission |
| Encryption at Rest | AES-256 encryption for stored data |
| Access Control | Role-based access control; minimum privilege principle |
| Authentication | Strong password requirements; MFA available |
| Audit Logging | All access and modification events logged |
| Data Backup | Daily automated backups with 30-day retention |
| Vulnerability Management | Regular security patching; annual penetration testing |
| Personnel Training | Annual data protection training for all staff with data access |
| Incident Response | Documented breach response procedure (see Section 7) |

---

## 7. DATA BREACH NOTIFICATION

7.1 Gatom shall notify Licensee without undue delay, and in any event within **72 hours** of becoming aware of a personal data breach affecting Client Data.

7.2 Notification shall include (to the extent available at the time):
- Nature of the breach and categories of data affected;
- Approximate number of data subjects affected;
- Likely consequences of the breach;
- Measures taken or proposed to address the breach.

7.3 In cases where timely notification is prevented by force majeure, Gatom shall notify Licensee as soon as practicable.

---

## 8. INTERNATIONAL DATA TRANSFERS

8.1 Client Data is stored and processed primarily within **[DATA CENTER REGION — e.g., Egypt / EU]**.

8.2 Where personal data is transferred outside the country of the Controller, such transfers shall be subject to:
- **Standard Contractual Clauses (SCCs)** as approved by the European Commission, for EU data subjects;
- **Equivalent contractual safeguards** aligned with internationally recognized data protection frameworks for all other data subjects;
- Any other legally required transfer mechanism as applicable to the data subject's jurisdiction, as notified by the Controller.

8.3 Licensee authorizes Gatom to transfer personal data to sub-processors listed in Appendix 1, subject to equivalent data protection safeguards.

---

## 9. SUB-PROCESSORS

*See Appendix 1 — Sub-Processor List for current sub-processors authorized to process Client Data.*

Gatom shall notify Licensee of any intended changes to the Sub-Processor List at least **14 days in advance**, providing Licensee the opportunity to object.

---

## 10. DATA SUBJECT RIGHTS

Gatom shall assist Licensee in fulfilling the following data subject rights requests within **30 days** of receipt:

| Right | Description |
|---|---|
| Access | Provide a copy of personal data held |
| Rectification | Correct inaccurate or incomplete data |
| Erasure | Delete personal data ("right to be forgotten") |
| Portability | Export data in machine-readable format |
| Objection | Restrict or object to specific processing activities |

---

## 11. APPLICABLE REGULATIONS

This DPA is designed to operate in compliance with applicable data protection laws across jurisdictions, including but not limited to:

- **EU General Data Protection Regulation (GDPR) 2016/679** — for Licensees or data subjects in the EU/EEA
- **UK GDPR / Data Protection Act 2018** — for UK data subjects
- **General data protection principles** recognized internationally, including purpose limitation, data minimization, accuracy, storage limitation, and security
- **ePrivacy Directive** — for cookie and electronic communications data

The applicable regulation in any specific case is determined by the location of the data subjects and the Controller's operating jurisdiction.

---

## SIGNATURES

This DPA is incorporated into and forms part of the License Agreement. By signing the License Agreement, both Parties agree to the terms of this DPA.

---

*Document: Schedule-1-DPA-v1.0 | Gatom Legal | Effective: 2026-06-11*

---

## APPENDIX 1 — SUB-PROCESSOR LIST

*Last Updated: 2026-06-11*

| Sub-Processor | Service | Location | Safeguard |
|---|---|---|---|
| [Cloud Provider — e.g., AWS / Hetzner] | Infrastructure hosting & storage | [Region] | SCCs / Data Center Agreement |
| [Email Provider — e.g., SendGrid] | Transactional email delivery | [Region] | SCCs |
| [Analytics — e.g., Plausible / internal] | Usage analytics | [Region] | Privacy-preserving / No personal data |
| [Payment Processor — e.g., Stripe / Paymob] | Payment processing | [Region] | PCI-DSS compliant; no card data stored by Gatom |
| [Backup Provider] | Automated backups | [Region] | Encrypted backups |

> ℹ️ This list will be updated as sub-processors change. Licensees will receive 14 days' advance notice of material changes.
