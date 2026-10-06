# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderCrmSales(models.AbstractModel):
    _name = 'sgc.provider.crm.sales'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: CRM & Sales'

    _sgc_module = 'crm'
    _sgc_label = 'CRM & Sales'
    _sgc_icon = 'fa-line-chart'
    _sgc_accent = 'teal'
    _sgc_sequence = 5
    _sgc_pitch = 'Forward-looking demand: pipeline value, win rate and confirmed revenue.'

    @api.model
    def _sgc_collect(self, ctx):
        kpis, charts = [], []
        # Assigned in the sale_management block below; declared up-front so the
        # CRM KPI list can reference it whether or not Sales is installed.
        quotations_sent = 0

        # ---- Pipeline (crm.lead) ----
        dom = [('type', '=', 'opportunity'), ('company_id', 'in', ctx['company_ids'])]
        open_dom = dom + [('active', '=', True)]
        pipeline = self._sgc_sum('crm.lead', open_dom, 'expected_revenue')
        won = self._sgc_count('crm.lead', dom + [('stage_id.is_won', '=', True),
                                                  ('date_closed', '>=', ctx['dt_from'])])
        lost = self._sgc_count('crm.lead', dom + [('active', '=', False), ('probability', '=', 0),
                                                   ('date_closed', '>=', ctx['dt_from'])])
        win_rate = (won / (won + lost) * 100.0) if (won + lost) else 0.0
        stages = self.env['crm.lead'].sudo()._read_group(
            open_dom, ['stage_id'], ['expected_revenue:sum'], order='stage_id asc')

        kpis += [
            self._sgc_kpi('crm_pipeline', _('Open Pipeline'), pipeline,
                          format='currency', icon='fa-filter', accent='teal'),
            self._sgc_kpi('crm_winrate', _('Win Rate'), win_rate,
                          format='percent', icon='fa-trophy', accent='amber'),
            self._sgc_kpi('crm_quotations', _('Quotations Sent'), quotations_sent,
                          icon='fa-file-text-o', accent='amber',
                          hint=_('Draft + sent sale orders this period')),
        ]
        if stages:
            charts.append({
                'key': 'crm_funnel', 'title': _('Pipeline by Stage'), 'subtitle': _('Expected revenue distribution'),
                'type': 'bar', 'span': 1, 'accent': 'teal',
                'labels': [s.display_name for s, _v in stages],
                'datasets': [{'label': _('Expected'), 'data': [round(v, 2) for _s, v in stages]}],
                'value_format': 'currency',
            })

        # ---- Sales (sale.order), only if sale_management is installed ----
        if self.env['ir.module.module'].sudo().search_count(
                [('name', '=', 'sale_management'), ('state', 'in', ('installed', 'to upgrade'))]):
            quotations_sent = self._sgc_count('sale.order',
                [('state', 'in', ('draft', 'sent')),
                 ('company_id', 'in', ctx['company_ids']),
                 ('date_order', '>=', ctx['dt_from'])])
            base = [('state', 'in', ('sale', 'done')), ('company_id', 'in', ctx['company_ids'])]
            cur = base + [('date_order', '>=', ctx['dt_from']), ('date_order', '<=', ctx['dt_to'])]
            prev_from, prev_to = self._sgc_previous_range(ctx)
            prev = base + [('date_order', '>=', prev_from), ('date_order', '<=', prev_to)]
            revenue = self._sgc_sum('sale.order', cur, 'amount_untaxed')
            revenue_prev = self._sgc_sum('sale.order', prev, 'amount_untaxed')
            trend = self._sgc_series('sale.order', cur, 'date_order', 'amount_untaxed', ctx)

            kpis.append(self._sgc_kpi('sale_revenue', _('Confirmed Revenue'), revenue,
                                      format='currency', icon='fa-money', span=2,
                                      delta=self._sgc_delta(revenue, revenue_prev),
                                      spark=trend['values'],
                                      action={'type': 'ir.actions.act_window', 'res_model': 'sale.order',
                                              'name': _('Confirmed Orders'), 'domain': cur,
                                              'views': [[False, 'list'], [False, 'form']]}))
            if trend['labels']:
                charts.append({
                    'key': 'sale_trend', 'title': _('Revenue Trajectory'), 'subtitle': _('Confirmed order value'),
                    'type': 'line', 'span': 2, 'accent': 'brand',
                    'labels': trend['labels'], 'datasets': [{'label': _('Revenue'), 'data': trend['values']}],
                    'value_format': 'currency',
                })

        return {'kpis': kpis, 'charts': charts}
