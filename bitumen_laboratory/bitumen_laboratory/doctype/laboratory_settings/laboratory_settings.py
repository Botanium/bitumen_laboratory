import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LaboratorySettings(Document):
	def validate(self):
		self._validate_limit_pair("minimum_flash_point", "maximum_flash_point", "Flash Point")
		self._validate_limit_pair("minimum_viscosity", "maximum_viscosity", "Viscosity")

	def _validate_limit_pair(self, min_field, max_field, label):
		min_value = flt(self.get(min_field))
		max_value = flt(self.get(max_field))

		if min_value < 0:
			frappe.throw(_("{0} minimum cannot be negative.").format(label))
		if max_value < 0:
			frappe.throw(_("{0} maximum cannot be negative.").format(label))
		if max_value and min_value > max_value:
			frappe.throw(_("{0} minimum cannot be greater than maximum.").format(label))

