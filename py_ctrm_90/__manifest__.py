# -*- coding: utf-8 -*-

{
    'name': 'Resolucion 90',
    'version': '0.0.0.1',
    'category': 'Reporting',
    'summary': 'Resolucion 90',
    'sequence': '10',
    'author': 'Hugo Benegas, Criterium SA',
    'company': 'Criterium SA',
    'maintainer': 'Hugo Benegas',
    'support': 'hugo.benegas@criterium.com.py',
    'website': 'https://odoo.criterium.com.py/',
    'demo': [],
    'depends': ['base', 'account', 'py_ctrm_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move.xml',
        'views/resolucion90_view.xml',
        'views/res_company.xml',
        'views/res_partner.xml',
        'views/account_tip_doc.xml'
    ],
    'assets': {
        'web.assets_backend': [
            '/py_ctrm_90/static/src/js/wizard_bottom.js',
        ],
        'web.assets_qweb': [
            '/py_ctrm_90/static/src/xml/wizard_bottom.xml',
        ],
    },
    'installable': True,
}
