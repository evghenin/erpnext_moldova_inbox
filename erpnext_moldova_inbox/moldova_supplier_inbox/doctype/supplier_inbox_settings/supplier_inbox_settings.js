frappe.ui.form.on("Supplier Inbox Settings", {
	configure_email_account(frm) {
		frm.call("configure_email_account").then((r) => {
			if (r.message && r.message.message) {
				frappe.show_alert({message: r.message.message, indicator: r.message.changed ? "green" : "blue"});
			}
		});
	},
});
