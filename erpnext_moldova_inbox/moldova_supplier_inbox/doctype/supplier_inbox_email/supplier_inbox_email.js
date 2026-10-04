frappe.ui.form.on("Supplier Inbox Email", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Retry Handlers"), () => {
			frm.call("retry_handlers").then((r) => {
				if (r.message) {
					frappe.show_alert({message: r.message, indicator: "green"});
				}
				frm.reload_doc();
			});
		});
	},
});
