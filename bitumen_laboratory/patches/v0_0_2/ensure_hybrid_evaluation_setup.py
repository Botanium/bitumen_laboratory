from bitumen_laboratory.install import (
	ensure_laboratory_settings,
	ensure_weight_bridge_ticket_lab_fields,
)


def execute():
	ensure_laboratory_settings()
	ensure_weight_bridge_ticket_lab_fields()
