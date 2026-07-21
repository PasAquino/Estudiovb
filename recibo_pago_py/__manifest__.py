# -*- coding: utf-8 -*-
{
    'name': 'Recibo de Pago PDF',
    'version': '15.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Imprime un recibo de pago PDF desde account.payment',
    'description': """
        Módulo que agrega un reporte PDF de Recibo de Pago al modelo account.payment.
        El reporte muestra:
         - Información de la empresa (cabecera)
         - Datos del pago (número, fecha, cliente, importe, método)
         - Tabla de facturas reconciliadas con importes
    """,
    'author': 'Personalizado',
    'website': '',
    'depends': ['account'],
    'data': [
        'reports/report_recibo_pago.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

