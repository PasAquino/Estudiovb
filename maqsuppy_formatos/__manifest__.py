# -*- coding: utf-8 -*-

{
    'name': 'Formatos',
    'version': '16.0.1',
    'category': 'Localization',
    'sequence': 15,
    'author': 'Hugo Benegas, Criterium SA',
    'support': 'hugo.benegas@criterium.com.py',
    'website': 'https://odoo.criterium.com.py/',
    'summary':
        """
            Formatos personalizados   
        """,
    'depends': ['base', 'account', 'sale'],
    'data': [
        'reports/factura.xml',
        'reports/presupuesto.xml',
        'reports/presupuesto_latin_america.xml',
        'reports/presupuesto_latinoamerica.xml',
        'reports/presupuesto_lion.xml',
        'reports/factura_triplicado.xml',
        'reports/nota_remision.xml',
        'reports/factura_autoimpresor.xml',
        'reports/config_reports.xml',
    ],
    'installable': True,
    'auto_install': False,
}
