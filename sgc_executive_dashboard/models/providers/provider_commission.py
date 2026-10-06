# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderCommission(models.AbstractModel):
    _name = 'sgc.provider.commission'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Commission'

    _sgc_module = 'sgc_commission'
    _sgc_label = 'Commission'
    _sgc_icon = 'fa-percent'
    _sgc_accent = 'violet'
    _sgc_sequence = 4
    _sgc_pitch = 'Commission liability and payout status across the agent network.'

    @api.model
    def _sgc_collect(self, ctx):
        Line = self.env['commission.line'].sudo()
        liability = self._sgc_sum('commission.line', [], 'base_amount')

        by_state = Line._read_group([], ['state'], ['base_amount:sum'],
                                     order='base_amount:sum desc', limit=8)
        # Top 5 earning agents (best-effort: group by partner_id on commission.line
        # if present, otherwise fall back to user_id).
        groupby = 'partner_id' if 'partner_id' in Line._fields else 'user_id'
        top_agents = Line._read_group([], [groupby], ['base_amount:sum'],
                                       order='base_amount:sum desc', limit=5)

        return {
            'kpis': [
                self._sgc_kpi('cm_liability', _('Commission Liability'), liability,
                              format='currency', icon='fa-percent', span=2,
                              action={'type': 'ir.actions.act_window', 'res_model': 'commission.line',
                                      'name': _('Commission Lines'), 'domain': [],
                                      'views': [[False, 'list'], [False, 'form']]}),
                self._sgc_kpi('cm_lines', _('Commission Lines'), self._sgc_count('commission.line', []),
                              icon='fa-list', accent='slate'),
                self._sgc_kpi('cm_top_agents', _('Top Earning Agents'),
                              min(len(top_agents), 5),
                              icon='fa-user-tie', accent='violet',
                              hint=_('Top 5 by base commission amount')),
            ],
            'charts': [{
                'key': 'cm_by_state', 'title': _('Commission by Status'),
                'subtitle': _('Base amount grouped by payout state'), 'type': 'doughnut',
                'span': 1, 'accent': 'violet',
                'labels': [s or _('Unspecified') for s, _v in by_state],
                'datasets': [{'label': _('Amount'), 'data': [round(v or 0.0, 2) for _s, v in by_state]}],
                'value_format': 'currency',
            }, {
                'key': 'cm_top_agents', 'title': _('Top Earning Agents'),
                'subtitle': _('Top 5 by commission base'),
                'type': 'bar', 'horizontal': True, 'span': 1, 'accent': 'violet',
                'labels': [p.display_name if p else _('Unspecified') for p, _v in top_agents],
                'datasets': [{'label': _('Commission'),
                              'data': [round(v or 0.0, 2) for _p, v in top_agents]}],
                'value_format': 'currency',
            }],
        }
