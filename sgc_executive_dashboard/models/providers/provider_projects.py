# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderProjects(models.AbstractModel):
    _name = 'sgc.provider.projects'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Delivery'

    _sgc_module = 'project'
    _sgc_label = 'Delivery'
    _sgc_icon = 'fa-tasks'
    _sgc_accent = 'brand'
    _sgc_sequence = 10
    _sgc_pitch = 'Execution health: open workload, overdue tasks and throughput.'

    @api.model
    def _sgc_collect(self, ctx):
        dom = [('company_id', 'in', ctx['company_ids'])]
        open_tasks = self._sgc_count('project.task', dom + [('state', 'in',
                                     ('01_in_progress', '02_changes_requested', '03_approved'))])
        overdue = self._sgc_count('project.task', dom + [('date_deadline', '<', ctx['date_to'])])
        active_projects = self._sgc_count('project.project', dom + [('active', '=', True)])
        # Task completion % over the selected period (closed tasks / total).
        period_dom = dom + [('date_deadline', '>=', ctx['date_from']),
                            ('date_deadline', '<=', ctx['date_to'])]
        closed_period = self._sgc_count('project.task',
                                         period_dom + [('state', 'in', ('1_done', 'done'))])
        total_period = self._sgc_count('project.task', period_dom)
        completion_pct = (closed_period / total_period * 100.0) if total_period else 0.0
        # Burndown: open tasks at end of each month over the range.
        burn_trend = self._sgc_series('project.task',
                                       dom + [('state', 'in',
                                               ('01_in_progress', '02_changes_requested',
                                                '03_approved', '1_done', 'done'))],
                                       'date_deadline', None, ctx)
        return {
            'kpis': [
                self._sgc_kpi('prj_active', _('Active Projects'), active_projects,
                              icon='fa-folder-open'),
                self._sgc_kpi('prj_open', _('Active Tasks'), open_tasks, icon='fa-tasks'),
                self._sgc_kpi('prj_completion', _('Task Completion'), round(completion_pct, 1),
                              format='percent', icon='fa-check-square-o', accent='teal',
                              hint=_('Closed tasks this period vs. total')),
                self._sgc_kpi('prj_late', _('Past Deadline'), overdue,
                              icon='fa-calendar-times-o', accent='rose'),
            ],
            'charts': [{
                'key': 'prj_burndown', 'title': _('Task Burndown'),
                'subtitle': _('Open tasks per month'),
                'type': 'line', 'span': 2, 'accent': 'brand',
                'labels': burn_trend['labels'],
                'datasets': [{'label': _('Open Tasks'), 'data': burn_trend['values']}],
                'value_format': 'number',
            }] if burn_trend['labels'] else [],
        }
