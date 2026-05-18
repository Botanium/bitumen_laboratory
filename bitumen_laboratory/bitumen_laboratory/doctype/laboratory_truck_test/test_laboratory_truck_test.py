import frappe
from frappe.tests.utils import FrappeTestCase

from bitumen_laboratory.install import LABORATORY_SETTINGS_DEFAULTS, before_tests
from weight_bridge.install import ensure_weight_bridge_settings, seed_master_data


TEST_PLATE = "LAB-TEST-001"
TEST_DRIVER = "+9647700000099"
test_ignore = ["Purchase Order", "Sales Order"]


class TestLaboratoryTruckTest(FrappeTestCase):
	def setUp(self):
		seed_master_data()
		ensure_weight_bridge_settings()
		before_tests()
		self.pool = self._ensure_pool()
		self._ensure_test_truck_and_driver()
		self._clear_test_records()
		self._reset_laboratory_settings()

	def test_lab_test_fetches_weight_bridge_ticket_details_from_plate_number(self):
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(weight_bridge_ticket=None, pool=None)
		lab_test.insert(ignore_permissions=True)

		self.assertEqual(lab_test.weight_bridge_ticket, ticket.name)
		self.assertEqual(lab_test.driver_name, "Laboratory Test Driver")
		self.assertEqual(lab_test.cargo_item, "VR")
		self.assertEqual(lab_test.weight, 45000)
		self.assertEqual(lab_test.laboratory_status, "Draft")

	def test_automatic_passed_lab_test_requires_pool_and_updates_weight_bridge_ticket(self):
		self._set_laboratory_settings(
			evaluation_mode="Automatic",
			minimum_flash_point=100,
			maximum_flash_point=300,
			minimum_viscosity=10,
			maximum_viscosity=80,
		)
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(pool=None, flash_point=180, viscosity=45).insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(pool=self.pool, flash_point=180, viscosity=45)
		lab_test.insert(ignore_permissions=True)
		lab_test.submit()

		self.assertEqual(lab_test.laboratory_status, "Passed")
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_status"),
			"Passed",
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_test"),
			lab_test.name,
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_pool"),
			self.pool,
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "ticket_status"),
			"Pending Second Weight",
		)

	def test_rejected_lab_test_does_not_require_pool_and_marks_ticket_rejected(self):
		self._set_laboratory_settings(
			evaluation_mode="Automatic",
			minimum_flash_point=100,
			maximum_flash_point=300,
			minimum_viscosity=10,
			maximum_viscosity=80,
		)
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(pool=None, flash_point=90, viscosity=45)
		lab_test.insert(ignore_permissions=True)
		lab_test.submit()

		self.assertEqual(lab_test.laboratory_status, "Rejected")
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_status"),
			"Rejected",
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_test"),
			lab_test.name,
		)
		self.assertIsNone(frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_pool"))
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "ticket_status"),
			"Rejected",
		)

	def test_hybrid_mode_without_criteria_saves_draft_and_blocks_submit(self):
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(pool=None, flash_point=180, viscosity=45)
		lab_test.insert(ignore_permissions=True)

		self.assertEqual(lab_test.laboratory_status, "Draft")
		with self.assertRaises(frappe.ValidationError):
			lab_test.submit()

	def test_manual_passed_lab_test_uses_operator_decision(self):
		self._set_laboratory_settings(evaluation_mode="Manual")
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(
				pool=None,
				flash_point=180,
				viscosity=45,
				laboratory_status="Passed",
			).insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(
			pool=self.pool,
			flash_point=180,
			viscosity=45,
			laboratory_status="Passed",
		)
		lab_test.insert(ignore_permissions=True)
		lab_test.submit()

		self.assertEqual(lab_test.laboratory_status, "Passed")
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_status"),
			"Passed",
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_pool"),
			self.pool,
		)

	def test_accepted_with_exception_routes_failed_test_to_pool_without_rejecting_ticket(self):
		self._set_laboratory_settings(
			evaluation_mode="Automatic",
			minimum_flash_point=100,
			maximum_flash_point=300,
			minimum_viscosity=10,
			maximum_viscosity=80,
			allow_failed_test_exception=1,
		)
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(
			pool=self.pool,
			flash_point=90,
			viscosity=45,
			accept_failed_result=1,
			exception_reason="Management approved discounted intake.",
		)
		lab_test.insert(ignore_permissions=True)
		lab_test.submit()

		self.assertEqual(lab_test.laboratory_status, "Accepted With Exception")
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_status"),
			"Accepted With Exception",
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_pool"),
			self.pool,
		)
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "ticket_status"),
			"Pending Second Weight",
		)

	def test_accepted_with_exception_requires_settings_reason_and_pool(self):
		self._set_laboratory_settings(
			evaluation_mode="Automatic",
			minimum_flash_point=100,
			maximum_flash_point=300,
			minimum_viscosity=10,
			maximum_viscosity=80,
		)
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(
				pool=self.pool,
				flash_point=90,
				viscosity=45,
				accept_failed_result=1,
				exception_reason="Management approved discounted intake.",
			).insert(ignore_permissions=True)

		self._set_laboratory_settings(allow_failed_test_exception=1)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(
				pool=None,
				flash_point=90,
				viscosity=45,
				accept_failed_result=1,
				exception_reason="Management approved discounted intake.",
			).insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(
				pool=self.pool,
				flash_point=90,
				viscosity=45,
				accept_failed_result=1,
				exception_reason="",
			).insert(ignore_permissions=True)

	def test_laboratory_settings_validate_limit_ranges(self):
		settings = frappe.get_single("Laboratory Settings")

		settings.evaluation_mode = "Invalid"
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

		settings.reload()
		settings.minimum_flash_point = 300
		settings.maximum_flash_point = 100
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

		settings.reload()
		settings.minimum_viscosity = -1
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

	def test_laboratory_metadata_and_weight_bridge_extension_are_available(self):
		test_meta = frappe.get_meta("Laboratory Truck Test")
		settings_meta = frappe.get_meta("Laboratory Settings")
		weight_bridge_meta = frappe.get_meta("Weight Bridge Ticket")
		workspace = frappe.get_doc("Workspace", "Laboratory")

		self.assertTrue(test_meta.is_submittable)
		self.assertTrue(settings_meta.issingle)
		self.assertEqual(test_meta.get_field("pool").options, "Warehouse")
		self.assertEqual(test_meta.get_field("flash_point").fieldtype, "Float")
		self.assertEqual(test_meta.get_field("viscosity").fieldtype, "Float")
		self.assertIsNotNone(test_meta.get_field("accept_failed_result"))
		self.assertIsNotNone(settings_meta.get_field("evaluation_mode"))
		self.assertIsNotNone(settings_meta.get_field("allow_failed_test_exception"))
		self.assertIsNotNone(weight_bridge_meta.get_field("laboratory_status"))
		self.assertIsNotNone(weight_bridge_meta.get_field("laboratory_test"))
		self.assertEqual(weight_bridge_meta.get_field("laboratory_section").insert_after, "net_weight")
		self.assertEqual(weight_bridge_meta.get_field("laboratory_status").insert_after, "laboratory_section")
		self.assertEqual(weight_bridge_meta.get_field("laboratory_test").insert_after, "laboratory_status")
		self.assertEqual(weight_bridge_meta.get_field("laboratory_pool").insert_after, "laboratory_test")
		self.assertIn(
			"Accepted With Exception",
			weight_bridge_meta.get_field("laboratory_status").options.split("\n"),
		)
		self.assertIn("Rejected", weight_bridge_meta.get_field("ticket_status").options.split("\n"))
		self.assertEqual(workspace.public, 1)

	def test_plate_lookup_uses_latest_active_weight_bridge_ticket(self):
		first_ticket = self._new_weight_bridge_ticket(first_weight=41000)
		first_ticket.insert(ignore_permissions=True)
		second_ticket = self._new_weight_bridge_ticket(first_weight=45500)
		second_ticket.insert(ignore_permissions=True)

		from bitumen_laboratory.bitumen_laboratory.doctype.laboratory_truck_test.laboratory_truck_test import (
			get_weight_bridge_ticket_for_plate,
		)

		result = get_weight_bridge_ticket_for_plate(TEST_PLATE)

		self.assertEqual(result.name, second_ticket.name)
		self.assertEqual(result.first_weight, 45500)

	def test_cancelled_laboratory_test_clears_ticket_lab_status(self):
		self._set_laboratory_settings(
			evaluation_mode="Automatic",
			minimum_flash_point=100,
			maximum_flash_point=300,
			minimum_viscosity=10,
			maximum_viscosity=80,
		)
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)
		lab_test = self._new_laboratory_test(pool=None, flash_point=90, viscosity=45)
		lab_test.insert(ignore_permissions=True)
		lab_test.submit()

		lab_test.cancel()

		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_status"),
			"Pending Laboratory Test",
		)
		self.assertIsNone(frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_test"))
		self.assertEqual(
			frappe.db.get_value("Weight Bridge Ticket", ticket.name, "ticket_status"),
			"Pending Second Weight",
		)

	def test_disabled_auto_update_keeps_weight_bridge_ticket_unchanged(self):
		self._set_laboratory_settings(evaluation_mode="Manual", auto_update_weight_bridge_ticket=0)
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)

		lab_test = self._new_laboratory_test(pool=self.pool, laboratory_status="Passed")
		lab_test.insert(ignore_permissions=True)
		lab_test.submit()

		self.assertIn(frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_status"), (None, ""))
		self.assertIsNone(frappe.db.get_value("Weight Bridge Ticket", ticket.name, "laboratory_test"))

	def test_passed_lab_test_rejects_group_or_disabled_pool(self):
		self._set_laboratory_settings(evaluation_mode="Manual")
		ticket = self._new_weight_bridge_ticket()
		ticket.insert(ignore_permissions=True)
		group_pool = self._ensure_pool("Laboratory Group Pool", is_group=1)
		disabled_pool = self._ensure_pool("Laboratory Disabled Pool", disabled=1)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(pool=group_pool, laboratory_status="Passed").insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			self._new_laboratory_test(pool=disabled_pool, laboratory_status="Passed").insert(ignore_permissions=True)

	def _new_laboratory_test(
		self,
		weight_bridge_ticket=None,
		pool=None,
		flash_point=180,
		viscosity=45,
		laboratory_status="Draft",
		accept_failed_result=0,
		exception_reason=None,
	):
		return frappe.get_doc(
			{
				"doctype": "Laboratory Truck Test",
				"test_datetime": "2099-02-01 12:00:00",
				"plate_number": TEST_PLATE,
				"weight_bridge_ticket": weight_bridge_ticket,
				"pool": pool,
				"flash_point": flash_point,
				"viscosity": viscosity,
				"laboratory_status": laboratory_status,
				"accept_failed_result": accept_failed_result,
				"exception_reason": exception_reason,
			}
		)

	def _new_weight_bridge_ticket(self, first_weight=45000):
		return frappe.get_doc(
			{
				"doctype": "Weight Bridge Ticket",
				"plate_number": TEST_PLATE,
				"driver": TEST_DRIVER,
				"operator": "Administrator",
				"cargo_item": "VR",
				"origin_type": "Warehouse",
				"origin": self.pool,
				"first_weight_datetime": "2099-02-01 10:00:00",
				"first_weight": first_weight,
			}
		)

	def _clear_test_records(self):
		frappe.db.delete("Laboratory Truck Test", {"plate_number": TEST_PLATE})
		frappe.db.delete("Weight Bridge Ticket", {"plate_number": TEST_PLATE})
		frappe.db.delete("Series", {"name": ("like", "LAB-%")})
		frappe.db.delete("Series", {"name": ("like", "WB-990201-%")})

	def _ensure_test_truck_and_driver(self):
		if not frappe.db.exists("Weight Bridge Truck", TEST_PLATE):
			frappe.get_doc(
				{
					"doctype": "Weight Bridge Truck",
					"plate_number": TEST_PLATE,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("Weight Bridge Driver", TEST_DRIVER):
			frappe.get_doc(
				{
					"doctype": "Weight Bridge Driver",
					"phone_number": TEST_DRIVER,
					"driver_name": "Laboratory Test Driver",
					"passport_number": "LAB123456",
					"national_code": "LAB123456",
				}
			).insert(ignore_permissions=True)

	def _ensure_pool(self, warehouse_name="Laboratory Pool", is_group=0, disabled=0):
		pool = frappe.db.get_value(
			"Warehouse",
			{"warehouse_name": warehouse_name, "is_group": is_group},
			"name",
		)
		if pool:
			frappe.db.set_value("Warehouse", pool, "disabled", disabled)
			return pool

		company = frappe.db.get_value("Company", {}, ["name"], as_dict=True)
		warehouse = frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": warehouse_name,
				"company": company.name,
				"is_group": is_group,
				"disabled": disabled,
			}
		).insert(ignore_permissions=True)
		return warehouse.name

	def _reset_laboratory_settings(self):
		self._set_laboratory_settings(**LABORATORY_SETTINGS_DEFAULTS)

	def _set_laboratory_settings(self, **kwargs):
		settings = frappe.get_single("Laboratory Settings")
		for fieldname, value in kwargs.items():
			settings.set(fieldname, value)
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Laboratory Settings")
