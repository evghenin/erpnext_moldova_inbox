# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import io
import zipfile

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_moldova_inbox.moldova_supplier_inbox.attachments import collect_mail_files
from erpnext_moldova_inbox.moldova_supplier_inbox.dispatch import queue_handlers
from erpnext_moldova_inbox.moldova_supplier_inbox.original_mail import original_message


def handler_processed(inbound_email):
	frappe.flags.inbox_processed = frappe.flags.inbox_processed or []
	frappe.flags.inbox_processed.append(inbound_email)
	todo = frappe.get_doc({"doctype": "ToDo", "description": inbound_email}).insert(ignore_permissions=True)
	return {"doctype": todo.doctype, "name": todo.name}


def handler_skipped(inbound_email):
	frappe.flags.inbox_skipped = (frappe.flags.inbox_skipped or 0) + 1
	return None


def handler_failed(inbound_email):
	frappe.flags.inbox_failed = (frappe.flags.inbox_failed or 0) + 1
	raise RuntimeError("handler failed")


class TestInboundEmail(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.flags.inbox_processed = []
		frappe.flags.inbox_skipped = 0
		frappe.flags.inbox_failed = 0
		frappe.db.set_single_value("Supplier Inbox Settings", "enabled", 1)
		self._paths = [
			"erpnext_moldova_inbox.moldova_supplier_inbox.doctype.supplier_inbox_email.test_supplier_inbox_email.handler_failed",
			"erpnext_moldova_inbox.moldova_supplier_inbox.doctype.supplier_inbox_email.test_supplier_inbox_email.handler_processed",
			"erpnext_moldova_inbox.moldova_supplier_inbox.doctype.supplier_inbox_email.test_supplier_inbox_email.handler_skipped",
		]
		from unittest.mock import patch

		self._handlers = patch(
			"erpnext_moldova_inbox.moldova_supplier_inbox.dispatch.get_handler_paths",
			return_value=self._paths,
		)
		self._handlers.start()

	def tearDown(self):
		self._handlers.stop()
		super().tearDown()

	def test_forwarded_mail_keeps_the_supplier_sender_and_subject(self):
		parsed = original_message(
			"Fwd: Factura Orange - HOTEL LIFE SRL",
			"hotel.life.srl@gmail.com",
			"Hotel Life",
			"---------- Forwarded message ---------\n"
			"From: Orange <factura.electronica@orange.md>\n"
			"Date: Thu, Sep 24, 2026 at 6:00 AM\n"
			"Subject: Factura Orange - HOTEL LIFE SRL\n"
			"To: <hotel.life.srl@gmail.com>\n",
		)
		self.assertEqual(parsed["original_sender_name"], "Orange")
		self.assertEqual(parsed["original_sender_email"], "factura.electronica@orange.md")
		self.assertEqual(parsed["original_subject"], "Factura Orange - HOTEL LIFE SRL")

	def test_archive_files_are_unpacked_onto_the_inbox_email(self):
		doc = self._make_inbound(run=False)
		communication = frappe.get_doc(
			{"doctype": "Communication", "subject": "Invoice", "communication_medium": "Email"}
		).insert(ignore_permissions=True)
		nested = io.BytesIO()
		with zipfile.ZipFile(nested, "w") as inner:
			inner.writestr("nested/factura.xml", "<factura/>")
		outer = io.BytesIO()
		with zipfile.ZipFile(outer, "w") as archive:
			archive.writestr("note.txt", "hello")
			archive.writestr("inner.zip", nested.getvalue())
		for file_name, content in (("plain.txt", b"loose"), ("documents.zip", outer.getvalue())):
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": file_name,
					"content": content,
					"attached_to_doctype": "Communication",
					"attached_to_name": communication.name,
					"is_private": 1,
				}
			).save(ignore_permissions=True)

		collect_mail_files(doc.name, communication.name)
		attached = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Supplier Inbox Email", "attached_to_name": doc.name},
			fields=["file_name", "file_url"],
		)
		names = {row.file_name for row in attached}
		self.assertEqual(names, {"plain.txt", "note.txt", "factura.xml"})
		source_url = frappe.db.get_value(
			"File",
			{"attached_to_doctype": "Communication", "attached_to_name": communication.name, "file_name": "plain.txt"},
			"file_url",
		)
		linked_url = next(row.file_url for row in attached if row.file_name == "plain.txt")
		self.assertEqual(linked_url, source_url)

	def test_two_attachments_one_document(self):
		doc = self._make_inbound()
		for filename in ("a.txt", "b.txt"):
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": filename,
					"content": filename,
					"attached_to_doctype": "Supplier Inbox Email",
					"attached_to_name": doc.name,
					"is_private": 1,
				}
			)
			file.save(ignore_permissions=True)
		files = frappe.get_all("File", filters={"attached_to_doctype": "Supplier Inbox Email", "attached_to_name": doc.name})
		self.assertEqual(len(files), 2)
		self.assertTrue(frappe.db.exists("Supplier Inbox Email", doc.name))

	def test_failed_handler_does_not_block_the_next(self):
		doc = self._make_inbound(run=False)
		queue_handlers(doc.name)
		doc.reload()
		by_handler = {row.handler: row.status for row in doc.handlers}
		self.assertEqual(by_handler[self._paths[0]], "Failed")
		self.assertEqual(by_handler[self._paths[1]], "Processed")
		self.assertEqual(by_handler[self._paths[2]], "Skipped")
		processed = next(row for row in doc.handlers if row.handler == self._paths[1])
		self.assertEqual(processed.reference_doctype, "ToDo")
		self.assertTrue(processed.reference_name)

	def test_second_pass_skips_finished_handlers(self):
		doc = self._make_inbound(run=False)
		queue_handlers(doc.name)
		processed_calls = len(frappe.flags.inbox_processed)
		skipped_calls = frappe.flags.inbox_skipped
		failed_calls = frappe.flags.inbox_failed
		queue_handlers(doc.name)
		self.assertEqual(len(frappe.flags.inbox_processed), processed_calls)
		self.assertEqual(frappe.flags.inbox_skipped, skipped_calls)
		self.assertEqual(frappe.flags.inbox_failed, failed_calls + 1)
		self.assertTrue(frappe.db.exists("Supplier Inbox Email", doc.name))

	def _make_inbound(self, run=True):
		if not run:
			self._handlers.stop()
		doc = frappe.get_doc(
			{
				"doctype": "Supplier Inbox Email",
			}
		).insert(ignore_permissions=True)
		if not run:
			self._handlers.start()
		return doc
