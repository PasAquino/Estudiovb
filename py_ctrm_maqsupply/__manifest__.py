# -*- coding: utf-8 -*-

{
    'name': 'Customizaciones Maqsupply',
    'version': '15.0.1.0',
    'summary': 'Funciones especificas y nuevos campos a modulos existentes',
    'description': 'Customizaciones',
    'category': 'Hidden/Tools',
    'author': 'Hugo Benegas, Criterium SA',
    'support': 'hugo.benegas@criterium.com.py',
    'website': 'https://criterium.com.py/',
    'license': 'AGPL-3',
    'depends': ['base', 'purchase'],
    'data': [
        'views/purchase_order.xml',
        'views/account_move.xml',
    ],
    'installable': True,
    'auto_install': False
}
