# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models
from dateutil.relativedelta import relativedelta


class SgcProviderRealEstate(models.AbstractModel):
    _name = 'sgc.provider.realestate'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Real Estate / Offplan Rental'

    _sgc_module = 'sgc_offplan_rental_property_management'
    _sgc_label = 'Real Estate'
    _sgc_icon = 'fa-building'
    _sgc_accent = 'brand'
    _sgc_sequence = 1
    _sgc_pitch = 'Units under management, offplan sales value and lease coverage in one view.'

    @api.model
    def _sgc_collect(self, ctx):
        units = self._sgc_count('property.details', [('active', '=', True)])

        sale_dom = [('contract_date', '>=', ctx['date_from']),
                    ('contract_date', '<=', ctx['date_to'])]
        sales_value = self._sgc_sum('sale.contract', sale_dom, 'sale_price')
        prev_from, prev_to = self._sgc_previous_range(ctx)
        sales_value_prev = self._sgc_sum('sale.contract', [
            ('contract_date', '>=', prev_from), ('contract_date', '<=', prev_to)], 'sale_price')
        trend = self._sgc_series('sale.contract', sale_dom, 'contract_date', 'sale_price', ctx)

        active_leases = self._sgc_count('tenancy.details', [
            ('start_date', '<=', ctx['date_to']), ('end_date', '>=', ctx['date_from'])])
        # Occupancy = active leases / total active units (any unit under
        # active management). Cap at 100% defensively.
        occupancy_pct = (active_leases / units * 100.0) if units else 0.0
        occupancy_pct = min(occupancy_pct, 100.0)
        # Occupancy trend: active leases counted at the end of each month
        # over the window.
        occupancy_trend = self._sgc_series(
            'tenancy.details',
            [('state', 'not in', ('cancelled', 'expired', 'terminated'))],
            'start_date', None, ctx)

        expiring_soon = self._sgc_count('tenancy.details', [
            ('end_date', '>=', ctx['date_to']),
            ('end_date', '<=', ctx['date_to'] + relativedelta(days=30))])

        rent_dom = [('invoice_date', '>=', ctx['date_from']), ('invoice_date', '<=', ctx['date_to'])]
        rent_collected = self._sgc_sum('rent.invoice', rent_dom, 'amount')

        by_type = self.env['property.details'].sudo()._read_group(
            [('active', '=', True)], ['property_type'], ['__count'], order='__count desc', limit=8)

        # Sales by project: sale.contract links to a property, so group the
        # period's contract value by the property it was sold against.
        by_project = self.env['sale.contract'].sudo()._read_group(
            sale_dom, ['property_id'], ['sale_price:sum'],
            order='sale_price:sum desc', limit=8)

        return {
            'kpis': [
                self._sgc_kpi('re_units', _('Units Under Management'), units,
                              icon='fa-building', span=1,
                              action={'type': 'ir.actions.act_window', 'res_model': 'property.details',
                                      'name': _('Properties'), 'domain': [('active', '=', True)],
                                      'views': [[False, 'list'], [False, 'form']]}),
                self._sgc_kpi('re_occupancy', _('Occupancy'), round(occupancy_pct, 1),
                              format='percent', icon='fa-home', accent='teal',
                              hint=_('Active leases / active units')),
                self._sgc_kpi('re_sales_value', _('Offplan Sales Value'), sales_value,
                              format='currency', icon='fa-handshake-o', span=2,
                              delta=self._sgc_delta(sales_value, sales_value_prev),
                              spark=trend['values'],
                              action={'type': 'ir.actions.act_window', 'res_model': 'sale.contract',
                                      'name': _('Sale Contracts'), 'domain': sale_dom,
                                      'views': [[False, 'list'], [False, 'form']]}),
                self._sgc_kpi('re_leases', _('Active Leases'), active_leases,
                              icon='fa-key', accent='teal'),
                self._sgc_kpi('re_expiring', _('Lease Expiries (30d)'), expiring_soon,
                              icon='fa-calendar-times-o', accent='amber',
                              hint=_('Tenancies ending within the next 30 days')),
                self._sgc_kpi('re_rent', _('Rent Invoiced'), rent_collected,
                              format='currency', icon='fa-file-text-o', accent='violet'),
            ],
            'charts': [{
                'key': 're_occupancy_trend', 'title': _('Occupancy Trend'),
                'subtitle': _('New active leases per month'),
                'type': 'line', 'span': 2, 'accent': 'teal',
                'labels': occupancy_trend['labels'],
                'datasets': [{'label': _('New Leases'), 'data': occupancy_trend['values']}],
                'value_format': 'number',
            }, {
                'key': 're_sales_trend', 'title': _('Offplan Sales Trajectory'),
                'subtitle': _('Contract value per month'), 'type': 'line', 'span': 2, 'accent': 'brand',
                'labels': trend['labels'],
                'datasets': [{'label': _('Sales'), 'data': trend['values']}],
                'value_format': 'currency',
            }, {
                'key': 're_sales_by_project', 'title': _('Sales by Project'),
                'subtitle': _('Contract value by property'),
                'type': 'bar', 'horizontal': True, 'span': 1, 'accent': 'brand',
                'labels': [p.display_name if p else _('Unassigned') for p, _v in by_project],
                'datasets': [{'label': _('Sales'),
                              'data': [round(v or 0.0, 2) for _p, v in by_project]}],
                'value_format': 'currency',
            }, {
                'key': 're_units_by_type', 'title': _('Portfolio Mix'), 'subtitle': _('Units by property type'),
                'type': 'polarArea', 'span': 1, 'accent': 'teal',
                'labels': [t or _('Unspecified') for t, _c in by_type],
                'datasets': [{'label': _('Units'), 'data': [c for _t, c in by_type]}],
                'value_format': 'number',
            }],
        }
