{
    'name': 'SGC Statement From Payments',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Rebuild bank and cash statements from migrated payments and reconcile them',
    'description': """
Migrated payments that sit in the outstanding accounts can be cleared without a bank file: the wizard creates one
statement line per payment, in date order and grouped by journal and month, then reconciles each line with its
payment. Everything it creates is flagged as generated, so it is never mistaken for a statement of the bank, and
it can be removed again. A preview shows what would be done, and what is left out and why, before anything is written.
    """,
    'author': 'SGC',
    'license': 'LGPL-3',
    'depends': ['account', 'om_account_reconcile'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_statement_wizard_views.xml',
        'views/account_bank_statement_views.xml',
    ],
    'installable': True,
}
