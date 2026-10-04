# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_moldova_inbox.moldova_supplier_inbox.dispatch import recreate_missing


class SupplierInboxSettings(Document):
	@frappe.whitelist()
	def configure_email_account(self):
		if not self.email_account:
			frappe.throw(_("Select an Email Account first."))

		account = frappe.get_doc("Email Account", self.email_account)
		changes = []

		if not account.enable_incoming:
			account.enable_incoming = 1
			changes.append(_("Enabled incoming"))

		if not account.use_imap:
			account.use_imap = 1
			changes.append(_("Enabled IMAP"))

		if account.email_sync_option != "ALL":
			account.email_sync_option = "ALL"
			changes.append(_("Set sync to all messages, including those already read"))

		if not account.imap_folder:
			account.append("imap_folder", {"folder_name": "INBOX", "append_to": "Supplier Inbox Email"})
			changes.append(_("Added IMAP folder INBOX with Append To Supplier Inbox Email"))
		else:
			for folder in account.imap_folder:
				if folder.append_to == "Supplier Inbox Email":
					continue
				folder.append_to = "Supplier Inbox Email"
				changes.append(
					_("Set Append To to Supplier Inbox Email on folder {0}").format(folder.folder_name or "INBOX")
				)

		if not changes:
			return {"changed": False, "message": _("Email Account {0} is already set to Supplier Inbox Email.").format(account.name)}

		account.save(ignore_permissions=True)
		return {
			"changed": True,
			"message": _("Email Account {0}: {1}").format(account.name, "; ".join(changes)),
		}

	@frappe.whitelist()
	def recreate_missing_emails(self):
		if not self.email_account:
			frappe.throw(_("Select an Email Account first."))
		created = recreate_missing(self.email_account)
		if not created:
			return {"created": 0, "message": _("Every received message already has a Supplier Inbox Email.")}
		return {
			"created": len(created),
			"message": _("Created {0} Supplier Inbox Email documents.").format(len(created)),
		}
