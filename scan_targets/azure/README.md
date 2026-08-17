# Azure Scan Targets

This directory contains intentionally insecure Azure resources for use with the
Complisoc Azure profile. Checkov scans this directory when the Azure scan profile
is selected.

## Resources

| Resource | Misconfiguration |
|----------|------------------|
| `storageAccount` | Public container access enabled (`publicAccess: Container`, `allowBlobPublicAccess: true`) and weak TLS (`minimumTlsVersion: TLS1_0`). |
| `nsg` | Over-permissive inbound rule allowing all traffic from any source to any destination. |
| `managedDisk` | Disk encryption is explicitly disabled (`encryptionSettings.enabled: false`). |

## Scanning

Checkov natively supports Bicep scanning:

```bash
checkov -d scan_targets/azure/
```

When running a Complisoc scan with the Azure profile, these resources are scanned
automatically alongside Defender cloud-findings ingestion.
