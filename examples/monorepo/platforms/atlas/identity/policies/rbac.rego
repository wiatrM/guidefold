# Atlas RBAC policy bundle. Deny by default; see the rbac-policies skill.
# input shape: { principal: {id, roles[], orgUnit, clearance[]}, action, resource: {type, id, orgUnit, label}, context: {requestId} }
package atlas.rbac

import rego.v1

default allow := false

# Linear role inheritance: admin ⊇ supervisor ⊇ analyst.
role_rank := {"analyst": 1, "supervisor": 2, "admin": 3}

principal_rank := max([role_rank[r] | some r in input.principal.roles; role_rank[r]])

has_role(role) if principal_rank >= role_rank[role]

# Analysts may read any resource within their own org unit.
allow if {
	has_role("analyst")
	endswith(input.action, ":read")
	input.resource.orgUnit == input.principal.orgUnit
}

# Supervisors may additionally write within their org unit ...
allow if {
	has_role("supervisor")
	endswith(input.action, ":write")
	input.resource.orgUnit == input.principal.orgUnit
}

# ... and export data whose label is within their clearance.
allow if {
	has_role("supervisor")
	endswith(input.action, ":export")
	label_ok
}

# Admins may perform any action listed in the bundled roles document.
allow if {
	has_role("admin")
	input.action in data.roles.admin_actions
}

label_ok if input.resource.label in input.principal.clearance
