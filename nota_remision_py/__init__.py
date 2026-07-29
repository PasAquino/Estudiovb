# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import reports


def remove_report_binding(cr, registry):
    """
    Elimina el binding del ir.actions.report con stock.picking
    para que la Nota de Remision NO aparezca en el menu Imprimir.
    El PDF se genera exclusivamente desde el boton 'Imprimir Nota de Remision'.
    """
    cr.execute("""
        UPDATE ir_act_report_xml
           SET binding_model_id = NULL
         WHERE report_name = 'nota_remision_py.report_nota_remision_document'
    """)


