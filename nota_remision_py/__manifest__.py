# -*- coding: utf-8 -*-
{
    'name': 'Nota de Remision Paraguay',
    'version': '15.0.1.0.1',
    'category': 'Inventory',
    'summary': 'Genera e imprime Notas de Remision desde transferencias de stock (Paraguay)',
    'description': """
        Modulo para generar, administrar e imprimir Notas de Remision
        integradas con las transferencias de inventario (stock.picking).
        - Estados: Borrador / Confirmado
        - Wizard para completar datos antes de confirmar
        - Timbrado desde account.journal.stamped (tipo 2 = Remisiones)
        - Reporte PDF generado con ReportLab (sin problemas de acentos)
    """,
    'author': 'Personalizado',
    'website': '',
    'depends': ['stock', 'py_ctrm_base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/remision_confirm_wizard_view.xml',
        'views/stock_picking_remision_views.xml',
        'reports/report_nota_remision.xml',
    ],
    'post_init_hook': 'remove_report_binding',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
