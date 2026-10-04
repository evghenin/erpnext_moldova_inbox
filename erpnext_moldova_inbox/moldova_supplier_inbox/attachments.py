# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import io
import os
import zipfile

import frappe

ARCHIVE_EXTENSIONS = {".zip"}
MAX_DEPTH = 5
MAX_FILES = 100
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def collect_mail_files(supplier_inbox_email, communication):
	"""Copy mail attachments onto Supplier Inbox Email, unpacking archives."""
	if frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Supplier Inbox Email", "attached_to_name": supplier_inbox_email},
		limit=1,
	):
		return

	sources = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Communication", "attached_to_name": communication},
		fields=["name", "file_name"],
	)
	state = {"count": 0, "bytes": 0}
	for source in sources:
		file_doc = frappe.get_doc("File", source.name)
		file_name = source.file_name or file_doc.file_name
		if _is_archive(file_name):
			content = file_doc.get_content()
			if isinstance(content, str):
				content = content.encode()
			_unpack(supplier_inbox_email, file_name, content or b"", state, depth=0)
			continue
		if state["count"] >= MAX_FILES or not _safe_name(file_name):
			continue
		state["count"] += 1
		file_doc.create_attachment_copy(
			"Supplier Inbox Email", supplier_inbox_email, ignore_permissions=True
		)


def _store(supplier_inbox_email, file_name, content, state, depth):
	name = _safe_name(file_name)
	if not name:
		return
	if _is_archive(name):
		_unpack(supplier_inbox_email, name, content, state, depth)
		return
	if state["count"] >= MAX_FILES:
		return
	state["count"] += 1
	state["bytes"] += len(content)
	_attach(supplier_inbox_email, name, content)


def _unpack(supplier_inbox_email, file_name, content, state, depth):
	if depth >= MAX_DEPTH:
		frappe.log_error(title="Supplier Inbox archive skipped", message=f"{file_name}: nested too deep")
		return
	try:
		archive = zipfile.ZipFile(io.BytesIO(content))
	except zipfile.BadZipFile:
		frappe.log_error(title="Supplier Inbox archive skipped", message=f"{file_name}: not a valid zip")
		return

	with archive:
		for info in archive.infolist():
			if info.is_dir() or state["count"] >= MAX_FILES or state["bytes"] >= MAX_UNCOMPRESSED_BYTES:
				continue
			inner_name = _safe_name(info.filename)
			if not inner_name:
				continue
			if info.flag_bits & 0x1:
				frappe.log_error(
					title="Supplier Inbox archive skipped",
					message=f"{file_name}: {inner_name} is encrypted. Archive passwords are not configured yet.",
				)
				continue
			try:
				payload = archive.read(info)
			except RuntimeError:
				frappe.log_error(
					title="Supplier Inbox archive skipped",
					message=f"{file_name}: {inner_name} could not be read",
				)
				continue
			if state["bytes"] + len(payload) > MAX_UNCOMPRESSED_BYTES:
				frappe.log_error(title="Supplier Inbox archive skipped", message=f"{file_name}: uncompressed size limit")
				return
			_store(supplier_inbox_email, inner_name, payload, state, depth + 1)


def _attach(supplier_inbox_email, file_name, content):
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"content": content,
			"attached_to_doctype": "Supplier Inbox Email",
			"attached_to_name": supplier_inbox_email,
			"is_private": 1,
		}
	)
	file_doc.save(ignore_permissions=True)


def _is_archive(file_name):
	return os.path.splitext(file_name)[1].lower() in ARCHIVE_EXTENSIONS


def _safe_name(file_name):
	name = os.path.basename((file_name or "").replace("\\", "/")).strip()
	if not name or name in {".", ".."} or name.startswith("."):
		return ""
	return name
