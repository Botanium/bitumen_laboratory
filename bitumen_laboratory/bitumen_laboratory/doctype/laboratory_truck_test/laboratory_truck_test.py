import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, cstr, flt, now_datetime


PASS_STATUS = "Passed"
REJECT_STATUS = "Rejected"
PENDING_STATUS = "Draft"
EXCEPTION_STATUS = "Accepted With Exception"
HYBRID_MODE = "Hybrid"
AUTOMATIC_MODE = "Automatic"
VALID_STATUSES = (PENDING_STATUS, PASS_STATUS, REJECT_STATUS, EXCEPTION_STATUS)
POOL_REQUIRED_STATUSES = (PASS_STATUS, EXCEPTION_STATUS)
TEST_LIMIT_FIELDS = (
	("flash_point", "minimum_flash_point", "maximum_flash_point"),
	("viscosity", "minimum_viscosity", "maximum_viscosity"),
)


class LaboratoryTruckTest(Document):
	def autoname(self):
		self.name = make_autoname("LAB-.YY.MM.DD.-.##")

	def before_validate(self):
		if not self.test_datetime:
			self.test_datetime = now_datetime()
		if not self.operator or self.operator == "user":
			self.operator = frappe.session.user
		self._fetch_weight_bridge_ticket_details()
		self._set_laboratory_status()

	def validate(self):
		self._validate_weight_bridge_ticket()
		self._validate_test_values()
		self._set_laboratory_status()
		self._validate_laboratory_status()
		self._validate_exception_acceptance()
		self._validate_pool()

	def before_submit(self):
		self._set_laboratory_status()
		self._validate_laboratory_status()
		self._validate_exception_acceptance()
		self._validate_pool()
		self._validate_submission_status()

	def on_submit(self):
		if cint(self._settings().auto_update_weight_bridge_ticket):
			self._update_weight_bridge_ticket()

	def on_cancel(self):
		if self.weight_bridge_ticket:
			self._clear_weight_bridge_ticket_lab_status()

	def _fetch_weight_bridge_ticket_details(self):
		ticket_name = self.weight_bridge_ticket
		if not ticket_name and self.plate_number:
			details = get_weight_bridge_ticket_for_plate(self.plate_number)
			ticket_name = details.get("name") if details else None

		if not ticket_name:
			return

		ticket = _get_weight_bridge_ticket_details(ticket_name)
		if not ticket:
			frappe.throw(_("Weight Bridge Ticket {0} does not exist.").format(frappe.bold(ticket_name)))

		self.weight_bridge_ticket = ticket.name
		self.plate_number = ticket.plate_number
		self.driver = ticket.driver
		self.driver_name = ticket.driver_name
		self.cargo_item = ticket.cargo_item
		self.weight = ticket.first_weight
		self.weight_datetime = ticket.first_weight_datetime

	def _validate_weight_bridge_ticket(self):
		if not self.weight_bridge_ticket:
			frappe.throw(_("A Weight Bridge Ticket is required for the laboratory test."))

		ticket = _get_weight_bridge_ticket_details(self.weight_bridge_ticket)
		if not ticket:
			frappe.throw(_("Weight Bridge Ticket {0} does not exist.").format(frappe.bold(self.weight_bridge_ticket)))
		if ticket.docstatus == 2:
			frappe.throw(_("Weight Bridge Ticket {0} is cancelled.").format(frappe.bold(self.weight_bridge_ticket)))
		if self.plate_number and ticket.plate_number != self.plate_number:
			frappe.throw(_("Plate Number must match the linked Weight Bridge Ticket."))

	def _validate_pool(self):
		if self.laboratory_status not in POOL_REQUIRED_STATUSES:
			return

		if not self.pool:
			frappe.throw(_("Pool is required when the laboratory test is accepted for a pool."))
		if not frappe.db.exists("Warehouse", self.pool):
			frappe.throw(_("Pool Warehouse {0} does not exist.").format(frappe.bold(self.pool)))
		if frappe.db.get_value("Warehouse", self.pool, "is_group"):
			frappe.throw(_("Pool must be a non-group Warehouse."))
		if frappe.db.get_value("Warehouse", self.pool, "disabled"):
			frappe.throw(_("Pool Warehouse {0} is disabled.").format(frappe.bold(self.pool)))

	def _validate_test_values(self):
		for fieldname in ("flash_point", "viscosity"):
			value = flt(self.get(fieldname))
			if value <= 0:
				frappe.throw(_("{0} must be greater than zero.").format(self.meta.get_label(fieldname)))

	def _set_laboratory_status(self):
		if not flt(self.flash_point) or not flt(self.viscosity):
			self.laboratory_status = PENDING_STATUS
			return

		settings = self._settings()
		evaluation_mode = self._evaluation_mode(settings)

		if evaluation_mode == AUTOMATIC_MODE:
			self._set_automatic_laboratory_status(settings)
			return

		if evaluation_mode == HYBRID_MODE and self._has_configured_criteria(settings):
			self._set_automatic_laboratory_status(settings)
			return

		self._normalize_manual_laboratory_status()

	def _set_automatic_laboratory_status(self, settings):
		if not self._has_configured_criteria(settings):
			self.laboratory_status = PENDING_STATUS
			return

		if self._test_values_fail_limits(settings):
			self.laboratory_status = EXCEPTION_STATUS if cint(self.accept_failed_result) else REJECT_STATUS
			if self.laboratory_status == EXCEPTION_STATUS:
				self.accept_failed_result = 1
			return

		self.laboratory_status = PASS_STATUS
		self.accept_failed_result = 0

	def _normalize_manual_laboratory_status(self):
		if cint(self.accept_failed_result):
			self.laboratory_status = EXCEPTION_STATUS
		elif not self.laboratory_status:
			self.laboratory_status = PENDING_STATUS

		if self.laboratory_status == EXCEPTION_STATUS:
			self.accept_failed_result = 1

	def _validate_laboratory_status(self):
		if self.laboratory_status not in VALID_STATUSES:
			frappe.throw(_("Laboratory Status must be one of: {0}.").format(", ".join(VALID_STATUSES)))

	def _validate_exception_acceptance(self):
		if self.laboratory_status != EXCEPTION_STATUS:
			return

		settings = self._settings()
		if not cint(settings.allow_failed_test_exception):
			frappe.throw(_("Accepted With Exception is disabled in Laboratory Settings."))
		if not cstr(self.exception_reason).strip():
			frappe.throw(_("Exception Reason is required when failed test results are accepted."))

	def _validate_submission_status(self):
		if self.laboratory_status != PENDING_STATUS:
			return

		if self._evaluation_mode(self._settings()) == AUTOMATIC_MODE:
			frappe.throw(_("Configure passing criteria for Flash Point and Viscosity before submitting an automatic laboratory test."))

		frappe.throw(_("Select a final Laboratory Status before submitting."))

	def _has_configured_criteria(self, settings):
		for _test_field, minimum_field, maximum_field in TEST_LIMIT_FIELDS:
			if not self._has_configured_limit(settings.get(minimum_field), settings.get(maximum_field)):
				return False
		return True

	def _has_configured_limit(self, minimum, maximum):
		return bool(flt(minimum) or flt(maximum))

	def _test_values_fail_limits(self, settings):
		for test_field, minimum_field, maximum_field in TEST_LIMIT_FIELDS:
			if self._value_outside_limits(
				flt(self.get(test_field)),
				settings.get(minimum_field),
				settings.get(maximum_field),
			):
				return True
		return False

	def _value_outside_limits(self, value, minimum, maximum):
		minimum = flt(minimum)
		maximum = flt(maximum)
		if minimum and value < minimum:
			return True
		if maximum and value > maximum:
			return True
		return False

	def _update_weight_bridge_ticket(self):
		if not self.weight_bridge_ticket:
			return

		values = {
			"laboratory_status": self.laboratory_status,
			"laboratory_test": self.name,
			"laboratory_pool": self.pool if self.laboratory_status in POOL_REQUIRED_STATUSES else None,
		}
		if self.laboratory_status == REJECT_STATUS and _ticket_status_accepts("Rejected"):
			values["ticket_status"] = "Rejected"
		elif self.laboratory_status in POOL_REQUIRED_STATUSES:
			ticket_status = frappe.db.get_value("Weight Bridge Ticket", self.weight_bridge_ticket, "ticket_status")
			if ticket_status in ("Pending Laboratory Test", "Rejected") and _ticket_status_accepts("Pending Second Weight"):
				values["ticket_status"] = "Pending Second Weight"

		frappe.db.set_value("Weight Bridge Ticket", self.weight_bridge_ticket, values, update_modified=True)
		frappe.clear_cache(doctype="Weight Bridge Ticket")

	def _clear_weight_bridge_ticket_lab_status(self):
		values = {
			"laboratory_status": "Pending Laboratory Test",
			"laboratory_test": None,
			"laboratory_pool": None,
		}
		if frappe.db.get_value("Weight Bridge Ticket", self.weight_bridge_ticket, "ticket_status") == "Rejected":
			values["ticket_status"] = "Pending Second Weight"

		frappe.db.set_value("Weight Bridge Ticket", self.weight_bridge_ticket, values, update_modified=True)
		frappe.clear_cache(doctype="Weight Bridge Ticket")

	def _settings(self):
		return frappe.get_single("Laboratory Settings")

	def _evaluation_mode(self, settings):
		return settings.evaluation_mode or HYBRID_MODE


@frappe.whitelist()
def get_weight_bridge_ticket_for_plate(plate_number):
	if not plate_number:
		return {}

	tickets = frappe.get_all(
		"Weight Bridge Ticket",
		filters={
			"plate_number": plate_number,
			"docstatus": ("!=", 2),
		},
		fields=[
			"name",
			"plate_number",
			"driver",
			"driver_name",
			"cargo_item",
			"first_weight",
			"first_weight_datetime",
			"ticket_status",
			"docstatus",
		],
		order_by="creation desc",
		limit=5,
	)
	for ticket in tickets:
		if ticket.ticket_status in ("Pending Second Weight", "Pending Laboratory Test", "Rejected"):
			return ticket

	return tickets[0] if tickets else {}


def _get_weight_bridge_ticket_details(ticket_name):
	return frappe.db.get_value(
		"Weight Bridge Ticket",
		ticket_name,
		[
			"name",
			"plate_number",
			"driver",
			"driver_name",
			"cargo_item",
			"first_weight",
			"first_weight_datetime",
			"ticket_status",
			"docstatus",
		],
		as_dict=True,
	)


def _ticket_status_accepts(value):
	field = frappe.get_meta("Weight Bridge Ticket").get_field("ticket_status")
	options = [option for option in (field.options or "").split("\n") if option] if field else []
	return value in options
