# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, fields, models


class SgcProviderConstruction(models.AbstractModel):
    _name = 'sgc.provider.construction'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Construction Management'

    _sgc_module = 'sgc_construction_management'
    _sgc_label = 'Construction'
    _sgc_icon = 'fa-wrench'
    _sgc_accent = 'slate'
    _sgc_sequence = 2
    _sgc_pitch = 'Project progress, budget burn and site risk in one command view.'

    @api.model
    def _sgc_collect(self, ctx):
        Project = self.env['construction.project'].sudo()
        WBS = self.env['construction.wbs'].sudo()
        projects = Project.search([])
        total_projects = len(projects)

        # progress/planned_progress are computed, non-stored fields on
        # construction.project — must be read per-record, not via SQL
        # _read_group aggregation (which only supports stored fields).
        progress_vals = projects.mapped('progress')
        planned_vals = projects.mapped('planned_progress')
        progress_avg = (sum(progress_vals) / len(progress_vals)) if progress_vals else 0.0
        planned_avg = (sum(planned_vals) / len(planned_vals)) if planned_vals else 0.0

        agg = Project._read_group([], [], ['budget_consumed:avg', 'margin_percent:avg'])
        budget_avg, margin_avg = (agg[0] if agg else (0, 0))

        contract_value = self._sgc_sum('construction.project', [], 'contract_value')
        total_billed = self._sgc_sum('construction.project', [], 'total_billed')
        open_ncr = sum(Project.search([]).mapped('open_ncr_count'))

        # On-time milestone % + overdue count: a WBS line whose planned_end
        # has passed and progress<100 is overdue; one already complete
        # (progress>=100) by its planned_end is on time.
        all_wbs = WBS.search([])
        today = fields.Date.context_today(self)
        overdue_milestones = len([w for w in all_wbs
                                   if w.planned_end and w.planned_end < today
                                   and (w.progress or 0.0) < 100.0])
        completed_on_time = len([w for w in all_wbs
                                  if w.planned_end and w.planned_end < today
                                  and (w.progress or 0.0) >= 100.0])
        due_past = overdue_milestones + completed_on_time
        on_time_pct = (completed_on_time / due_past * 100.0) if due_past else 0.0
        # Milestone status stacked-bar data: bucket WBS by progress state.
        not_started = len([w for w in all_wbs if (w.progress or 0.0) == 0.0])
        in_progress = len([w for w in all_wbs if 0.0 < (w.progress or 0.0) < 100.0])
        complete = len([w for w in all_wbs if (w.progress or 0.0) >= 100.0])

        # Budget burn: actual WBS cost booked per month across the window.
        burn = self._sgc_series('construction.wbs',
                                 [('actual_end', '>=', ctx['date_from']),
                                  ('actual_end', '<=', ctx['date_to'])],
                                 'actual_end', 'actual_cost', ctx)

        top = Project._read_group([], ['name'], ['total_billed:sum', 'total_expenses:sum'],
                                   order='total_billed:sum desc', limit=8)

        return {
            'kpis': [
                self._sgc_kpi('cn_projects', _('Active Projects'), total_projects,
                              icon='fa-wrench',
                              action={'type': 'ir.actions.act_window', 'res_model': 'construction.project',
                                      'name': _('Construction Projects'), 'domain': [],
                                      'views': [[False, 'list'], [False, 'form']]}),
                self._sgc_kpi('cn_progress', _('Avg. Progress vs Plan'), round(progress_avg or 0.0, 1),
                              format='percent', icon='fa-tasks', accent='teal',
                              hint=_("Planned: %s%%") % round(planned_avg or 0.0, 1)),
                self._sgc_kpi('cn_on_time', _('On-Time Milestones'), round(on_time_pct, 1),
                              format='percent', icon='fa-check-square-o', accent='teal',
                              hint=_('Completed by planned date / all milestones due in the past')),
                self._sgc_kpi('cn_overdue', _('Overdue Milestones'), overdue_milestones,
                              icon='fa-calendar-times-o', accent='rose'),
                self._sgc_kpi('cn_budget', _('Avg. Budget Consumed'), round(budget_avg or 0.0, 1),
                              format='percent', icon='fa-pie-chart', accent='amber'),
                self._sgc_kpi('cn_contract_value', _('Contract Value'), contract_value,
                              format='currency', icon='fa-file-text', span=2),
                self._sgc_kpi('cn_ncr', _('Open Site Issues (NCR)'), open_ncr,
                              icon='fa-exclamation-triangle', accent='rose'),
            ],
            'charts': ([{
                'key': 'cn_budget_burn', 'title': _('Budget Burn'),
                'subtitle': _('Actual cost booked per month'),
                'type': 'line', 'span': 2, 'accent': 'amber',
                'labels': burn['labels'],
                'datasets': [{'label': _('Actual Cost'), 'data': burn['values']}],
                'value_format': 'currency',
            }] if burn['labels'] else []) + [{
                'key': 'cn_milestone_status', 'title': _('Milestone Status'),
                'subtitle': _('WBS lines by progress bucket'),
                'type': 'bar', 'stacked': True, 'span': 1, 'accent': 'brand',
                'labels': [_('Milestones')],
                'datasets': [
                    {'label': _('Not Started'), 'data': [not_started]},
                    {'label': _('In Progress'), 'data': [in_progress]},
                    {'label': _('Complete'), 'data': [complete]},
                ],
                'value_format': 'number',
            }, {
                'key': 'cn_billed_vs_expense', 'title': _('Billing vs Spend'),
                'subtitle': _('Top projects by billed value'), 'type': 'bar', 'horizontal': True,
                'span': 1, 'accent': 'slate',
                'labels': [n for n, _b, _e in top],
                'datasets': [
                    {'label': _('Billed'), 'data': [round(b or 0.0, 2) for _n, b, _e in top]},
                    {'label': _('Expenses'), 'data': [round(e or 0.0, 2) for _n, _b, e in top]},
                ],
                'value_format': 'currency',
            }],
        }
