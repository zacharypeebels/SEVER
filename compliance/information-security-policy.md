# SEVER — Information Security Policy

**Version 1.0 · Adopted July 7, 2026 · Owner: Zachary Peebels, Founder (Information Security Officer)**
**Review cadence: annually, or upon material change to systems or regulations**

## 1. Purpose and scope

This policy governs the protection of all systems and data operated by SEVER ("the
organization"), including consumer financial data received via the Plaid API, consumer
identity data, and supporting infrastructure. It applies to all personnel (currently the
founder) and all production systems, which are hosted on Amazon Web Services (AWS).

## 2. Roles and responsibilities

The Founder acts as Information Security Officer (ISO) and is accountable for implementing,
operating, and reviewing this policy. Security contact: the monitored address provided in
vendor questionnaires.

## 3. Data classification

| Class | Examples | Handling |
|---|---|---|
| Consumer financial data | Transaction data from Plaid, subscription ledgers | Encrypted at rest and in transit; access via authenticated application paths only |
| Consumer identity data | Email addresses, authentication records | Managed in Amazon Cognito; passwords hashed by AWS, never accessible to the organization |
| Secrets | API credentials, database credentials, signing tokens | AWS Secrets Manager only; never in source code, tickets, or chat |
| Public data | Marketing site, application code | No restriction |

## 4. Infrastructure security

- All client-server traffic is encrypted with TLS 1.2+; plaintext HTTP is redirected.
- All consumer data is encrypted at rest with AES-256 via AWS KMS (Amazon RDS).
- Production databases are not internet-addressable; network access is restricted by
  security groups to the application tier only, which is itself reachable only via the
  load balancer.
- Compute is containerized (AWS Fargate) and stateless; no consumer data resides on
  compute instances.

## 5. Access control

Access control requirements are defined in the companion **Access Control Policy**,
incorporated by reference: least privilege, role-based access, MFA for administrative
access, no shared or long-lived credentials, and quarterly access reviews.

## 6. Vulnerability and patch management

- Dependency vulnerability scanning (pip-audit) runs in CI and **blocks deployment** on
  known CVEs in application dependencies.
- Container images are scanned on every push (Amazon ECR scanning).
- Static application security testing (CodeQL) runs on every change and weekly.
- Automated dependency update proposals (Dependabot) run weekly across application,
  container, and CI dependencies, which also surfaces end-of-life software.
- Patch SLA: critical vulnerabilities within 7 days; high within 30 days; others within
  90 days. Because scanning gates the deploy pipeline, critical issues are in practice
  remediated before any release.

## 7. Logging and monitoring

- All AWS management-plane actions are recorded by AWS CloudTrail (multi-region, log-file
  integrity validation enabled) to an access-restricted S3 bucket.
- Application and service logs are retained in Amazon CloudWatch Logs.

## 8. Incident response

Upon suspected compromise: (1) contain — revoke affected credentials/keys, isolate
affected services; (2) assess scope using CloudTrail and application logs; (3) remediate
and redeploy from source; (4) notify affected consumers and partners (including Plaid)
without undue delay and within 72 hours of confirmation; (5) document a post-incident
review with corrective actions.

## 9. Vendor management

Material processors: AWS (hosting, identity, storage), Plaid (financial data
connectivity), GitHub (source control, CI/CD). Each is a recognized processor operating
its own compliance program (e.g., SOC 2, ISO 27001). New processors require ISO approval.

## 10. Data retention and disposal

Defined in the companion **Data Retention and Disposal Policy**, incorporated by
reference.

## 11. Policy review

This policy is reviewed at least annually by the ISO and updated upon material changes to
architecture, personnel, or applicable law.
