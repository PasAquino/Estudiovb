from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # ----------------------------------------------------------------------
    # ⚙️ Configuración general FCWS (centralizada por compañía principal)
    # ----------------------------------------------------------------------
    fcws_is_production = fields.Boolean(
        string="Usar entorno de Producción",
        help="Si está activado, el sistema usará las credenciales y URL de producción.",
    )
    fcws_base_url = fields.Char(
        string="URL Base del Servicio FCWS",
        help="URL base del servicio FCWS. Ejemplo: https://ekuatia.criterium.com.py/fcws",
    )
    fcws_docstamp_number = fields.Char(
        string="Número de Timbrado",
        help="Número de timbrado vigente utilizado en los documentos electrónicos.",
    )
    fcws_timbrado_fec_ini = fields.Date(
        string="Fecha de inicio del timbrado",
        help="Fecha de inicio del timbrado configurado en FCWS.",
    )

    # ----------------------------------------------------------------------
    # 🔑 Credenciales de Test
    # ----------------------------------------------------------------------
    fcws_test_user = fields.Char(
        string="Usuario Test",
        help="Usuario del entorno de pruebas de FCWS.",
    )
    fcws_test_password = fields.Char(
        string="Contraseña Test",
        help="Contraseña del entorno de pruebas de FCWS.",
    )
    fcws_docstamp_number_test = fields.Char(
        string="Número de Timbrado Test",
        help="Número de timbrado vigente utilizado en los documentos electrónicos en entorno de pruebas.",
    )

    # ----------------------------------------------------------------------
    # 🔒 Credenciales de Producción
    # ----------------------------------------------------------------------
    fcws_prod_user = fields.Char(
        string="Usuario Producción",
        help="Usuario del entorno de producción de FCWS.",
    )
    fcws_prod_password = fields.Char(
        string="Contraseña Producción",
        help="Contraseña del entorno de producción de FCWS.",
    )

    # ----------------------------------------------------------------------
    # 🏢 Nombre de la sucursal (campo individual por compañía)
    # ----------------------------------------------------------------------
    fcws_branch_name = fields.Char(
        string="Nombre de Sucursal",
        help="Nombre de la sucursal emisora. Este campo puede variar por compañía.",
    )
    economic_activity_code = fields.Char(
        string="Economic Activity Code",
        help="Code that identifies the company's registered economic activity."
    )
    economic_activity_description = fields.Char(
        string="Economic Activity Description",
        help="Description of the company's registered economic activity."
    )
