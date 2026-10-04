# Supplier Inbox Email

ERPNext already downloads the mailbox. This app turns each incoming message into one document and calls every registered handler. It does not import Orange or ARAX facturas, payment bills, or bank files.

## App

`erpnext_moldova_inbox`. `required_apps = ["erpnext"]`. No dependency on EFactura, banking, or customs.

Python 3.10, double quotes, tabs, Ruff, 110-character lines.

## DocType Supplier Inbox Email

Created by Email Account **Append To**. Fields:

- Email Account
- link to the Communication ERPNext already created

Sender, subject, time, body, attachments, and Message-ID stay on that Communication. A repeated delivery of the same message does not create a second Communication, so it does not create a second Supplier Inbox Email. Outgoing mail is ignored.

Child table **Supplier Inbox Email Handler**:

- handler dotted path
- status: `Queued`, `Processed`, `Skipped`, `Failed`
- `reference_doctype` and `reference_name` when the handler created a document
- error text
- attempt time

A retry enqueues `Failed` rows and handlers that have no row. `Processed` and `Skipped` are not called again.

## Dispatch

On `Supplier Inbox Email` after insert, read `inbound_email_handlers` from every installed app. Enqueue one background job per handler so a failure does not roll back the email document and does not block the other handlers.

Hook in the consuming app:

```python
inbound_email_handlers = [
    "erpnext_moldova_efactura.inbox.handle_inbound_email",
]
```

The function receives the Supplier Inbox Email name. It chooses its own attachments. It returns `None` to skip, or `{"doctype": "...", "name": "..."}` when it created a document. An exception sets that row to `Failed`.

Idempotency of the business document stays in the handler. Inbox only stops itself from calling a finished handler twice.

## Outside this app

Purchase Factura import, payment invoice drafts, Maib, MIA, NovaPay, and Megamega. EFactura does not store the Email Account. The Orange/ARAX handler is a later change in EFactura and is optional: EFactura works unchanged when Inbox is absent.

## Tests

On `test.localhost`:

- an email with two attachments creates one Supplier Inbox Email
- two test handlers both run
- an exception in the first leaves the second `Processed`
- a second pass does not create another Supplier Inbox Email and does not call handlers already `Processed` or `Skipped`
