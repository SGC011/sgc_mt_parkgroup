# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, fields, models
from dateutil.relativedelta import relativedelta


class SgcProviderFinance(models.AbstractModel):
    _name = 'sgc.provider.finance'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Finance'

    _sgc_module = 'account'
    _sgc_label = 'Finance'
    _sgc_icon = 'fa-university'
    _sgc_accent = 'violet'
    _sgc_sequence = 7
    _sgc_pitch = 'Cash position, receivables ageing, AML exposure and e-invoice compliance.'

    @api.model
    def _sgc_collect(self, ctx):
        today = fields.Date.context_today(self)
        company = [('company_id', 'in', ctx['company_ids']), ('state', '=', 'posted')]

        inv = company + [('move_type', '=', 'out_invoice'),
                         ('invoice_date', '>=', ctx['date_from']), ('invoice_date', '<=', ctx['date_to'])]
        bills = company + [('move_type', '=', 'in_invoice'),
                           ('invoice_date', '>=', ctx['date_from']), ('invoice_date', '<=', ctx['date_to'])]
        invoiced = self._sgc_sum('account.move', inv, 'amount_untaxed_signed')
        billed = self._sgc_sum('account.move', bills, 'amount_untaxed_signed')
        margin = invoiced - abs(billed)
        margin_pct = (margin / invoiced * 100.0) if invoiced else 0.0

        ar_domain = company + [('move_type', '=', 'out_invoice'),
                               ('payment_state', 'in', ('not_paid', 'partial'))]
        receivable = self._sgc_sum('account.move', ar_domain, 'amount_residual_signed')
        overdue = self._sgc_sum('account.move', ar_domain + [('invoice_date_due', '<', today)],
                                'amount_residual_signed')

        trend = self._sgc_series('account.move', inv, 'invoice_date', 'amount_untaxed_signed', ctx)
        buckets = self._sgc_ageing(ar_domain, today)

        kpis = [
            self._sgc_kpi('fin_invoiced', _('Invoiced'), invoiced, format='currency',
                          icon='fa-file-text', accent='violet', spark=trend['values']),
            self._sgc_kpi('fin_margin', _('Gross Margin'), round(margin_pct, 1), format='percent',
                          icon='fa-percent', accent='teal',
                          hint=_('Customer invoices less vendor bills, untaxed')),
            self._sgc_kpi('fin_ar', _('Receivables'), receivable, format='currency',
                          icon='fa-hourglass-half', accent='amber'),
            self._sgc_kpi('fin_overdue', _('Overdue'), overdue, format='currency',
                          icon='fa-exclamation-triangle', accent='rose',
                          hint=_('Past due date and unpaid'),
                          action={'type': 'ir.actions.act_window', 'res_model': 'account.move',
                                  'name': _('Overdue Invoices'),
                                  'domain': ar_domain + [('invoice_date_due', '<', today)],
                                  'views': [[False, 'list'], [False, 'form']]}),
            # Absolute net-profit figure (margin_pct was the % version already).
            self._sgc_kpi('fin_net_profit', _('Net Profit (Gross)'), round(margin, 2),
                          format='currency', icon='fa-line-chart', accent='violet',
                          hint=_('Customer invoiced minus vendor bills, untaxed')),
        ]
        # Cash position: positive cash + bank journal balances (account.type
        # 'cash'/'bank' on journal entries, summed in the period window).
        cash_position = self._sgc_sum('account.move',
            company + [('journal_id.type', 'in', ('cash', 'bank')),
                       ('state', '=', 'posted'),
                       ('date', '<=', today)],
            'amount_total_signed')
        kpis.append(self._sgc_kpi('fin_cash', _('Cash Position'), cash_position,
                                 format='currency', icon='fa-money', accent='teal',
                                 hint=_('Cash + bank journals, cumulative up to today')))
        charts = [{
            'key': 'fin_trend', 'title': _('P&L Trajectory'),
            'subtitle': _('Customer invoiced per month'), 'type': 'line', 'span': 2, 'accent': 'violet',
            'labels': trend['labels'],
            'datasets': [{'label': _('Invoiced'), 'data': trend['values']}],
            'value_format': 'currency',
        }, {
            'key': 'fin_ageing', 'title': _('Receivables Ageing'),
            'subtitle': _('Outstanding balance by bucket'),
            'type': 'bar', 'span': 1, 'accent': 'violet',
            'labels': list(buckets.keys()),
            'datasets': [{'label': _('Outstanding'), 'data': list(buckets.values())}],
            'value_format': 'currency',
        }]

        # AML compliance signal (aml_compliance), only if installed AND the
        # model is actually registered — some environments have the module
        # row marked 'installed' while a model failed to load (partial
        # removal/rename); never let that take down the whole Finance
        # section for the sake of one optional KPI.
        if (self.env['ir.module.module'].sudo().search_count(
                [('name', '=', 'aml_compliance'), ('state', 'in', ('installed', 'to upgrade'))])
                and 'aml.transaction.alert' in self.env.registry.models):
            open_alerts = self._sgc_count('aml.transaction.alert', [])
            kpis.append(self._sgc_kpi('fin_aml_alerts', _('Open AML Alerts'), open_alerts,
                                      icon='fa-shield', accent='rose',
                                      hint=_('Unresolved transaction monitoring alerts')))

        # UAE e-invoicing compliance signal (uae_einvoice_core), only if installed.
        if self.env['ir.module.module'].sudo().search_count(
                [('name', '=', 'uae_einvoice_core'), ('state', 'in', ('installed', 'to upgrade'))]):
            einvoiced = self._sgc_count('account.move', inv + [('einvoice_state', '!=', False)])
            rate = (einvoiced / len(self.env['account.move'].sudo().search(inv)) * 100.0
                    if self._sgc_count('account.move', inv) else 0.0)
            kpis.append(self._sgc_kpi('fin_einvoice', _('E-Invoice Compliance'), round(rate, 1),
                                      format='percent', icon='fa-certificate', accent='teal',
                                      hint=_('Customer invoices with an e-invoice submission state')))

        return {'kpis': kpis, 'charts': charts}

    @api.model
    def _sgc_ageing(self, domain, today):
        edges = [('Current', None, today),
                 ('1-30 days', today - relativedelta(days=30), today),
                 ('31-60 days', today - relativedelta(days=60), today - relativedelta(days=31)),
                 ('61-90 days', today - relativedelta(days=90), today - relativedelta(days=61)),
                 ('90+ days', None, today - relativedelta(days=91))]
        out = {'Current': self._sgc_sum(
            'account.move', domain + [('invoice_date_due', '>=', today)], 'amount_residual_signed')}
        for label, start, end in edges[1:]:
            dom = list(domain)
            if start:
                dom.append(('invoice_date_due', '>=', start))
            dom.append(('invoice_date_due', '<=', end))
            out[label] = round(self._sgc_sum('account.move', dom, 'amount_residual_signed'), 2)
        return out
