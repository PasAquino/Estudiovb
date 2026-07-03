# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Plan contable base Paraguay',
    'version': '15.0.1',
    'author': 'Criterium S.A.',
    'category': 'Accounting/Accounting',
    'website': 'www.criterium.com.py',
    'summary': 'Plan contable base para Paraguay',
    'description': """
Funcional

-Define el Plan contable para Paraguay.

-Genera las cuentas contables del plan.

-Define las cuentas por defecto para ventas y compras.

-Define los impuestos por defecto iva ompras y ventas 5% y 10%.

     """,
    'depends': [
        'account',
    ],
    'data': [
        'data/l10n_py.xml',
        'data/account.account.template.csv',
        'data/account_tax_group.xml',
        'data/l10n_py_post.xml',
        'data/account_chart_template_data.xml',
    ],
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
}
