# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderPurchase(models.AbstractModel):
    _name = 'sgc.provider.purchase'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Procurement'

    _sgc_module = 'purchase'
    _sgc_label = 'Procurement'
    _sgc_icon = 'fa-truck'
    _sgc_accent = 'slate'
    _sgc_sequence = 6
    _sgc_pitch = 'Spend control and commitment visibility across every purchase order.'

    @api.model
    def _sgc_collect(self, ctx):
        dom = [('state', 'in', ('purchase', 'done')), ('company_id', 'in', ctx['company_ids']),
               ('date_approve', '>=', ctx['dt_from']), ('date_approve', '<=', ctx['dt_to'])]
        spend = self._sgc_sum('purchase.order', dom, 'amount_untaxed')
        trend = self._sgc_series('purchase.order', dom, 'date_approve', 'amount_untaxed', ctx)
        pending = self._sgc_sum('purchase.order',
                                [('state', 'in', ('draft', 'sent', 'to approve')),
                                 ('company_id', 'in', ctx['company_ids'])], 'amount_untaxed')
        # Avg PO cycle time = avg days from RFQ create -> PO confirm.
        recent_pos = self.env['purchase.order'].sudo().search(
            [('state', 'in', ('purchase', 'done')), ('company_id', 'in', ctx['company_ids']),
             ('date_approve', '>=', ctx['dt_from']),
             ('date_approve', '<=', ctx['dt_to'])], limit=2000)
        cycle_days = []
        for p in recent_pos:
            if p.date_order and p.date_approve and p.date_approve >= p.date_order:
                cycle_days.append((p.date_approve - p.date_order).days)
        avg_cycle_days = (sum(cycle_days) / len(cycle_days)) if cycle_days else 0.0
        return {
            'kpis': [
                self._sgc_kpi('pur_spend', _('Committed Spend'), spend, format='currency',
                              icon='fa-truck', accent='slate', spark=trend['values']),
                self._sgc_kpi('pur_open', _('Open Purchase Orders'),
                              self._sgc_count('purchase.order',
                                               [('state', 'in', ('draft', 'sent', 'to approve',
                                                                   'purchase', 'done'))]),
                              icon='fa-file-text-o', accent='teal'),
                self._sgc_kpi('pur_pending', _('Awaiting Approval'), pending,
                              format='currency', icon='fa-clock-o', accent='amber'),
                self._sgc_kpi('pur_cycle', _('Avg. PO Cycle (days)'), round(avg_cycle_days, 1),
                              format='duration', icon='fa-clock-o', accent='violet',
                              hint=_('Days from RFQ to PO confirmation')),
            ],
            'charts': [{
                'key': 'pur_trend', 'title': _('Spend Trajectory'),
                'subtitle': _('Committed spend per month'), 'type': 'line', 'span': 2, 'accent': 'slate',
                'labels': trend['labels'],
                'datasets': [{'label': _('Spend'), 'data': trend['values']}],
                'value_format': 'currency',
            }],
        }
