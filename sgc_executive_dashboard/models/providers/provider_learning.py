# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderLearning(models.AbstractModel):
    _name = 'sgc.provider.learning'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Learning & Assessment'

    _sgc_module = 'sgc_elearning'
    _sgc_label = 'Learning'
    _sgc_icon = 'fa-graduation-cap'
    _sgc_accent = 'teal'
    _sgc_sequence = 11
    _sgc_pitch = 'Course completion, certifications issued and assessment quality.'

    @api.model
    def _sgc_collect(self, ctx):
        kpis, charts = [], []

        total_progress = self._sgc_count('learning.progress', [])
        completed = self._sgc_count('learning.progress', [('completed', '=', True)])
        completion_pct = (completed / total_progress * 100.0) if total_progress else 0.0
        trend = self._sgc_series('learning.progress',
                                 [('completed', '=', True), ('last_access_date', '>=', ctx['dt_from']),
                                  ('last_access_date', '<=', ctx['dt_to'])],
                                 'last_access_date', None, ctx)

        kpis.append(self._sgc_kpi('lrn_completion', _('Course Completion'),
                                  round(completion_pct, 1),
                                  format='percent', icon='fa-graduation-cap', accent='teal',
                                  spark=trend['values']))

        certs_issued = self._sgc_count('learning.certificate', [
            ('is_valid', '=', True), ('completion_date', '>=', ctx['dt_from']),
            ('completion_date', '<=', ctx['dt_to'])])
        kpis.append(self._sgc_kpi('lrn_certs', _('Certifications Issued'), certs_issued,
                                  icon='fa-certificate', accent='amber'))

        if self.env['ir.module.module'].sudo().search_count(
                [('name', '=', 'sgc_assessment'), ('state', 'in', ('installed', 'to upgrade'))]):
            avg = self.env['assessment.candidate'].sudo()._read_group(
                [], [], ['overall_score:avg'])
            avg_score = (avg[0][0] if avg else 0.0) or 0.0
            kpis.append(self._sgc_kpi('lrn_assess_avg', _('Avg. Assessment Score'),
                                      round(avg_score, 1),
                                      icon='fa-check-square-o', accent='violet'))

        if trend['labels']:
            charts.append({
                'key': 'lrn_completion_trend', 'title': _('Learning Momentum'),
                'subtitle': _('Completions per month'), 'type': 'line', 'span': 2, 'accent': 'teal',
                'labels': trend['labels'],
                'datasets': [{'label': _('Completions'), 'data': trend['values']}],
                'value_format': 'number',
            })

        return {'kpis': kpis, 'charts': charts}
