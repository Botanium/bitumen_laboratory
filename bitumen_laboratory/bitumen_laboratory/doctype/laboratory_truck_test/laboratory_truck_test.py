import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt, now_datetime


PASS_STATUS = "Passed"
REJECT_STATUS = "Rejected"
PENDING_STATUS = "Draft"


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
		self._validate_pool()

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
		if self.laboratory_status != PASS_STATUS:
			return

		if not self.pool:
			frappe.throw(_("Pool is required when the laboratory test passes."))
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
		if self._value_outside_limits(flt(self.flash_point), settings.minimum_flash_point, settings.maximum_flash_point):
			self.laboratory_status = REJECT_STATUS
			return
		if self._value_outside_limits(flt(self.viscosity), settings.minimum_viscosity, settings.maximum_viscosity):
			self.laboratory_status = REJECT_STATUS
			return

		self.laboratory_status = PASS_STATUS

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
			"laboratory_pool": self.pool if self.laboratory_status == PASS_STATUS else None,
		}
		if self.laboratory_status == REJECT_STATUS and _ticket_status_accepts("Rejected"):
			values["ticket_status"] = "Rejected"

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
