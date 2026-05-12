import frappe


LABORATORY_MODULE = "Bitumen Laboratory"
LABORATORY_ROLES = ("Laboratory Technician", "Laboratory Supervisor")
LABORATORY_TRANSACTION_DOCTYPES = ("Laboratory Truck Test",)
LABORATORY_SETTINGS_DOCTYPES = ("Laboratory Settings",)
LABORATORY_SETTINGS_DEFAULTS = {
	"minimum_flash_point": 0,
	"maximum_flash_point": 0,
	"minimum_viscosity": 0,
	"maximum_viscosity": 0,
	"auto_update_weight_bridge_ticket": 1,
}


def before_install():
	if "weight_bridge" not in frappe.get_installed_apps():
		frappe.throw("Bitumen Laboratory requires the Weight Bridge app to be installed first.")


def after_install():
	ensure_laboratory_module()
	ensure_laboratory_settings()
	ensure_roles_and_permissions()
	ensure_weight_bridge_ticket_lab_fields()
	ensure_laboratory_workspace()


def before_tests():
	ensure_laboratory_module()
	ensure_laboratory_settings()
	ensure_roles_and_permissions()
	ensure_weight_bridge_ticket_lab_fields()
	ensure_laboratory_workspace()


def ensure_laboratory_module():
	frappe.local.module_app[frappe.scrub(LABORATORY_MODULE)] = "bitumen_laboratory"
	if frappe.db.exists("Module Def", LABORATORY_MODULE):
		return

	frappe.get_doc(
		{
			"doctype": "Module Def",
			"module_name": LABORATORY_MODULE,
			"app_name": "bitumen_laboratory",
		}
	).insert(ignore_permissions=True)
	frappe.clear_cache()


def ensure_laboratory_settings():
	if not frappe.db.exists("DocType", "Laboratory Settings"):
		return

	settings = frappe.get_single("Laboratory Settings")
	changed = False
	for fieldname, value in LABORATORY_SETTINGS_DEFAULTS.items():
		if settings.get(fieldname) in (None, ""):
			settings.set(fieldname, value)
			changed = True

	if changed:
		settings.save(ignore_permissions=True)

	frappe.clear_cache(doctype="Laboratory Settings")


def ensure_roles_and_permissions():
	for role in LABORATORY_ROLES:
		ensure_role(role)

	for doctype in LABORATORY_TRANSACTION_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue

		ensure_custom_permission(
			doctype,
			"Laboratory Technician",
			{
				"read": 1,
				"write": 1,
				"create": 1,
				"email": 1,
				"print": 1,
				"report": 1,
				"share": 1,
				"submit": 1,
			},
		)
		ensure_custom_permission(
			doctype,
			"Laboratory Supervisor",
			{
				"read": 1,
				"write": 1,
				"create": 1,
				"delete": 1,
				"email": 1,
				"print": 1,
				"report": 1,
				"share": 1,
				"submit": 1,
				"cancel": 1,
				"amend": 1,
			},
		)
		frappe.clear_cache(doctype=doctype)

	for doctype in LABORATORY_SETTINGS_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue

		ensure_custom_permission(doctype, "Laboratory Technician", {"read": 1})
		ensure_custom_permission(
			doctype,
			"Laboratory Supervisor",
			{"read": 1, "write": 1, "email": 1, "print": 1, "report": 1, "share": 1},
		)
		frappe.clear_cache(doctype=doctype)


def ensure_weight_bridge_ticket_lab_fields():
	if not frappe.db.exists("DocType", "Weight Bridge Ticket"):
		return

	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Weight Bridge Ticket": [
				{
					"fieldname": "laboratory_section",
					"fieldtype": "Section Break",
					"insert_after": "ticket_status",
					"label": "Laboratory",
					"collapsible": 1,
				},
				{
					"fieldname": "laboratory_status",
					"fieldtype": "Select",
					"insert_after": "laboratory_section",
					"in_standard_filter": 1,
					"label": "Laboratory Status",
					"options": "\nPending Laboratory Test\nPassed\nRejected",
					"read_only": 1,
				},
				{
					"fieldname": "laboratory_test",
					"fieldtype": "Link",
					"insert_after": "laboratory_status",
					"label": "Laboratory Test",
					"options": "Laboratory Truck Test",
					"read_only": 1,
				},
				{
					"fieldname": "laboratory_pool",
					"fieldtype": "Link",
					"insert_after": "laboratory_test",
					"label": "Laboratory Pool",
					"options": "Warehouse",
					"read_only": 1,
				},
			],
		},
		update=True,
	)
	ensure_ticket_status_accepts_rejected()
	frappe.clear_cache(doctype="Weight Bridge Ticket")


def ensure_ticket_status_accepts_rejected():
	field = frappe.get_meta("Weight Bridge Ticket").get_field("ticket_status")
	if not field:
		return

	options = [option for option in (field.options or "").split("\n") if option]
	if "Rejected" in options:
		return

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"Weight Bridge Ticket",
		"ticket_status",
		"options",
		"\n".join(options + ["Rejected"]),
		"Text",
	)


def ensure_laboratory_workspace():
	if not frappe.db.exists("Workspace", "Laboratory"):
		return

	quality_sequence = frappe.db.get_value("Workspace", "Quality", "sequence_id") or 9
	frappe.db.set_value(
		"Workspace",
		"Laboratory",
		{
			"icon": "quality",
			"public": 1,
			"is_hidden": 0,
			"sequence_id": float(quality_sequence) + 0.1,
		},
		update_modified=False,
	)
	frappe.clear_cache()


def ensure_role(role_name):
	if frappe.db.exists("Role", role_name):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
		}
	).insert(ignore_permissions=True)


def ensure_custom_permission(doctype, role, flags):
	from frappe.permissions import setup_custom_perms

	setup_custom_perms(doctype)
	name = frappe.db.get_value(
		"Custom DocPerm",
		{
			"parent": doctype,
			"role": role,
			"permlevel": 0,
			"if_owner": 0,
		},
	)

	if name:
		docperm = frappe.get_doc("Custom DocPerm", name)
	else:
		docperm = frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
				"if_owner": 0,
			}
		)

	for field in (
		"read",
		"write",
		"create",
		"delete",
		"submit",
		"cancel",
		"amend",
		"report",
		"export",
		"import",
		"share",
		"print",
		"email",
	):
		docperm.set(field, flags.get(field, 0))

	if docperm.is_new():
		docperm.insert(ignore_permissions=True)
	else:
		docperm.save(ignore_permissions=True)
