const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SCRIPT_PATH = path.join(
	__dirname,
	"../bitumen_laboratory/bitumen_laboratory/doctype/laboratory_truck_test/laboratory_truck_test.js"
);

function loadScript(ticketResponse = {}, settingsResponse = {}) {
	const script = fs.readFileSync(SCRIPT_PATH, "utf8");
	const context = {
		calls: [],
		alerts: [],
		dbCalls: [],
		queries: {},
		buttons: [],
		route: null,
		module: { exports: {} },
		__(text) {
			return text;
		},
		frappe: {
			call(options) {
				context.calls.push(options);
				options.callback({ message: ticketResponse });
			},
			set_route(...args) {
				context.route = args;
			},
			show_alert(alert) {
				context.alerts.push(alert);
			},
			db: {
				get_doc(doctype, name) {
					context.dbCalls.push({ doctype, name });
					return Promise.resolve(settingsResponse);
				},
			},
			ui: {
				form: {
					on(_doctype, handlers) {
						context.handlers = handlers;
					},
				},
			},
		},
	};
	vm.runInNewContext(script, context);
	return context;
}

function createFrm(doc = {}) {
	return {
		doc: {
			doctype: "Laboratory Truck Test",
			plate_number: "LAB-TEST-001",
			...doc,
		},
		dashboard: {
			clear_headline_count: 0,
			headline: null,
			clear_headline() {
				this.clear_headline_count += 1;
			},
			set_headline_alert(value) {
				this.headline = value;
			},
		},
		add_custom_button(label, handler) {
			this.buttons.push({ label, handler });
		},
		buttons: [],
		set_query(fieldname, handler) {
			this.queries[fieldname] = handler;
		},
		set_value(fieldname, value) {
			this.doc[fieldname] = value;
			return Promise.resolve();
		},
		set_df_property(fieldname, property, value) {
			this.dfProperties = this.dfProperties || {};
			this.dfProperties[fieldname] = this.dfProperties[fieldname] || {};
			this.dfProperties[fieldname][property] = value;
		},
		toggle_display(fieldname, visible) {
			this.displayed = this.displayed || {};
			this.displayed[fieldname] = visible;
		},
		toggle_reqd(fieldname, required) {
			this.required = this.required || {};
			this.required[fieldname] = required;
		},
		queries: {},
	};
}

test("plate number lookup populates linked weight bridge ticket details", () => {
	const context = loadScript({
		name: "WB-990201-01",
		driver: "+9647700000099",
		driver_name: "Laboratory Test Driver",
		cargo_item: "VR",
		first_weight: 45000,
		first_weight_datetime: "2099-02-01 10:00:00",
	});
	const frm = createFrm();

	context.handlers.plate_number(frm);

	assert.equal(context.calls.length, 1);
	assert.equal(context.calls[0].args.plate_number, "LAB-TEST-001");
	assert.equal(frm.doc.weight_bridge_ticket, "WB-990201-01");
	assert.equal(frm.doc.driver_name, "Laboratory Test Driver");
	assert.equal(frm.doc.cargo_item, "VR");
	assert.equal(frm.doc.weight, 45000);
	assert.equal(frm.doc.weight_datetime, "2099-02-01 10:00:00");
});

test("missing weight bridge ticket shows an operator alert", () => {
	const context = loadScript({});
	const frm = createFrm();

	context.handlers.plate_number(frm);

	assert.equal(context.alerts.length, 1);
	assert.equal(context.alerts[0].indicator, "orange");
	assert.equal(frm.doc.weight_bridge_ticket, undefined);
});

test("setup scopes pool and weight bridge ticket queries", () => {
	const context = loadScript();
	const frm = createFrm({ plate_number: "ABC-123" });

	context.handlers.setup(frm);

	assert.equal(JSON.stringify(frm.queries.pool()), JSON.stringify({
		filters: {
			is_group: 0,
			disabled: 0,
		},
	}));
	assert.equal(JSON.stringify(frm.queries.weight_bridge_ticket()), JSON.stringify({
		filters: {
			docstatus: ["!=", 2],
			plate_number: "ABC-123",
		},
	}));
});

test("hybrid refresh without configured criteria keeps status editable and does not require pool", async () => {
	const context = loadScript({}, {
		evaluation_mode: "Hybrid",
		minimum_flash_point: 0,
		maximum_flash_point: 0,
		minimum_viscosity: 0,
		maximum_viscosity: 0,
		allow_failed_test_exception: 0,
	});
	const frm = createFrm({
		laboratory_status: "Draft",
		weight_bridge_ticket: "WB-990201-01",
	});

	await context.handlers.refresh(frm);
	frm.buttons[0].handler();

	assert.equal(context.dbCalls[0].doctype, "Laboratory Settings");
	assert.equal(frm.dfProperties.laboratory_status.read_only, 0);
	assert.equal(frm.required.pool, false);
	assert.equal(frm.displayed.accept_failed_result, false);
	assert.equal(frm.dashboard.clear_headline_count > 0, true);
	assert.deepEqual(context.route, ["Form", "Weight Bridge Ticket", "WB-990201-01"]);
});

test("refresh displays passed status and requires pool", async () => {
	const context = loadScript({}, {
		evaluation_mode: "Hybrid",
		minimum_flash_point: 100,
		maximum_flash_point: 300,
		minimum_viscosity: 10,
		maximum_viscosity: 80,
	});
	const frm = createFrm({
		laboratory_status: "Passed",
		weight_bridge_ticket: "WB-990201-01",
	});

	await context.handlers.refresh(frm);
	frm.buttons[0].handler();

	assert.equal(frm.dfProperties.laboratory_status.read_only, 1);
	assert.equal(frm.required.pool, true);
	assert.match(frm.dashboard.headline, /Passed/);
	assert.deepEqual(context.route, ["Form", "Weight Bridge Ticket", "WB-990201-01"]);
});

test("accepted with exception requires pool and exception reason in the form", async () => {
	const context = loadScript({}, {
		evaluation_mode: "Automatic",
		minimum_flash_point: 100,
		maximum_flash_point: 300,
		minimum_viscosity: 10,
		maximum_viscosity: 80,
		allow_failed_test_exception: 1,
	});
	const frm = createFrm({
		laboratory_status: "Accepted With Exception",
		accept_failed_result: 1,
	});

	await context.handlers.refresh(frm);

	assert.equal(frm.required.pool, true);
	assert.equal(frm.required.exception_reason, true);
	assert.equal(frm.displayed.accept_failed_result, true);
	assert.equal(frm.displayed.exception_reason, true);
	assert.match(frm.dashboard.headline, /Accepted With Exception/);
	assert.match(frm.dashboard.headline, /indicator orange/);
});

test("checking management exception sets accepted with exception status", () => {
	const context = loadScript();
	const frm = createFrm({
		laboratory_status: "Rejected",
		accept_failed_result: 1,
	});

	context.handlers.accept_failed_result(frm);

	assert.equal(frm.doc.laboratory_status, "Accepted With Exception");
	assert.equal(frm.required.pool, true);
});
