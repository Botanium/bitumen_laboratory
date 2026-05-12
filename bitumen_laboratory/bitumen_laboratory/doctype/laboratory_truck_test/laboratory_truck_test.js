frappe.ui.form.on("Laboratory Truck Test", {
	setup(frm) {
		frm.set_query("pool", () => ({
			filters: {
				is_group: 0,
				disabled: 0,
			},
		}));
		frm.set_query("weight_bridge_ticket", () => {
			const filters = { docstatus: ["!=", 2] };
			if (frm.doc.plate_number) {
				filters.plate_number = frm.doc.plate_number;
			}
			return { filters };
		});
	},

	refresh(frm) {
		update_status_indicator(frm);
		toggle_pool_requirement(frm);
		if (frm.doc.weight_bridge_ticket) {
			frm.add_custom_button(__("Open Weight Bridge Ticket"), () => {
				frappe.set_route("Form", "Weight Bridge Ticket", frm.doc.weight_bridge_ticket);
			});
		}
	},

	plate_number(frm) {
		fetch_weight_bridge_ticket(frm);
	},

	flash_point(frm) {
		update_status_indicator(frm);
		toggle_pool_requirement(frm);
	},

	viscosity(frm) {
		update_status_indicator(frm);
		toggle_pool_requirement(frm);
	},

	laboratory_status(frm) {
		update_status_indicator(frm);
		toggle_pool_requirement(frm);
	},
});

function fetch_weight_bridge_ticket(frm) {
	if (!frm.doc.plate_number) {
		return;
	}

	frappe.call({
		method:
			"bitumen_laboratory.bitumen_laboratory.doctype.laboratory_truck_test.laboratory_truck_test.get_weight_bridge_ticket_for_plate",
		args: {
			plate_number: frm.doc.plate_number,
		},
		callback(response) {
			const ticket = response.message || {};
			if (!ticket.name) {
				frappe.show_alert({
					message: __("No active Weight Bridge Ticket was found for this plate number."),
					indicator: "orange",
				});
				return;
			}

			frm.set_value("weight_bridge_ticket", ticket.name);
			frm.set_value("driver", ticket.driver);
			frm.set_value("driver_name", ticket.driver_name);
			frm.set_value("cargo_item", ticket.cargo_item);
			frm.set_value("weight", ticket.first_weight);
			frm.set_value("weight_datetime", ticket.first_weight_datetime);
		},
	});
}

function update_status_indicator(frm) {
	const status = frm.doc.laboratory_status;
	if (!status || status === "Draft") {
		frm.dashboard.clear_headline();
		return;
	}

	const indicator = status === "Passed" ? "green" : "red";
	frm.dashboard.set_headline_alert(
		`<div class="indicator ${indicator}">${__("Laboratory Test")}: ${__(status)}</div>`
	);
}

function toggle_pool_requirement(frm) {
	frm.toggle_reqd("pool", frm.doc.laboratory_status === "Passed");
}

if (typeof module !== "undefined") {
	module.exports = {
		fetch_weight_bridge_ticket,
		toggle_pool_requirement,
		update_status_indicator,
	};
}

