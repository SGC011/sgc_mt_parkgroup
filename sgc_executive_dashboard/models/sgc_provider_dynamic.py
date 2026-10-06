# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Validated execution engine for AI-driven KPI queries.

This is the single ORM entry point every AI-produced or AI-saved query must
pass through. It is deliberately NOT a `sgc.kpi.provider` subclass — the
dashboard aggregator (`sgc.executive.dashboard._sgc_providers`) auto-
discovers any model whose `_inherit` contains `sgc.kpi.provider`, and
`tests/test_aggregator.py` hard-asserts exactly 12 provider sections. This
model must never become a 13th.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_MAX_DOMAIN_LEAVES = 20
_MAX_DOMAIN_ELEMENTS = 40
_MAX_IN_LIST_LEN = 100
_MAX_STRING_LEN = 256
_ALLOWED_AGGREGATES = {'count', 'sum', 'avg', 'min', 'max'}
_ALLOWED_GROUP_TYPES = {
    'many2one', 'selection', 'char', 'boolean', 'date', 'datetime',
}


class SgcProviderDynamic(models.AbstractModel):
    # No `_inherit = 'sgc.kpi.provider'` — see module docstring above.
    _name = 'sgc.provider.dynamic'
    _description = 'SGC AI — Validated Dynamic KPI Query Executor'

    # ------------------------------------------------------------ validation
    @api.model
    def _sgc_sanitize_value(self, value):
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            if len(value) > _MAX_STRING_LEN:
                raise UserError(_("A filter value is too long."))
            return value
        if isinstance(value, (list, tuple)):
            if len(value) > _MAX_IN_LIST_LEN:
                raise UserError(_("A filter list is too long."))
            out = []
            for v in value:
                if isinstance(v, (list, tuple, dict)):
                    raise UserError(_("Nested filter values are not allowed."))
                out.append(self._sgc_sanitize_value(v))
            return out
        raise UserError(_("Unsupported filter value type."))

    @api.model
    def _sgc_validate_domain(self, domain, model_name, cap, Capability):
        if not isinstance(domain, list):
            raise UserError(_("The query filter must be a list."))
        if len(domain) > _MAX_DOMAIN_ELEMENTS:
            raise UserError(_("The query filter is too complex."))
        leaves = 0
        out = []
        allowed_ops = Capability.allowed_operators()
        for element in domain:
            if isinstance(element, str):
                if element not in ('&', '|', '!'):
                    raise UserError(_("Invalid filter operator: %s", element))
                out.append(element)
                continue
            if not (isinstance(element, (list, tuple)) and len(element) == 3):
                raise UserError(_("Invalid filter clause."))
            field, op, value = element
            if not isinstance(field, str) or field not in cap['filters']:
                raise UserError(_(
                    "The AI proposed a field that is not available for "
                    "filtering: %s", field))
            if op not in allowed_ops:
                raise UserError(_("Filter operator not allowed: %s", op))
            value = self._sgc_sanitize_value(value)
            out.append((field, op, value))
            leaves += 1
        if leaves > _MAX_DOMAIN_LEAVES:
            raise UserError(_("The query filter has too many conditions."))
        return out

    @api.model
    def _sgc_validate(self, spec):
        """Rebuild a spec from scratch, keeping only whitelisted keys with
        whitelisted values. Never mutates or passes through the caller's
        dict. Raises `UserError` with a client-safe message on any
        violation. Called unconditionally by `_sgc_execute`, even for a
        spec sourced from an already-stored `sgc.kpi.definition` — a saved
        definition must never bypass this just because it's data rather
        than a live LLM response.
        """
        if not isinstance(spec, dict):
            raise UserError(_("Invalid query specification."))

        Capability = self.env['sgc.capability']

        model_name = spec.get('model_name')
        if not isinstance(model_name, str):
            raise UserError(_("A model name is required."))
        cap = Capability.model_info(model_name)
        if not cap:
            raise UserError(_(
                "The AI proposed a model that is not available to this "
                "dashboard: %s", model_name))

        aggregate = spec.get('aggregate') or 'count'
        if aggregate not in _ALLOWED_AGGREGATES:
            raise UserError(_("Invalid aggregate function: %s", aggregate))

        measure_field = spec.get('measure_field')
        if aggregate == 'count':
            measure_field = None
        elif measure_field is not None:
            if not isinstance(measure_field, str) or measure_field not in cap['measures']:
                raise UserError(_(
                    "The AI proposed a measure that is not available: %s",
                    measure_field))
            field = self.env[model_name]._fields.get(measure_field)
            if field is None or field.type not in ('integer', 'float', 'monetary') \
                    or not getattr(field, 'store', False):
                raise UserError(_("The proposed measure field is not aggregatable."))
        else:
            # A non-count aggregate needs a measure — fall back to count
            # rather than erroring, since the LLM may reasonably omit it.
            aggregate = 'count'

        date_field = spec.get('date_field')
        if date_field is not None:
            if not isinstance(date_field, str) or date_field not in cap['date_fields']:
                raise UserError(_(
                    "The AI proposed a date field that is not available: %s",
                    date_field))

        group_field = spec.get('group_field')
        if group_field is not None:
            if not isinstance(group_field, str) or group_field not in cap['groups']:
                raise UserError(_(
                    "The AI proposed a grouping field that is not available: %s",
                    group_field))
            field = self.env[model_name]._fields.get(group_field)
            if field is None or field.type not in _ALLOWED_GROUP_TYPES \
                    or not getattr(field, 'store', False):
                raise UserError(_("The proposed grouping field cannot be used."))

        domain = self._sgc_validate_domain(spec.get('domain') or [], model_name, cap, Capability)

        limit = spec.get('limit')
        try:
            limit = int(limit) if limit is not None else 10
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))

        order = spec.get('order') if spec.get('order') in ('asc', 'desc') else 'desc'
        viz = spec.get('viz') if spec.get('viz') in (
            'kpi', 'bar', 'line', 'doughnut', 'polarArea') else 'kpi'
        value_format = spec.get('value_format') if spec.get('value_format') in (
            'currency', 'number', 'percent', 'duration') else (
            cap['measures'].get(measure_field, 'number') if measure_field else 'number')

        def _clean_text(value, max_len):
            if not isinstance(value, str):
                return ''
            return ''.join(ch for ch in value if ch.isprintable())[:max_len]

        return {
            'code': _clean_text(spec.get('code') or '', 64),
            'name': _clean_text(spec.get('name') or model_name, 128),
            'model_name': model_name,
            'aggregate': aggregate,
            'measure_field': measure_field,
            'date_field': date_field,
            'group_field': group_field,
            'domain': domain,
            'limit': limit,
            'order': order,
            'viz': viz,
            'value_format': value_format,
        }

    # ------------------------------------------------------------- execution
    @api.model
    def _sgc_execute(self, spec, ctx):
        """The only ORM entry point for AI-driven queries. Always
        re-validates (defense in depth), always forces company/date scoping
        that the caller cannot remove, and only ever issues `search_count`
        or `_read_group` — no write, no create, no unlink, no plain `search`
        followed by `read`.
        """
        self.env['sgc.executive.dashboard']._sgc_check_access()
        spec = self._sgc_validate(spec)

        Capability = self.env['sgc.capability']
        cap = Capability.model_info(spec['model_name'])
        if not cap:
            return None

        domain = list(spec['domain']) + list(cap['default_domain'])
        if cap['company_field']:
            domain = domain + [(cap['company_field'], 'in', ctx['company_ids'])]
        if spec['date_field']:
            is_dt = cap['date_fields'].get(spec['date_field']) == 'datetime'
            lo, hi = (ctx['dt_from'], ctx['dt_to']) if is_dt else (ctx['date_from'], ctx['date_to'])
            domain = domain + [(spec['date_field'], '>=', lo), (spec['date_field'], '<=', hi)]

        use_sudo = self.env['ir.config_parameter'].sudo().get_param(
            'sgc_ai.dynamic_sudo', '1') == '1'
        Model = self.env[spec['model_name']]
        Model = Model.sudo() if use_sudo else Model

        try:
            if spec['aggregate'] == 'count' and not spec['group_field']:
                value = Model.search_count(domain)
                breakdown = None
            elif not spec['group_field']:
                agg = f"{spec['measure_field']}:{spec['aggregate']}"
                groups = Model._read_group(domain, [], [agg])
                value = (groups and groups[0][0]) or 0.0
                breakdown = None
            else:
                agg = (f"{spec['measure_field']}:{spec['aggregate']}"
                       if spec['measure_field'] else '__count')
                order_clause = f"{agg} {spec['order']}"
                rows = Model._read_group(
                    domain, [spec['group_field']], [agg],
                    order=order_clause, limit=spec['limit'])
                value = sum((row[1] or 0.0) for row in rows) if rows else 0.0
                labels = [
                    row[0].display_name if hasattr(row[0], 'display_name')
                    else (row[0] or _('Unassigned'))
                    for row in rows
                ]
                values = [round(row[1] or 0.0, 2) for row in rows]
                breakdown = {'labels': labels, 'values': values}
        except Exception:
            _logger.exception(
                "SGC AI dynamic query failed for model=%s spec=%s",
                spec['model_name'], spec['code'])
            return None

        series = None
        if spec['date_field']:
            try:
                series = self.env['sgc.kpi.provider']._sgc_series(
                    spec['model_name'], domain, spec['date_field'],
                    spec['measure_field'], ctx)
            except Exception:
                series = None

        return {
            'value': value,
            'value_format': spec['value_format'],
            'breakdown': breakdown,
            'series': series,
            'domain': domain,
            'model_name': spec['model_name'],
            'spec': spec,
        }

    @api.model
    def _sgc_action(self, spec, domain, name=None):
        return {
            'type': 'ir.actions.act_window',
            'name': name or spec.get('name') or spec.get('model_name'),
            'res_model': spec['model_name'],
            'domain': domain,
            'views': [[False, 'list'], [False, 'form']],
        }
