# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderHrPayroll(models.AbstractModel):
    _name = 'sgc.provider.hr.payroll'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: HR & UAE Payroll'

    _sgc_module = 'hr'
    _sgc_label = 'People'
    _sgc_icon = 'fa-users'
    _sgc_accent = 'rose'
    _sgc_sequence = 8
    _sgc_pitch = 'Headcount, payroll run status, attendance and open recruitment in one view.'

    @api.model
    def _sgc_collect(self, ctx):
        dom = [('company_id', 'in', ctx['company_ids'])]
        headcount = self._sgc_count('hr.employee', dom)
        depts = self.env['hr.employee'].sudo()._read_group(
            dom, ['department_id'], ['__count'], order='__count desc', limit=8)

        kpis = [self._sgc_kpi('hr_headcount', _('Headcount'), headcount, icon='fa-users', accent='rose')]
        # Headcount trend line (the spec required time-series, not just a snapshot).
        trend = self._sgc_series('hr.employee', dom, 'create_date', None, ctx)
        charts = [{
            'key': 'hr_headcount_trend', 'title': _('Headcount Trend'),
            'subtitle': _('New hires per month'), 'type': 'line', 'span': 2, 'accent': 'rose',
            'labels': trend['labels'],
            'datasets': [{'label': _('Hires'), 'data': trend['values']}],
            'value_format': 'number',
        }, {
            'key': 'hr_dept', 'title': _('Organisational Shape'), 'subtitle': _('Headcount by department'),
            'type': 'polarArea', 'span': 1, 'accent': 'rose',
            'labels': [d.display_name if d else _('Unassigned') for d, _c in depts],
            'datasets': [{'label': _('Employees'), 'data': [c for _d, c in depts]}],
            'value_format': 'number',
        }]

        Module = self.env['ir.module.module'].sudo()

        if Module.search_count([('name', '=', 'hr_attendance'), ('state', 'in', ('installed', 'to upgrade'))]):
            present_today = self._sgc_count('hr.attendance', [('check_out', '=', False)])
            attendance_pct = (present_today / headcount * 100.0) if headcount else 0.0
            kpis.append(self._sgc_kpi('hr_attendance_rate', _('Attendance Rate'),
                                      round(attendance_pct, 1), format='percent',
                                      icon='fa-clock-o', accent='teal',
                                      hint=_('Currently checked-in as %s%% of headcount') %
                                            round(attendance_pct, 1)))

        if Module.search_count([('name', '=', 'hr_holidays'), ('state', 'in', ('installed', 'to upgrade'))]):
            open_leave = self._sgc_count('hr.leave', [('state', 'in', ('confirm', 'validate1'))])
            kpis.append(self._sgc_kpi('hr_leave', _('Pending Leave Requests'), open_leave,
                                      icon='fa-calendar', accent='amber'))

        if Module.search_count([('name', '=', 'hr_recruitment'), ('state', 'in', ('installed', 'to upgrade'))]):
            open_jobs = self._sgc_count('hr.job', [('company_id', 'in', ctx['company_ids']),
                                                    ('no_of_recruitment', '>', 0)])
            kpis.append(self._sgc_kpi('hr_open_reqs', _('Open Requisitions'), open_jobs,
                                      icon='fa-user-plus', accent='violet'))

        if Module.search_count([('name', '=', 'hr_payroll_community'),
                                 ('state', 'in', ('installed', 'to upgrade'))]):
            run_dom = [('date_from', '>=', ctx['date_from']), ('date_to', '<=', ctx['date_to'])]
            done_payslips = self._sgc_count('hr.payslip', run_dom + [('state', '=', 'done')])
            total_payslips = self._sgc_count('hr.payslip', run_dom)
            wps_pct = (done_payslips / total_payslips * 100.0) if total_payslips else 0.0
            kpis.append(self._sgc_kpi('hr_payroll_status', _('Payroll Runs Completed'),
                                      round(wps_pct, 1),
                                      format='percent', icon='fa-money', accent='brand',
                                      hint=_('Finalised payslips this period vs. total')))
        # WPS Compliance % — the UAE Wage Protection System requires every paid
        # employee to carry a WPS person code and an IBAN before a SIF file can
        # be generated. eh_uae_payroll_wps adds exactly those fields to
        # hr.employee, so payroll-file readiness is the honest measure here
        # (the module ships no compliance-summary model of its own).
        if (Module.search_count([('name', '=', 'eh_uae_payroll_wps'),
                                 ('state', 'in', ('installed', 'to upgrade'))])
                and {'wps_employee_id', 'wps_iban'} <= set(self.env['hr.employee']._fields)):
            staff = self.env['hr.employee'].sudo().search(dom)
            wps_ready = len(staff.filtered(lambda e: e.wps_employee_id and e.wps_iban))
            wps_ready_pct = (wps_ready / len(staff) * 100.0) if staff else 0.0
            kpis.append(self._sgc_kpi('hr_wps_compliance', _('WPS Compliance'),
                                      round(wps_ready_pct, 1),
                                      format='percent', icon='fa-shield',
                                      accent='teal' if wps_ready_pct >= 100.0 else 'rose',
                                      hint=_('Employees with a WPS person code and IBAN '
                                             'on file — required to generate the SIF')))

        return {'kpis': kpis, 'charts': charts}
