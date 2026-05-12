from bitumen_laboratory.install import (
	ensure_laboratory_settings,
	ensure_laboratory_workspace,
	ensure_roles_and_permissions,
	ensure_weight_bridge_ticket_lab_fields,
)


def execute():
	ensure_laboratory_settings()
	ensure_roles_and_permissions()
	ensure_weight_bridge_ticket_lab_fields()
	ensure_laboratory_workspace()

