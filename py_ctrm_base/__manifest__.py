# -*- coding: utf-8 -*-
{
    'name': "Localizacion PY",
    'version': "15.0.1",
    'category': 'Accounting/Accounting',
    'sequence': 15,
    'author': "Criterium S.A.",
    'website': "http://wwww.criterium.com.py",
    'summary': """
       Localizacion Paraguay para Odoo 
    """,
    'description': """
Funcional

Este módulo añade características contables para la localización paraguaya, que representan la configuración mínima necesaria para que una empresa pueda operar en Paraguay y bajo las normas y directrices de la SET (Subsecretaria de Estado de Tributación).

Siga los siguientes pasos de configuración en producción:

    Diríjase a su empresa y configure su número de NIF (RUC).
    Ve a Contabilidad / Ajustes y establece el Plan de Cuentas que te gustaría usar.
    Cree sus diarios de venta teniendo en cuenta la información del Establecimiento y Punto de Expedición.
    Cree las secuencias de los diarios teniendo en cuenta la información del timbrado, su número inicial y final, así como las fechas.

Lo más destacado:

    El plan de cuentas no se instalará automáticamente, cada Plantilla de contable depende de la responsabilidad del Contador de la empresa, tendrá que instalar el plan contable para sus necesidades.
    No se generarán diarios de ventas al instalar un plan contable, deberá configurar sus diarios manualmente.

Técnico

Este módulo añade tanto modelos como campos que serán eventualmente utilizados para la declaración IVA. A continuación, se presenta un resumen de las principales características:



""",
     # any module necessary for this one to work correctly
    'depends': ['base',
                'account',
                'sale'
                ],
    # always loaded
    'data': [
        'views/account_journal_view.xml',
        'views/account_move_view.xml',
        'views/account_tip_doc.xml',
        'views/res_partner_ruc_view.xml',
        'views/account_journal_stamp.xml',
        "security/security.xml",
        'security/ir.model.access.csv',
    ],
    'external_dependencies': {
        'python': [
            'num2words',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
}
