# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Reportes contables para Paraguay',
    'version': '15.0.1',
    'author': 'Criterium S.A.',
    'category': 'Accounting/Accounting',
    'website': 'www.criterium.com.py',
    'summary': 'Plan contable base para Paraguay',
    'description': """
        Modulo a para generación de informes contables conforme a normativas de Paraguay (con formato de rúbrica):
            * Libro diario
            * Libro mayor
            * Libro IVA
            * Balance Gral:
                
                
    """,
    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'account_payment_paraguay'],

    # always loaded
    'data': [
        'reports/py_accounting_daily_book.xml',
        'reports/py_accounting_balance_book.xml',
        'reports/py_accounting_ledger_book.xml',
        'reports/py_accounting_vat_book.xml',
        'reports/py_accounting_report_pagos.xml',
        'reports/py_accounting_report_cobranzas.xml',
        'reports/py_format_account.xml',
        'wizard/wizard_daily_book.xml',
        'wizard/wizard_balance_book.xml',
        'wizard/wizard_ledger_book.xml',
        'wizard/wizard_vat_book.xml',
        'wizard/wizard_pagos.xml',
        'wizard/wizard_cobros.xml',
        'views/menu_view.xml',
        'views/account_journal_view.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,

}
