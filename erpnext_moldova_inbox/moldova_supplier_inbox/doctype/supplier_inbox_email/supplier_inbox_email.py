# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_moldova_inbox.moldova_supplier_inbox.dispatch import queue_handlers


class SupplierInboxEmail(Document):
	def after_insert(self):
		queue_handlers(self.name)

	@frappe.whitelist()
	def retry_handlers(self):
		queue_handlers(self.name)
		return _("Failed handlers and handlers with no row were queued again.")
