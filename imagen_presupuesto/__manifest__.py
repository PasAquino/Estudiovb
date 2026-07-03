# -*- coding: utf-8 -*-

{
    'name': 'imagen_presupuesto',
    'version': '16.0.1',
    'category': 'Localization',
    'sequence': 15,
    'author': 'Hugo Benegas, Criterium SA',
    'support': 'hugo.benegas@criterium.com.py',
    'website': 'https://odoo.criterium.com.py/',
    'summary':
        """
            imagen_presupuesto   
        """,
    'depends': ['base', 'account', 'sale'],
    'data': [
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'reports/sale_order_line.xml',
        # 'reports/presupuestoopcion2.xml',
        'views/sale_order_line.xml',
    ],
    'installable': True,
    'auto_install': False,
}
