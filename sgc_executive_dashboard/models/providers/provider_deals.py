# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderDeals(models.AbstractModel):
    _name = 'sgc.provider.deals'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Deals Management'

    _sgc_module = 'sgc_deals_management'
    _sgc_label = 'Deals'
    _sgc_icon = 'fa-handshake-o'
    _sgc_accent = 'amber'
    _sgc_sequence = 3
    _sgc_pitch = 'Closed deal value, unit velocity and stage distribution across projects.'

    @api.model
    def _sgc_collect(self, ctx):
        # The "deal" fields (is_deal, deal_date, deal_sales_value, ...) are
        # added by sgc_deals_management onto sale.order, not realestate.unit.
        Order = self.env['sale.order'].sudo()
        deal_dom = [('is_deal', '=', True),
                    ('deal_date', '>=', ctx['date_from']), ('deal_date', '<=', ctx['date_to'])]
        deal_value = self._sgc_sum('sale.order', deal_dom, 'deal_sales_value')
        deal_count = self._sgc_count('sale.order', deal_dom)

        # Open (still-in-play) deal value: everything not yet confirmed or
        # cancelled. This is the forward-looking number the spec asks for,
        # distinct from the closed/won value above.
        open_dom = [('is_deal', '=', True), ('state', 'in', ('draft', 'sent'))]
        open_value = self._sgc_sum('sale.order', open_dom, 'deal_sales_value')
        open_count = self._sgc_count('sale.order', open_dom)

        # Stage conversion % = deals that reached a won/confirmed state as a
        # share of every deal that entered the funnel (won + open + lost).
        won_count = self._sgc_count('sale.order',
                                     [('is_deal', '=', True), ('state', 'in', ('sale', 'done'))])
        lost_count = self._sgc_count('sale.order',
                                      [('is_deal', '=', True), ('state', '=', 'cancel')])
        funnel_total = won_count + open_count + lost_count
        conversion_pct = (won_count / funnel_total * 100.0) if funnel_total else 0.0

        prev_from, prev_to = self._sgc_previous_range(ctx)
        prev_value = self._sgc_sum('sale.order', [
            ('is_deal', '=', True), ('deal_date', '>=', prev_from), ('deal_date', '<=', prev_to)],
            'deal_sales_value')

        # Avg deal cycle = avg days from order placed to the deal closing out.
        # `effective_date` only exists when sale_stock is installed, so fall
        # back to write_date on confirmed deals when it isn't there.
        end_field = 'effective_date' if 'effective_date' in Order._fields else 'write_date'
        closed_deals = Order.search(deal_dom + [('state', '=', 'sale')], limit=2000)
        cycle_days_list = []
        for d in closed_deals:
            start, end = d.date_order, d[end_field]
            if start and end and end >= start:
                cycle_days_list.append((end - start).days)
        avg_cycle_days = round(
            sum(cycle_days_list) / len(cycle_days_list), 1) if cycle_days_list else 0.0

        trend = self._sgc_series('sale.order', deal_dom, 'deal_date', 'deal_sales_value', ctx)

        # Use deal_stage_id if the module provides it, otherwise fall back to
        # state. Many SGC deal modules add a stage_id field — keep flexible.
        if 'deal_stage_id' in Order._fields:
            by_stage = Order._read_group([('is_deal', '=', True)], ['deal_stage_id'],
                                          ['__count'], order='__count desc', limit=8)
            stage_labels = [s.display_name if s else _('Unspecified') for s, _c in by_stage]
        else:
            by_stage = Order._read_group([('is_deal', '=', True)], ['state'],
                                          ['__count'], order='__count desc', limit=8)
            stage_labels = [s or _('Unspecified') for s, _c in by_stage]

        return {
            'kpis': [
                self._sgc_kpi('dl_value', _('Closed Deal Value'), deal_value,
                              format='currency', icon='fa-handshake-o', span=2,
                              delta=self._sgc_delta(deal_value, prev_value),
                              spark=trend['values'],
                              action={'type': 'ir.actions.act_window', 'res_model': 'sale.order',
                                      'name': _('Deals'), 'domain': deal_dom,
                                      'views': [[False, 'list'], [False, 'form']]}),
                self._sgc_kpi('dl_open_value', _('Open Deal Value'), open_value,
                              format='currency', icon='fa-folder-open-o', accent='teal',
                              hint=_('Draft and sent deals still in play')),
                self._sgc_kpi('dl_count', _('Deals Closed'), deal_count,
                              icon='fa-check-circle', accent='teal'),
                self._sgc_kpi('dl_conversion', _('Stage Conversion'), round(conversion_pct, 1),
                              format='percent', icon='fa-filter', accent='amber',
                              hint=_('Won deals / all deals that entered the funnel')),
                self._sgc_kpi('dl_cycle', _('Avg. Deal Cycle (days)'), avg_cycle_days,
                              format='duration', icon='fa-clock-o', accent='violet',
                              hint=_('Days from order placed to deal close')),
            ],
            'charts': [{
                'key': 'dl_trend', 'title': _('Deal Velocity'), 'subtitle': _('Closed value per month'),
                'type': 'line', 'span': 2, 'accent': 'amber',
                'labels': trend['labels'], 'datasets': [{'label': _('Deal Value'), 'data': trend['values']}],
                'value_format': 'currency',
            }, {
                'key': 'dl_by_stage', 'title': _('Deals by Stage'), 'subtitle': _('Distribution across the funnel'),
                'type': 'bar', 'span': 1, 'accent': 'amber',
                'labels': stage_labels,
                'datasets': [{'label': _('Deals'), 'data': [c for _s, c in by_stage]}],
                'value_format': 'number',
            }],
        }
