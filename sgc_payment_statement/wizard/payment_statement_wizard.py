import logging
import re
from collections import defaultdict

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

LEGACY_NAME = re.compile(r'Old Name:\s*(\S+)')
# the account a bank or cash journal is booked on: anything else is a journal set up on the wrong account
LIQUIDITY_TYPES = ('asset_cash', 'asset_current', 'liability_credit_card')

BUCKETS = [
    ('eligible', 'To generate'),
    ('draft', 'Left out: payment still in draft'),
    ('duplicate', 'Left out: looks like a payment migrated twice'),
    ('bad_journal', 'Left out: journal booked on a non-bank account'),
    ('foreign', 'Left out: payment in a foreign currency'),
    ('no_outstanding', 'Left out: no open outstanding item'),
]


class SgcPaymentStatementWizard(models.TransientModel):
    _name = 'sgc.payment.statement.wizard'
    _description = 'Statement From Payments'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    journal_ids = fields.Many2many(
        'account.journal', string='Journals', required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    date_from = fields.Date()
    date_to = fields.Date()
    skip_duplicates = fields.Boolean(
        string='Leave out suspected duplicates', default=True,
        help='A payment with the same journal, partner, amount, date and legacy number as an earlier one is '
             'probably a payment migrated twice: it is left for you to check instead of being cleared.')
    reconcile = fields.Boolean(
        string='Reconcile the lines', default=True,
        help='Match each generated line with its payment. Without it the lines are only created.')
    state = fields.Selection([('draft', 'Draft'), ('preview', 'Preview'), ('done', 'Done')], default='draft')
    report = fields.Html(readonly=True, sanitize=False)

    # -------------------------------------------------------------------------
    # Scope
    # -------------------------------------------------------------------------

    def _payments_domain(self):
        self.ensure_one()
        domain = [
            ('journal_id', 'in', self.journal_ids.ids),
            ('state', 'in', ('draft', 'in_process')),
            ('company_id', '=', self.company_id.id),
        ]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        return domain

    @api.model
    def _legacy_key(self, payment):
        match = LEGACY_NAME.search(payment.memo or '')
        return match.group(1) if match else (payment.memo or '')

    def _open_outstanding_line(self, payment):
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == payment.outstanding_account_id and not line.reconciled)[:1]

    def _classify(self):
        """ :return: {bucket: recordset of payments} for the payments in scope not yet turned into a line. """
        self.ensure_one()
        Payment = self.env['account.payment']
        already = self.env['account.bank.statement.line'].search(
            [('sgc_payment_id', '!=', False), ('journal_id', 'in', self.journal_ids.ids)]).sgc_payment_id
        in_scope = Payment.search(self._payments_domain(), order='date, id') - already
        company_currency = self.company_id.currency_id
        buckets = {key: Payment for key, _label in BUCKETS}
        # a twin is told from its original whatever happened to the original since: cleared here, reconciled
        # by hand, or outside the dates of the run
        seen = set()
        if self.skip_duplicates:
            for payment in Payment.search([
                    ('journal_id', 'in', self.journal_ids.ids), ('state', 'in', ('draft', 'in_process', 'paid')),
                    ('company_id', '=', self.company_id.id)], order='date, id'):
                key = self._duplicate_key(payment)
                if payment in in_scope:
                    if key in seen:
                        buckets['duplicate'] |= payment
                        continue
                seen.add(key)
        for payment in in_scope - buckets['duplicate']:
            journal = payment.journal_id
            if payment.state == 'draft':
                bucket = 'draft'
            elif journal.default_account_id.account_type not in LIQUIDITY_TYPES:
                bucket = 'bad_journal'
            elif payment.currency_id != company_currency or (journal.currency_id and journal.currency_id != company_currency):
                bucket = 'foreign'
            elif not self._open_outstanding_line(payment):
                bucket = 'no_outstanding'
            else:
                bucket = 'eligible'
            buckets[bucket] |= payment
        return buckets

    def _duplicate_key(self, payment):
        return (payment.journal_id.id, payment.partner_id.id, payment.amount, payment.date, self._legacy_key(payment))

    # -------------------------------------------------------------------------
    # Preview
    # -------------------------------------------------------------------------

    def _render_report(self, buckets, extra=None):
        by_journal = defaultdict(lambda: {key: [0, 0.0] for key, _label in BUCKETS})
        for key, payments in buckets.items():
            for payment in payments:
                cell = by_journal[payment.journal_id][key]
                cell[0] += 1
                cell[1] += payment.amount
        head = ''.join('<th class="text-end">%s</th>' % escape(self.env._(label)) for _key, label in BUCKETS)
        rows = []
        totals = {key: [0, 0.0] for key, _label in BUCKETS}
        for journal in sorted(by_journal, key=lambda j: j.code):
            cells = []
            for key, _label in BUCKETS:
                count, amount = by_journal[journal][key]
                totals[key][0] += count
                totals[key][1] += amount
                cells.append('<td class="text-end">%s</td>' % (('%d<br/><small>%s</small>' % (count, '{:,.2f}'.format(amount))) if count else '-'))
            rows.append('<tr><td>%s %s</td>%s</tr>' % (escape(journal.code), escape(journal.name), ''.join(cells)))
        foot = ''.join('<td class="text-end"><b>%d</b><br/><small>%s</small></td>' % (v[0], '{:,.2f}'.format(v[1]))
                       for v in totals.values())
        html = ('<table class="table table-sm"><thead><tr><th>Journal</th>%s</tr></thead><tbody>%s</tbody>'
                '<tfoot><tr><td><b>Total</b></td>%s</tr></tfoot></table>' % (head, ''.join(rows), foot))
        if extra:
            html += extra
        return Markup(html)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new',
        }

    def action_preview(self):
        self.ensure_one()
        self.report = self._render_report(self._classify())
        self.state = 'preview'
        return self._reopen()

    def action_back(self):
        self.state = 'draft'
        return self._reopen()

    # -------------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------------

    def _statement_line_vals(self, payment):
        sign = 1 if payment.payment_type == 'inbound' else -1
        label = payment.name + (' | %s' % payment.memo if payment.memo else '')
        return {
            'journal_id': payment.journal_id.id,
            'date': payment.date,
            'payment_ref': label,
            'partner_id': payment.partner_id.id,
            'amount': sign * payment.amount,
            'sgc_payment_id': payment.id,
        }

    def action_generate(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Only accounting managers can generate statements.'))
        buckets = self._classify()
        eligible = buckets['eligible']
        if not eligible:
            raise UserError(_('There is no payment to generate a statement line for.'))

        Statement = self.env['account.bank.statement']
        StatementLine = self.env['account.bank.statement.line']
        groups = defaultdict(lambda: eligible.browse())
        for payment in eligible:
            groups[(payment.journal_id.id, payment.date.strftime('%Y-%m'))] |= payment

        created = failed = 0
        errors = []
        # chronologically per journal: the opening balance of a statement is the closing one of the one before
        for (journal_id, month), payments in sorted(groups.items()):
            journal = self.env['account.journal'].browse(journal_id)
            lines = StatementLine.create([self._statement_line_vals(p) for p in payments.sorted(lambda p: (p.date, p.id))])
            statement = Statement.create({
                'name': 'GEN %s %s' % (journal.code, month),
                'journal_id': journal.id,
                'sgc_generated': True,
            })
            lines.statement_id = statement
            created += len(lines)
            if not self.reconcile:
                continue
            for line in lines:
                payment = line.sgc_payment_id
                aml = self._open_outstanding_line(payment)
                try:
                    with self.env.cr.savepoint():
                        line._om_reconcile({'matches': [{'aml_id': aml.id}]})
                except Exception as error:  # one payment must not stop the others
                    failed += 1
                    errors.append((payment.name, str(error)))
                    _logger.exception('Statement from payments: %s not reconciled', payment.name)

        reconciled = StatementLine.search_count(
            [('sgc_payment_id', 'in', eligible.ids), ('is_reconciled', '=', True)])
        extra = '<p><b>%d</b> statement lines created, <b>%d</b> reconciled, <b>%d</b> failed.</p>' % (
            created, reconciled, failed)
        if errors:
            extra += '<ul>%s</ul>' % ''.join(
                '<li>%s: %s</li>' % (escape(name), escape(msg)) for name, msg in errors[:30])
        left = self._classify()
        left['eligible'] = left['eligible'].browse()
        self.report = self._render_report({k: v for k, v in left.items() if k != 'eligible'}, extra)
        self.state = 'done'
        return self._reopen()

    # -------------------------------------------------------------------------
    # Removal
    # -------------------------------------------------------------------------

    def action_remove_generated(self):
        """ Undo and delete every line and statement generated from payments in the selected journals. """
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Only accounting managers can remove generated statements.'))
        lines = self.env['account.bank.statement.line'].search(
            [('sgc_payment_id', '!=', False), ('journal_id', 'in', self.journal_ids.ids)])
        statements = lines.statement_id.filtered('sgc_generated')
        for line in lines.filtered('is_reconciled'):
            line.action_undo_reconciliation()
        lines.statement_id = False
        count = len(lines)
        lines.move_id.with_context(force_delete=True).unlink()
        statements.unlink()
        self.report = Markup('<p><b>%d</b> generated statement lines removed.</p>') % count
        self.state = 'done'
        return self._reopen()
