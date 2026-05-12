import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


VALID_EVALUATION_MODES = ("Hybrid", "Manual", "Automatic")


class LaboratorySettings(Document):
	def validate(self):
		self._validate_evaluation_mode()
		self._validate_limit_pair("minimum_flash_point", "maximum_flash_point", "Flash Point")
		self._validate_limit_pair("minimum_viscosity", "maximum_viscosity", "Viscosity")

	def _validate_evaluation_mode(self):
		if not self.evaluation_mode:
			self.evaluation_mode = "Hybrid"
		if self.evaluation_mode not in VALID_EVALUATION_MODES:
			frappe.throw(_("Evaluation Mode must be Hybrid, Manual, or Automatic."))

	def _validate_limit_pair(self, min_field, max_field, label):
		min_value = flt(self.get(min_field))
		max_value = flt(self.get(max_field))

		if min_value < 0:
			frappe.throw(_("{0} minimum cannot be negative.").format(label))
		if max_value < 0:
			frappe.throw(_("{0} maximum cannot be negative.").format(label))
		if max_value and min_value > max_value:
			frappe.throw(_("{0} minimum cannot be greater than maximum.").format(label))
