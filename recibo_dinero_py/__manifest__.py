# -*- coding: utf-8 -*-
{
    'name': 'Recibo de Dinero EVB',
    'version': '15.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Imprime Recibo de Dinero desde account.payment con datos de account_payment_paraguay',
    'description': """
        Módulo que agrega el reporte "Recibo de Dinero" al modelo account.payment.
        Toma los datos del grupo de pago (account.payment.paraguay):
          - Cabecera: empresa, N° recibo, fecha, cliente/proveedor, RUC
          - Tabla de facturas: número, importe pagado, N° retención, importe retención
          - Tabla de métodos de pago: método, banco, fecha, importe
    """,
    'author': 'Personalizado EVB',
    'website': '',
    'depends': ['account', 'account_payment_paraguay'],
    'data': [
        'security/ir.model.access.csv',
        'views/invoices_payment_paraguay_views.xml',
        'reports/report_recibo_dinero.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

