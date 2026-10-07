from odoo import fields, models


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    sgc_generated = fields.Boolean(
        string='Generated From Payments', copy=False, readonly=True,
        help='Built from the payments of the journal: it is not a statement of the bank.')


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    sgc_payment_id = fields.Many2one(
        'account.payment', string='Generated From Payment', copy=False, readonly=True, index='btree_not_null',
        ondelete='set null')
