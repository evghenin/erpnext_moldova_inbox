# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import re
from email.utils import parseaddr

import frappe

_FORWARD_MARK = re.compile(r"-{5,}\s*Forwarded message\s*-{5,}", re.IGNORECASE)
_FWD_PREFIX = re.compile(r"^(?:\s*(?:fw|fwd|re)\s*:\s*)+", re.IGNORECASE)


def fill_existing():
	"""Set original sender and subject on Supplier Inbox Email rows already linked to a Communication."""
	for row in frappe.get_all("Supplier Inbox Email", filters={"communication": ["is", "set"]}, fields=["name", "communication"]):
		communication = frappe.db.get_value(
			"Communication",
			row.communication,
			["subject", "sender", "sender_full_name", "text_content"],
			as_dict=True,
		)
		if not communication:
			continue
		frappe.db.set_value(
			"Supplier Inbox Email",
			row.name,
			original_message(
				communication.subject,
				communication.sender,
				communication.sender_full_name,
				communication.text_content,
			),
			update_modified=False,
		)
	frappe.db.sql("delete from `__UserSettings` where doctype=%s", "Supplier Inbox Email")


def original_message(subject, sender, sender_name, text):
	"""Sender and subject of the supplier mail, past a mailbox forward when present."""
	headers = _forwarded_headers(text or "")
	if headers and headers.get("from"):
		name, email = parseaddr(headers["from"])
		return {
			"original_sender_name": name,
			"original_sender_email": email,
			"original_subject": (headers.get("subject") or _strip_forward_prefix(subject))[:140],
		}

	name, email = parseaddr(sender or "")
	return {
		"original_sender_name": sender_name or name,
		"original_sender_email": email or (sender or ""),
		"original_subject": _strip_forward_prefix(subject)[:140],
	}


def _forwarded_headers(text):
	match = _FORWARD_MARK.search(text)
	if not match:
		return None
	headers = {}
	for line in text[match.end() :].splitlines():
		stripped = line.strip()
		if not stripped:
			if headers:
				break
			continue
		if ":" not in stripped:
			break
		key, value = stripped.split(":", 1)
		headers[key.strip().lower()] = value.strip()
	return headers


def _strip_forward_prefix(subject):
	return _FWD_PREFIX.sub("", subject or "").strip()
