# SEVER — Data Retention and Disposal Policy

**Version 1.0 · Adopted July 7, 2026 · Owner: Zachary Peebels, Founder**
**Review cadence: annually**

## 1. Scope

Applies to all consumer data processed by SEVER: identity data (email, authentication
records), subscription ledger data, and financial transaction data received via the
Plaid API.

## 2. Retention schedule

| Data | Retention | Basis |
|---|---|---|
| Consumer identity (Cognito) | Life of the account | Service delivery |
| Subscription ledger (RDS) | Life of the account | Service delivery |
| Plaid-derived transaction data | Life of the bank connection; removed when the consumer disconnects a bank or deletes the account | Service delivery, data minimization |
| Encrypted database backups | 7 days (automated ageout) | Disaster recovery |
| Infrastructure audit logs (CloudTrail) | Retained for audit purposes | Legal/audit obligation |
| Application logs | Operational retention in CloudWatch | Operations |

SEVER does not retain consumer bank credentials at any time (Plaid tokenization), and
does not sell or share consumer data for advertising.

## 3. Consumer-initiated deletion (right to erasure)

Consumers may permanently delete their account at any time from within the application.
Deletion executes immediately and irreversibly:

1. All subscription and financial ledger rows for the account are deleted from the
   production database in a single transaction.
2. The consumer's identity record is deleted from Amazon Cognito.
3. Residual copies in encrypted backups age out automatically within 7 days.

Consumers may also export all data held about them (JSON) from within the application
at any time (data portability).

## 4. Disposal methods

- Live data: transactional SQL deletion on encrypted storage.
- Backups: automated expiry of encrypted snapshots (7 days).
- Decommissioned storage: AWS-managed cryptographic erasure (KMS key retirement renders
  ciphertext unrecoverable).

## 5. Compliance and review

This policy is designed to satisfy applicable consumer privacy laws (including
CCPA-style deletion and portability rights) and is reviewed at least annually or upon
material change to processing activities.
