const PASS_STATUS = "Passed";
const PENDING_STATUS = "Draft";
const EXCEPTION_STATUS = "Accepted With Exception";
const AUTOMATIC_MODE = "Automatic";
const HYBRID_MODE = "Hybrid";
const POOL_REQUIRED_STATUSES = [PASS_STATUS, EXCEPTION_STATUS];

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
		const settings_loading = load_laboratory_settings(frm);
		update_decision_controls(frm);
		if (frm.doc.weight_bridge_ticket) {
			frm.add_custom_button(__("Open Weight Bridge Ticket"), () => {
				frappe.set_route("Form", "Weight Bridge Ticket", frm.doc.weight_bridge_ticket);
			});
		}
		return settings_loading;
	},

	plate_number(frm) {
		fetch_weight_bridge_ticket(frm);
	},

	flash_point(frm) {
		update_decision_controls(frm);
	},

	viscosity(frm) {
		update_decision_controls(frm);
	},

	laboratory_status(frm) {
		if (frm.doc.laboratory_status === EXCEPTION_STATUS && !frm.doc.accept_failed_result) {
			frm.set_value("accept_failed_result", 1);
		}
		update_decision_controls(frm);
	},

	accept_failed_result(frm) {
		if (frm.doc.accept_failed_result && frm.doc.laboratory_status !== EXCEPTION_STATUS) {
			frm.set_value("laboratory_status", EXCEPTION_STATUS);
		}
		update_decision_controls(frm);
	},
});

function load_laboratory_settings(frm) {
	if (!frappe.db || !frappe.db.get_doc) {
		apply_laboratory_settings(frm, {});
		return Promise.resolve({});
	}

	return frappe.db
		.get_doc("Laboratory Settings", "Laboratory Settings")
		.then((settings) => {
			apply_laboratory_settings(frm, settings || {});
			return settings || {};
		})
		.catch(() => {
			apply_laboratory_settings(frm, {});
			return {};
		});
}

function apply_laboratory_settings(frm, settings) {
	frm._laboratory_settings = settings || {};
	update_decision_controls(frm);
}

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
	if (!status || status === PENDING_STATUS) {
		frm.dashboard.clear_headline();
		return;
	}

	const indicator = status === PASS_STATUS ? "green" : status === EXCEPTION_STATUS ? "orange" : "red";
	frm.dashboard.set_headline_alert(
		`<div class="indicator ${indicator}">${__("Laboratory Test")}: ${__(status)}</div>`
	);
}

function update_decision_controls(frm) {
	const settings = frm._laboratory_settings || {};
	const evaluation_mode = settings.evaluation_mode || HYBRID_MODE;
	const has_criteria = has_configured_criteria(settings);
	const is_automatic = evaluation_mode === AUTOMATIC_MODE || (evaluation_mode === HYBRID_MODE && has_criteria);
	const allows_exception = Boolean(Number(settings.allow_failed_test_exception || 0));
	const uses_exception = Boolean(frm.doc.accept_failed_result || frm.doc.laboratory_status === EXCEPTION_STATUS);

	if (frm.set_df_property) {
		frm.set_df_property("laboratory_status", "read_only", is_automatic ? 1 : 0);
	}
	if (frm.toggle_display) {
		frm.toggle_display("accept_failed_result", allows_exception);
		frm.toggle_display("exception_reason", allows_exception && uses_exception);
	}
	if (frm.toggle_reqd) {
		frm.toggle_reqd("exception_reason", allows_exception && uses_exception);
	}

	toggle_pool_requirement(frm);
	update_status_indicator(frm);
}

function toggle_pool_requirement(frm) {
	frm.toggle_reqd("pool", POOL_REQUIRED_STATUSES.includes(frm.doc.laboratory_status));
}

function has_configured_criteria(settings) {
	return (
		has_configured_limit(settings.minimum_flash_point, settings.maximum_flash_point) &&
		has_configured_limit(settings.minimum_viscosity, settings.maximum_viscosity)
	);
}

function has_configured_limit(minimum, maximum) {
	return Boolean(Number(minimum || 0) || Number(maximum || 0));
}

if (typeof module !== "undefined") {
	module.exports = {
		apply_laboratory_settings,
		fetch_weight_bridge_ticket,
		has_configured_criteria,
		load_laboratory_settings,
		toggle_pool_requirement,
		update_decision_controls,
		update_status_indicator,
	};
}
