# MSB Label Print Service

Automated label printing service for the **Making Spirits Bright (MSB) Production Database**.

This service monitors exported label data, generates print jobs using the Brother bPAC SDK, and drives Brother label printers (e.g., P-touch P950NW) for container and display labeling workflows.

---

## Overview

The Label Print Service is designed for operational use during MSB production activities.

It supports:

- Automated batch printing  
- QR-coded labels for containers and displays  
- Integration with MSB database export pipelines  
- Robust logging and failure handling  
- Recovery of interrupted print batches  

This project is currently maintained as a private operational tool.

---

## Features

- Polling service for new label batches  
- Support for multiple label types  
- Uses Brother bPAC SDK templates (`.lbx`)  
- CSV-driven printing  
- Batch confirmation and failure handling  
- Detailed logging  
- Designed for unattended operation  

---

## Repository Structure

```
MSB_LabelPrintService/
│
├── label_poll_service_v*.py # Main polling services
├── bpac_* # Test and smoke scripts
├── confirm_last_batch.py # Batch confirmation tool
├── fail_last_batch.py # Batch failure tool
│
├── templates/ # Brother label templates (.lbx)
├── sql/ # Database export queries
├── csv/ # Input CSV files
│
├── logs/ # Runtime logs (not committed)
├── state/ # Service state files (not committed)
│
├── config.example.ini # Template configuration file
├── config.local.ini # Local secrets (ignored)
└── .gitignore
```

---

## Configuration

Copy the example configuration and provide local credentials:


copy config.example.ini config.local.ini


Edit `config.local.ini` with your environment-specific settings.

> ⚠️ **Do NOT commit `config.local.ini` — it contains secrets.**

---

## Requirements

- Windows environment  
- Python 3.x  
- Brother bPAC SDK installed  
- Compatible Brother label printer (e.g., P950NW)  
- Network or USB printer connectivity  

---

## Usage

Run the polling service:


python label_poll_service_v2.py


For testing:


python bpac_smoketest.py


---

## Logging

Logs are written to the `logs/` directory.

Batch-specific logs are stored under:


logs/batches/


---

## Operational Notes

- This service is intended to run continuously during production periods.  
- Printer error conditions must be resolved before batch processing can resume.  
- CSV files represent print jobs exported from the MSB database system.  

---

## Security

Sensitive configuration values are stored in `config.local.ini`, which is excluded from version control.

If credentials are exposed, rotate them immediately.

---

## Status

Active development / operational use for MSB production.

---

## Maintainer

**Greg Liebig**  
Engineering Innovations, LLC  
Making Spirits Bright — Sheboygan County  

---

## License

Private internal use only.