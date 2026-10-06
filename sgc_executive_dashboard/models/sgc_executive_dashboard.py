# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from dateutil.relativedelta import relativedelta
import datetime


class SgcExecutiveDashboard(models.AbstractModel):
    _name = 'sgc.executive.dashboard'
    _description = 'SGC Executive Dashboard Aggregator'

    # ------------------------------------------------------------------ range
    @api.model
    def _sgc_resolve_range(self, period, date_from=None, date_to=None):
        today = fields.Date.context_today(self)
        if period == 'custom' and date_from and date_to:
            return fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        if period == 'mtd':
            return today.replace(day=1), today
        if period == 'qtd':
            q_start_month = 3 * ((today.month - 1) // 3) + 1
            return today.replace(month=q_start_month, day=1), today
        if period == 'last12':
            return (today - relativedelta(months=11)).replace(day=1), today
        return today.replace(month=1, day=1), today  # ytd (default)

    @api.model
    def _sgc_context(self, period, date_from, date_to):
        d_from, d_to = self._sgc_resolve_range(period, date_from, date_to)
        company = self.env.company
        return {
            'period': period,
            'date_from': d_from,
            'date_to': d_to,
            'dt_from': datetime.datetime.combine(d_from, datetime.time.min),
            'dt_to': datetime.datetime.combine(d_to, datetime.time.max),
            'company_ids': self.env.companies.ids,
            'currency': {
                'id': company.currency_id.id,
                'symbol': company.currency_id.symbol,
                'position': company.currency_id.position,
                'decimals': company.currency_id.decimal_places,
            },
        }

    # --------------------------------------------------------------- security
    @api.model
    def _sgc_check_access(self):
        if not self.env.user.has_group('sgc_executive_dashboard.group_sgc_executive_viewer'):
            raise AccessError(_(
                "The SGC Executive Command Center is restricted to executive users."
            ))

    # ------------------------------------------------------------- providers
    @api.model
    def _sgc_providers(self):
        """Discover every AbstractModel inheriting the provider contract."""
        found = []
        for name in self.env.registry:
            if name == 'sgc.kpi.provider':
                continue
            model = self.env[name]
            inherit = model._inherit or []
            if isinstance(inherit, str):
                inherit = [inherit]
            if 'sgc.kpi.provider' in inherit:
                found.append(model)
        return sorted(found, key=lambda m: (m._sgc_sequence, m._sgc_label))

    # ------------------------------------------------------------- main call
    @api.model
    def sgc_get_dashboard(self, period='ytd', date_from=None, date_to=None):
        self._sgc_check_access()
        ctx = self._sgc_context(period, date_from, date_to)

        sections, kpis, charts = [], [], []
        for provider in self._sgc_providers():
            payload = provider._sgc_run(ctx)
            if payload is None:
                continue
            for kpi in payload['kpis']:
                kpi['source'] = provider._sgc_label
                kpis.append(kpi)
            for chart in payload['charts']:
                chart['source'] = provider._sgc_label
                charts.append(chart)
            sections.append({
                'key': provider._name,
                'label': provider._sgc_label,
                'icon': provider._sgc_icon,
                'accent': provider._sgc_accent,
                'kpi_count': len(payload['kpis']),
            })

        return {
            'meta': {
                'company': self.env.company.name,
                'company_ids': ctx['company_ids'],
                'user': self.env.user.name,
                'currency': ctx['currency'],
                'period': period,
                'date_from': fields.Date.to_string(ctx['date_from']),
                'date_to': fields.Date.to_string(ctx['date_to']),
                'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
                'can_install': self.env.user.has_group('base.group_system'),
            },
            'sections': sections,
            'kpis': kpis,
            'charts': charts,
            'universe': self.sgc_get_app_universe(),
        }

    # ------------------------------------------------- installed & dormant apps
    @api.model
    def sgc_get_app_universe(self):
        """Every Odoo application, installed or not — the 'unified' promise."""
        self._sgc_check_access()
        Module = self.env['ir.module.module'].sudo()
        modules = Module.search([('application', '=', True)], order='shortdesc asc')

        pitches = {}
        for provider in self._sgc_providers():
            if provider._sgc_module:
                pitches[provider._sgc_module] = {
                    'pitch': provider._sgc_pitch,
                    'accent': provider._sgc_accent,
                    'icon': provider._sgc_icon,
                }

        live, dormant = [], []
        for mod in modules:
            meta = pitches.get(mod.name, {})
            entry = {
                'id': mod.id,
                'name': mod.name,
                'label': mod.shortdesc,
                'summary': mod.summary or '',
                'state': mod.state,
                'icon_url': f'/{mod.name}/static/description/icon.png',
                'accent': meta.get('accent', 'slate'),
                'glyph': meta.get('icon', 'fa-cube'),
                'pitch': meta.get('pitch', ''),
                'instrumented': mod.name in pitches,
            }
            (live if mod.state in ('installed', 'to upgrade') else dormant).append(entry)

        return {
            'installed': live,
            'dormant': dormant,
            'installed_count': len(live),
            'dormant_count': len(dormant),
            'coverage': round(100.0 * len(live) / (len(live) + len(dormant)), 1)
                        if (live or dormant) else 0.0,
        }

    @api.model
    def sgc_install_module(self, module_id):
        """One-click activation from a dormant tile (System Administrators only)."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only administrators can activate applications."))
        module = self.env['ir.module.module'].sudo().browse(int(module_id))
        if not module.exists():
            raise UserError(_("This application no longer exists."))
        module.button_immediate_install()
        return {'name': module.name, 'state': module.state}
