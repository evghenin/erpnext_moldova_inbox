### Moldova Supplier Inbox

Shared ERPNext mailbox intake for supplier emails. Requires ERPNext / Frappe v15.

The app stores one **Supplier Inbox Email** per incoming message. Other Moldova apps register handlers and create their own documents from the attachments. This app does not parse facturas, payment bills, or bank reports.

### Behavior

- ERPNext pulls the mailbox through a normal Email Account. On the IMAP folder, **Append To** is **Supplier Inbox Email**.
- One received message becomes one Supplier Inbox Email. The letter itself, including its Message-ID, stays on the linked Communication. The same message is not stored twice because ERPNext already skips a Communication with that Message-ID.
- The list shows the original supplier, not the mailbox that forwarded the message. A Gmail-style "Forwarded message" block supplies the sender name, sender email, and subject. Without that block, the Communication sender and subject are used, with a leading Fwd/Re removed from the subject.
- Handlers read files only from the Supplier Inbox Email. A loose attachment is linked there to the file already stored on the Communication, without a second copy. Zip archives are not linked; their files are extracted and saved as new files, including a zip nested inside another zip. A broken or encrypted archive does not cancel the letter or the other files.
- After insert, every `inbound_email_handlers` hook is queued separately. One handler failure does not stop the others.
- A child table records each handler as `Queued`, `Processed`, `Skipped`, or `Failed`. The **Retry Handlers** button runs only `Failed` handlers and handlers that have no row yet.

### Handler contract

A consuming app adds a hook and does not need to be a required app of Inbox:

```python
inbound_email_handlers = [
    "erpnext_moldova_efactura.inbox.handle_inbound_email",
]
```

The function receives the Supplier Inbox Email name. It reads that document's own File attachments and does not open the Communication to look for the zip or the original mail files. It returns `None` when the message is not its concern, or `{"doctype": "...", "name": "..."}` when it creates a document. An exception is stored on that handler row as `Failed`.

### Archive passwords

Encrypted zips are skipped. The Supplier Inbox Email is still created, and an Error Log says which file could not be opened.

Passwords are not stored yet. When a supplier sends a protected archive, Supplier Inbox Settings will gain a list of passwords. Unpacking will try those passwords in order. A password that does not fit is not an error for the whole letter: that archive stays unopened and the rest of the files remain attached.

EFactura, banking, and other apps keep working when Inbox is not installed. Their mail handlers are optional.

### Installation

Requires ERPNext / Frappe v15. Install release **1.0.0**:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/evghenin/erpnext_moldova_inbox.git --branch v1.0.0
bench --site your-site install-app erpnext_moldova_inbox
bench --site your-site migrate
bench restart
```

`bench get-app` checks out the tag `v1.0.0`. On the Email Account, **Append To** for the IMAP folder must be **Supplier Inbox Email**. **Supplier Inbox Settings** can set that, together with incoming mail and sync of messages that were already read.

### Update

From the bench, move the app to the release tag and migrate. This does not switch the app to the `develop` branch.

```bash
cd $PATH_TO_YOUR_BENCH
cd apps/erpnext_moldova_inbox
git fetch --tags
git checkout v1.0.0
cd ../..
bench --site your-site migrate
bench build --app erpnext_moldova_inbox
bench restart
```

Repeat `git fetch --tags` and `git checkout` when a newer tag is published, then migrate and restart again. After an update, use **Create Missing Emails** on the Supplier Inbox Email list only for messages that were received before the app created those documents. New mail is picked up by the normal Email Account pull.

### Plan

The first implementation is described in [docs/plan.md](docs/plan.md).

### License

MIT
