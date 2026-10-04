# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime

from erpnext_moldova_inbox.moldova_supplier_inbox.attachments import collect_mail_files
from erpnext_moldova_inbox.moldova_supplier_inbox.original_mail import original_message


FINISHED = ("Processed", "Skipped")


def get_handler_paths():
	paths = []
	for app in frappe.get_installed_apps():
		for path in frappe.get_hooks("inbound_email_handlers", app_name=app) or []:
			if path not in paths:
				paths.append(path)
	return paths


def handlers_enabled():
	if not frappe.db.exists("DocType", "Supplier Inbox Settings"):
		return True
	return bool(frappe.db.get_single_value("Supplier Inbox Settings", "enabled"))


def queue_handlers(inbound_email):
	"""Create missing handler rows and enqueue one job per handler that should run."""
	if not handlers_enabled():
		return

	doc = frappe.get_doc("Supplier Inbox Email", inbound_email)
	existing = {row.handler: row for row in doc.handlers}
	to_run = []

	for path in get_handler_paths():
		row = existing.get(path)
		if row and row.status in FINISHED:
			continue
		if row and row.status == "Queued":
			to_run.append(path)
			continue
		if not row:
			doc.append("handlers", {"handler": path, "status": "Queued"})
		else:
			row.status = "Queued"
			row.error = None
		to_run.append(path)

	if doc.has_value_changed("handlers") or doc.is_dirty():
		doc.save(ignore_permissions=True)

	run_now = bool(frappe.flags.in_test)
	for path in to_run:
		frappe.enqueue(
			"erpnext_moldova_inbox.moldova_supplier_inbox.dispatch.run_handler",
			queue="short",
			enqueue_after_commit=not run_now,
			now=run_now,
			inbound_email=doc.name,
			handler=path,
		)


def run_handler(inbound_email, handler):
	doc = frappe.get_doc("Supplier Inbox Email", inbound_email)
	row = next((child for child in doc.handlers if child.handler == handler), None)
	if not row or row.status in FINISHED:
		return

	row.attempt_time = now_datetime()
	try:
		result = frappe.get_attr(handler)(doc.name)
		if result is None:
			row.status = "Skipped"
			row.error = None
		else:
			row.status = "Processed"
			row.reference_doctype = result.get("doctype")
			row.reference_name = result.get("name")
			row.error = None
	except Exception:
		row.status = "Failed"
		row.error = frappe.get_traceback()
		frappe.log_error(title="Supplier Inbox Email handler failed", message=row.error)

	doc.save(ignore_permissions=True)


def recreate_missing(email_account):
	"""Create a Supplier Inbox Email for each received message that no longer has one."""
	created = []
	names = frappe.get_all(
		"Communication",
		filters={"email_account": email_account, "sent_or_received": "Received"},
		pluck="name",
	)
	for name in names:
		communication = frappe.get_doc("Communication", name)
		if communication.reference_doctype == "Supplier Inbox Email" and frappe.db.exists(
			"Supplier Inbox Email", communication.reference_name
		):
			continue
		inbox_email = frappe.get_doc(
			{"doctype": "Supplier Inbox Email", "email_account": email_account}
		).insert(ignore_permissions=True)
		communication.reference_doctype = "Supplier Inbox Email"
		communication.reference_name = inbox_email.name
		link_communication(communication)
		frappe.db.set_value(
			"Communication",
			communication.name,
			{"reference_doctype": "Supplier Inbox Email", "reference_name": communication.reference_name},
			update_modified=False,
		)
		created.append(communication.reference_name)
	return created


def link_communication(communication, method=None):
	"""Point the Supplier Inbox Email at the Communication Append To just created."""
	if communication.reference_doctype != "Supplier Inbox Email" or not communication.reference_name:
		return
	if communication.sent_or_received == "Sent":
		return
	if not frappe.db.exists("Supplier Inbox Email", communication.reference_name):
		return

	email_account = communication.email_account
	message_id = communication.message_id
	current = communication.reference_name

	if message_id and email_account:
		existing = frappe.db.get_value(
			"Communication",
			{
				"message_id": message_id,
				"email_account": email_account,
				"reference_doctype": "Supplier Inbox Email",
				"name": ["!=", communication.name],
			},
			"reference_name",
		)
		if existing and existing != current and frappe.db.exists("Supplier Inbox Email", existing):
			frappe.delete_doc("Supplier Inbox Email", current, ignore_permissions=True, force=True)
			communication.reference_name = existing
			return

	values = {
		"communication": communication.name,
		"email_account": email_account or frappe.db.get_value("Supplier Inbox Email", current, "email_account"),
	}
	values.update(
		original_message(
			communication.subject,
			communication.sender,
			communication.sender_full_name,
			communication.text_content,
		)
	)
	frappe.db.set_value("Supplier Inbox Email", current, values, update_modified=False)
	collect_mail_files(current, communication.name)
