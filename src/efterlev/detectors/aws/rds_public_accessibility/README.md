# `aws.rds_public_accessibility`

Flags RDS instances and clusters configured with `publicly_accessible = true`.

## What this detector evidences

- **KSI-CNA-RNT** (Restricting Network Traffic) and **KSI-CNA-MAT** (Minimizing Attack Surface), both via SC-7.
- **800-53 controls:** AC-3 (Access Enforcement at the network layer), SC-7 (Boundary Protection).

## What it proves

An RDS resource (`aws_db_instance`, `aws_rds_cluster`, or `aws_rds_cluster_instance`) defined in the Terraform has `publicly_accessible` set to `true`. Per AWS docs, this gives the resource a public-internet-resolvable DNS name.

## What it does NOT prove

- That the RDS is actually reachable from the internet — the security groups attached to the resource determine ingress; this detector inspects only the publicly-accessible flag.
- That data flows ever cross the boundary, even if the network path exists.
- That IAM/DB-level credentials enforce strong auth.

## Detection signal

- `publicly_accessible = true` (boolean) → finding (`exposure_state="publicly_accessible"`).
- `publicly_accessible = false` or attribute absent → no evidence (the AWS default is private).
- `publicly_accessible` rendered as `${...}` (HCL interpolation or plan-JSON `(known after apply)`) → unparseable evidence.

## Known limitations

- The detector inspects per-resource state in isolation. A `publicly_accessible = true` RDS attached only to a private security group is *technically* still flagged here, but the upstream Gap Agent is the place where cross-resource reasoning lives.
