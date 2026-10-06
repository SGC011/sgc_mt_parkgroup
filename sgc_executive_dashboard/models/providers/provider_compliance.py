# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models
from dateutil.relativedelta import relativedelta


class SgcProviderCompliance(models.AbstractModel):
    _name = 'sgc.provider.compliance'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Compliance / KYC'

    _sgc_module = 'kyc_management'
    _sgc_label = 'Compliance'
    _sgc_icon = 'fa-id-card'
    _sgc_accent = 'rose'
    _sgc_sequence = 9
    _sgc_pitch = 'KYC completion, pending reviews and expiring identity documents.'

    @api.model
    def _sgc_collect(self, ctx):
        Application = self.env['kyc.application'].sudo()
        applications = Application.search([])
        total = len(applications)
        # is_kyc_complete is a computed, non-stored field — must be
        # filtered in Python, not via a search domain (not SQL-convertible).
        complete = len(applications.filtered('is_kyc_complete'))
        complete_pct = (complete / total * 100.0) if total else 0.0
        # "Pending reviews" — anything not yet complete and not in a terminal
        # rejected/withdrawn state (those are finished, not pending).
        pending_reviews = len([a for a in applications
                                if not a.is_kyc_complete and a.state not in ('rejected', 'withdrawn')])

        today = ctx['date_to']
        expiring = self._sgc_count('kyc.application', [
            '|',
            '&', ('passport_expiry_date', '>=', today),
                 ('passport_expiry_date', '<=', today + relativedelta(days=30)),
            '&', ('residency_expiry_date', '>=', today),
                 ('residency_expiry_date', '<=', today + relativedelta(days=30)),
        ])

        by_state = Application._read_group([], ['state'], ['__count'], order='__count desc', limit=8)

        return {
            'kpis': [
                self._sgc_kpi('kyc_complete', _('KYC Complete'), round(complete_pct, 1),
                              format='percent', icon='fa-id-card', accent='rose'),
                self._sgc_kpi('kyc_pending', _('Pending Reviews'), pending_reviews,
                              icon='fa-hourglass-half', accent='amber',
                              hint=_('Applications awaiting review/approval')),
                self._sgc_kpi('kyc_expiring', _('Documents Expiring (30d)'), expiring,
                              icon='fa-calendar-times-o', accent='amber'),
                self._sgc_kpi('kyc_total', _('KYC Applications'), total,
                              icon='fa-folder-open', accent='slate',
                              action={'type': 'ir.actions.act_window', 'res_model': 'kyc.application',
                                      'name': _('KYC Applications'), 'domain': [],
                                      'views': [[False, 'list'], [False, 'form']]}),
            ],
            # Only emit the chart when there is something to plot — an empty
            # canvas reads as a broken widget rather than an empty dataset.
            'charts': [{
                'key': 'kyc_by_state', 'title': _('KYC Pipeline'), 'subtitle': _('Applications by status'),
                'type': 'bar', 'span': 1, 'accent': 'rose',
                'labels': [s or _('Unspecified') for s, _c in by_state],
                'datasets': [{'label': _('Applications'), 'data': [c for _s, c in by_state]}],
                'value_format': 'number',
            }] if by_state else [],
        }
