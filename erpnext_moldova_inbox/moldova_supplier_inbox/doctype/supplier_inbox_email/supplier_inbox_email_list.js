frappe.listview_settings["Supplier Inbox Email"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Create Missing Emails"), () => {
			frappe.call({
				method: "run_doc_method",
				args: {
					dt: "Supplier Inbox Settings",
					dn: "Supplier Inbox Settings",
					method: "recreate_missing_emails",
				},
				callback(r) {
					if (r.message && r.message.message) {
						frappe.show_alert({message: r.message.message, indicator: "green"});
					}
					listview.refresh();
				},
			});
		});
	},
};
