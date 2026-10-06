# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Hardcoded safety allowlist for the AI dynamic query layer.

This is Python source, not configurable data — exactly as trusted as the 12
KPI providers themselves. Nothing an LLM response or a stored
``sgc.kpi.definition`` record says can ever widen it. Every model/field the
AI layer (``sgc.provider.dynamic``, ``sgc.ai.assistant``) may touch has to
be explicitly listed here, grounded in what the real providers under
``models/providers/`` actually read — never guessed.

Four disjoint field roles per model:
  - ``date_fields``: {field: 'date'|'datetime'} — usable as a window/series field.
  - ``measures``:    {field: value_format} — usable as an aggregate (sum/avg/min/max).
  - ``groups``:      [field, ...] — usable as a `_read_group` groupby dimension.
  - ``filters``:     [field, ...] — usable as a domain leaf field.
A field not listed in a role cannot be used in that role, ever, even if it
also appears in another role or exists on the model.
"""
from odoo import models

_SGC_CAPABILITIES = {
    # ---------------------------------------------------------------- Finance
    'account.move': {
        'module': 'account',
        'label': 'Invoices & Bills',
        'section': 'Finance',
        'company_field': 'company_id',
        'default_domain': [('state', '=', 'posted')],
        'date_fields': {
            'invoice_date': 'date', 'invoice_date_due': 'date', 'date': 'date',
        },
        'measures': {
            'amount_untaxed_signed': 'currency', 'amount_residual_signed': 'currency',
            'amount_total_signed': 'currency',
        },
        'groups': ['move_type', 'payment_state', 'state', 'partner_id', 'journal_id'],
        'filters': [
            'move_type', 'state', 'payment_state', 'partner_id', 'journal_id',
            'invoice_date', 'invoice_date_due', 'date',
            'journal_id.type',    # curated dotted literal, matched whole-string only
            'einvoice_state',     # conditional: only present with uae_einvoice_core
        ],
    },
    'aml.transaction.alert': {
        'module': 'aml_compliance',
        'label': 'AML Alerts',
        'section': 'Finance',
        'company_field': None,
        'default_domain': [],
        'date_fields': {},
        'measures': {},
        'groups': ['state'],
        'filters': ['state'],
    },

    # -------------------------------------------------------------- CRM/Sales
    'crm.lead': {
        'module': 'crm',
        'label': 'Pipeline (Opportunities)',
        'section': 'CRM & Sales',
        'company_field': 'company_id',
        'default_domain': [('type', '=', 'opportunity')],
        'date_fields': {'date_closed': 'datetime', 'create_date': 'datetime'},
        'measures': {'expected_revenue': 'currency', 'probability': 'percent',
                     'x_gate_answered_count': 'number'},
        'groups': ['stage_id', 'user_id', 'team_id', 'partner_id',
                   'x_gate_status', 'x_research_pain_tier'],
        'filters': [
            'active', 'stage_id', 'probability', 'date_closed', 'user_id',
            'team_id', 'partner_id',
            'stage_id.is_won',   # curated dotted literal
            # sgc_sales_playbook fields — pruned automatically by
            # _sgc_field_survives() if that module isn't installed.
            'x_gate_status', 'x_gate_answered_count', 'x_research_pain_tier',
        ],
    },
    'sale.order': {
        # Shared by provider_crm_sales.py and provider_deals.py. deal_* fields
        # only exist when sgc_deals_management is installed — pruned at
        # runtime by available_capabilities(), never assumed present.
        'module': 'sale_management',
        'label': 'Sales Orders & Deals',
        'section': 'CRM & Sales',
        'company_field': 'company_id',
        'default_domain': [],
        'date_fields': {'date_order': 'datetime', 'deal_date': 'date'},
        'measures': {'amount_untaxed': 'currency', 'deal_sales_value': 'currency'},
        'groups': ['state', 'partner_id', 'user_id', 'team_id', 'deal_stage_id'],
        'filters': ['state', 'partner_id', 'user_id', 'date_order', 'is_deal', 'deal_date'],
    },

    # ------------------------------------------------------------- Procurement
    'purchase.order': {
        'module': 'purchase',
        'label': 'Purchase Orders',
        'section': 'Procurement',
        'company_field': 'company_id',
        'default_domain': [],
        'date_fields': {'date_approve': 'datetime', 'date_order': 'datetime'},
        'measures': {'amount_untaxed': 'currency'},
        'groups': ['state', 'partner_id'],
        'filters': ['state', 'partner_id', 'date_approve', 'date_order'],
    },

    # --------------------------------------------------------------- HR/People
    'hr.employee': {
        'module': 'hr',
        'label': 'Employees',
        'section': 'People',
        'company_field': 'company_id',
        'default_domain': [],
        'date_fields': {'create_date': 'datetime'},
        'measures': {},
        'groups': ['department_id'],
        'filters': ['department_id', 'active'],
    },
    'hr.attendance': {
        'module': 'hr_attendance',
        'label': 'Attendance',
        'section': 'People',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'check_in': 'datetime', 'check_out': 'datetime'},
        'measures': {},
        'groups': ['employee_id'],
        'filters': ['employee_id', 'check_in', 'check_out'],
    },
    'hr.leave': {
        'module': 'hr_holidays',
        'label': 'Leave Requests',
        'section': 'People',
        'company_field': None,
        'default_domain': [],
        'date_fields': {},
        'measures': {},
        'groups': ['state', 'employee_id'],
        'filters': ['state', 'employee_id'],
    },
    'hr.job': {
        'module': 'hr_recruitment',
        'label': 'Job Positions',
        'section': 'People',
        'company_field': 'company_id',
        'default_domain': [],
        'date_fields': {},
        'measures': {'no_of_recruitment': 'number'},
        'groups': ['department_id'],
        'filters': ['department_id', 'no_of_recruitment'],
    },
    'hr.payslip': {
        'module': 'hr_payroll_community',
        'label': 'Payslips',
        'section': 'People',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'date_from': 'date', 'date_to': 'date'},
        'measures': {},
        'groups': ['state'],
        'filters': ['state', 'date_from', 'date_to'],
    },

    # -------------------------------------------------------------- Delivery
    'project.task': {
        'module': 'project',
        'label': 'Project Tasks',
        'section': 'Delivery',
        'company_field': 'company_id',
        'default_domain': [],
        'date_fields': {'date_deadline': 'date'},
        'measures': {},
        'groups': ['state', 'project_id'],
        'filters': ['state', 'date_deadline', 'project_id'],
    },
    'project.project': {
        'module': 'project',
        'label': 'Projects',
        'section': 'Delivery',
        'company_field': 'company_id',
        'default_domain': [],
        'date_fields': {},
        'measures': {},
        'groups': [],
        'filters': ['active'],
    },

    # ----------------------------------------------------------- Construction
    'construction.project': {
        'module': 'sgc_construction_management',
        'label': 'Construction Projects',
        'section': 'Construction',
        'company_field': None,
        'default_domain': [],
        'date_fields': {},
        # progress/planned_progress/open_ncr_count are computed, non-stored
        # fields (see provider_construction.py comments) — deliberately
        # excluded, they are not SQL-aggregatable via _read_group.
        'measures': {
            'contract_value': 'currency', 'total_billed': 'currency',
            'total_expenses': 'currency', 'budget_consumed': 'percent',
            'margin_percent': 'percent',
        },
        'groups': ['name'],
        'filters': [],
    },
    'construction.wbs': {
        'module': 'sgc_construction_management',
        'label': 'Construction WBS Lines',
        'section': 'Construction',
        'company_field': None,
        'default_domain': [],
        # progress is computed/non-stored on this model too — excluded.
        'date_fields': {'actual_end': 'date', 'planned_end': 'date'},
        'measures': {'actual_cost': 'currency'},
        'groups': ['project_id'],
        'filters': ['project_id', 'actual_end', 'planned_end'],
    },

    # ------------------------------------------------------------- Real Estate
    'property.details': {
        'module': 'sgc_offplan_rental_property_management',
        'label': 'Properties',
        'section': 'Real Estate',
        'company_field': None,
        'default_domain': [],
        'date_fields': {},
        'measures': {},
        'groups': ['property_type'],
        'filters': ['active', 'property_type'],
    },
    'sale.contract': {
        'module': 'sgc_offplan_rental_property_management',
        'label': 'Sale Contracts',
        'section': 'Real Estate',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'contract_date': 'date'},
        'measures': {'sale_price': 'currency'},
        'groups': ['property_id'],
        'filters': ['property_id', 'contract_date'],
    },
    'tenancy.details': {
        'module': 'sgc_offplan_rental_property_management',
        'label': 'Tenancies',
        'section': 'Real Estate',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'start_date': 'date', 'end_date': 'date'},
        'measures': {},
        'groups': ['state'],
        'filters': ['state', 'start_date', 'end_date'],
    },
    'rent.invoice': {
        'module': 'sgc_offplan_rental_property_management',
        'label': 'Rent Invoices',
        'section': 'Real Estate',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'invoice_date': 'date'},
        'measures': {'amount': 'currency'},
        'groups': [],
        'filters': ['invoice_date'],
    },

    # ------------------------------------------------------------- Commission
    'commission.line': {
        'module': 'sgc_commission',
        'label': 'Commission Lines',
        'section': 'Commission',
        'company_field': None,
        'default_domain': [],
        'date_fields': {},
        'measures': {'base_amount': 'currency'},
        'groups': ['state', 'partner_id', 'user_id'],
        'filters': ['state', 'partner_id', 'user_id'],
    },

    # ------------------------------------------------------------- Compliance
    'kyc.application': {
        'module': 'kyc_management',
        'label': 'KYC Applications',
        'section': 'Compliance',
        'company_field': None,
        'default_domain': [],
        # is_kyc_complete is computed/non-stored (see provider_compliance.py) — excluded.
        'date_fields': {
            'passport_expiry_date': 'date', 'residency_expiry_date': 'date',
            'create_date': 'datetime',
        },
        'measures': {},
        'groups': ['state'],
        'filters': ['state', 'passport_expiry_date', 'residency_expiry_date'],
    },

    # -------------------------------------------------------------- Learning
    'learning.progress': {
        'module': 'sgc_elearning',
        'label': 'Learning Progress',
        'section': 'Learning',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'last_access_date': 'datetime'},
        'measures': {},
        'groups': [],
        'filters': ['completed', 'last_access_date'],
    },
    'learning.certificate': {
        'module': 'sgc_elearning',
        'label': 'Learning Certificates',
        'section': 'Learning',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'completion_date': 'datetime'},
        'measures': {},
        'groups': [],
        'filters': ['is_valid', 'completion_date'],
    },
    'assessment.candidate': {
        'module': 'sgc_assessment',
        'label': 'Assessment Candidates',
        'section': 'Learning',
        'company_field': None,
        'default_domain': [],
        'date_fields': {},
        'measures': {'overall_score': 'number'},
        'groups': [],
        'filters': [],
    },

    # -------------------------------------------------------- Video Conferencing
    'video.meeting': {
        'module': 'sgc_video_conferencing',
        'label': 'Video Meetings',
        'section': 'Video Conferencing',
        'company_field': None,
        'default_domain': [],
        'date_fields': {'start_time': 'datetime'},
        'measures': {'actual_duration_minutes': 'duration'},
        'groups': [],
        'filters': ['start_time'],
    },
}

# Field types that may never act as a `_read_group` groupby dimension, even
# if a model's entry mistakenly lists one — a defense-in-depth backstop
# below the declarative allowlist itself.
_SGC_DISALLOWED_GROUP_TYPES = {
    'many2many', 'one2many', 'binary', 'html', 'reference',
}
_SGC_ALLOWED_GROUP_TYPES = {
    'many2one', 'selection', 'char', 'boolean', 'date', 'datetime',
}


class SgcCapability(models.AbstractModel):
    """SGC AI — safe model/field allowlist for dynamic queries.

    No persistence, no admin UI: the allowlist is Python source, exactly as
    hardcoded/trusted as the 12 KPI providers. Every public method here is
    read-only introspection — nothing on this model ever touches business
    data.
    """
    _name = 'sgc.capability'
    _description = 'SGC AI — Safe Model/Field Allowlist'

    def _sgc_module_installed(self, module_name):
        if not module_name:
            return True
        return bool(self.env['ir.module.module'].sudo().search_count([
            ('name', '=', module_name),
            ('state', 'in', ('installed', 'to upgrade')),
        ]))

    def _sgc_field_survives(self, model_name, field_name):
        """A field only counts as usable if it exists, is stored, and is a
        real base field name (no dotted traversal here — curated dotted
        literals in `filters` are validated separately in `field_info`).
        """
        if '.' in field_name:
            return False
        Model = self.env.get(model_name)
        if Model is None:
            return False
        field = Model._fields.get(field_name)
        return bool(field is not None and getattr(field, 'store', False))

    def available_capabilities(self):
        """Every capability entry whose gating module is installed and whose
        model is present in the current registry, with every field pruned
        down to what actually exists and is stored right now. This is what
        makes conditional fields (deal_sales_value, wps_*, einvoice_state,
        etc.) safe to declare unconditionally above.
        """
        out = {}
        for model_name, cap in _SGC_CAPABILITIES.items():
            if not self._sgc_module_installed(cap['module']):
                continue
            if model_name not in self.env.registry.models:
                continue
            pruned = dict(cap)
            pruned['date_fields'] = {
                f: kind for f, kind in cap['date_fields'].items()
                if self._sgc_field_survives(model_name, f)
            }
            pruned['measures'] = {
                f: fmt for f, fmt in cap['measures'].items()
                if self._sgc_field_survives(model_name, f)
            }
            pruned['groups'] = [
                f for f in cap['groups'] if self._sgc_field_survives(model_name, f)
                and self.env[model_name]._fields[f].type in _SGC_ALLOWED_GROUP_TYPES
            ]
            pruned['filters'] = [
                f for f in cap['filters']
                if self._sgc_field_survives(model_name, f) or (
                    # curated dotted literal: only the first hop must exist
                    # and be a many2one — no generic traversal logic.
                    '.' in f and self._sgc_dotted_literal_ok(model_name, f)
                )
            ]
            out[model_name] = pruned
        return out

    def _sgc_dotted_literal_ok(self, model_name, dotted_field):
        first_hop = dotted_field.split('.', 1)[0]
        Model = self.env.get(model_name)
        if Model is None:
            return False
        field = Model._fields.get(first_hop)
        return bool(field is not None and field.type == 'many2one')

    def model_info(self, model_name):
        return self.available_capabilities().get(model_name)

    def is_model_allowed(self, model_name):
        return model_name in self.available_capabilities()

    def field_info(self, model_name, field_name):
        """Returns a small descriptor if `field_name` is allowlisted in ANY
        role on `model_name`, else None. Used by `sgc.ai.intent._do_explain`
        to probe candidate group-field dimensions — it can only ever confirm
        an allowlisted field, never invent one.
        """
        cap = self.model_info(model_name)
        if not cap:
            return None
        if field_name in cap['groups']:
            return {'role': 'group', 'type': self.env[model_name]._fields[field_name].type}
        if field_name in cap['measures']:
            return {'role': 'measure', 'format': cap['measures'][field_name]}
        if field_name in cap['date_fields']:
            return {'role': 'date', 'kind': cap['date_fields'][field_name]}
        if field_name in cap['filters']:
            return {'role': 'filter'}
        return None

    def allowed_operators(self):
        return frozenset({
            '=', '!=', '>', '>=', '<', '<=', 'in', 'not in',
            'ilike', 'not ilike', 'like', '=like',
        })

    def describe_for_llm(self, max_chars=6000):
        """Compact per-model catalogue string for the assistant's system
        prompt. Truncates by dropping the lowest-priority (fewest fields)
        models first if the budget is exceeded, and says so.
        """
        caps = self.available_capabilities()
        entries = []
        for model_name, cap in caps.items():
            weight = (len(cap['measures']) + len(cap['groups'])
                      + len(cap['date_fields']) + len(cap['filters']))
            entries.append((weight, model_name, cap))
        entries.sort(key=lambda t: t[0], reverse=True)

        lines, truncated = [], False
        for weight, model_name, cap in entries:
            line = (
                f"{model_name} ({cap['label']}) | "
                f"dates: {', '.join(f'{f}({k[:2]})' for f, k in cap['date_fields'].items()) or '-'} | "
                f"measures: {', '.join(f'{f}({fmt})' for f, fmt in cap['measures'].items()) or '-'} | "
                f"group by: {', '.join(cap['groups']) or '-'} | "
                f"filter on: {', '.join(cap['filters']) or '-'}"
            )
            if sum(len(l) for l in lines) + len(line) > max_chars:
                truncated = True
                break
            lines.append(line)
        if truncated:
            lines.append(
                f"... ({len(entries) - len(lines)} additional lower-priority "
                f"model(s) omitted for length)")
        return '\n'.join(lines)
