from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fcws_is_production = fields.Boolean(
        string="Usar entorno de Producción",
        related="company_id.fcws_is_production",
        readonly=False,
    )
    fcws_base_url = fields.Char(
        string="URL Base del Servicio FCWS",
        related="company_id.fcws_base_url",
        readonly=False,
    )
    fcws_docstamp_number = fields.Char(
        string="Número de Timbrado",
        related="company_id.fcws_docstamp_number",
        readonly=False,
    )
    fcws_docstamp_number_test = fields.Char(
        string="Número de Timbrado Test",
        related="company_id.fcws_docstamp_number_test",
        readonly=False,
    )
    fcws_timbrado_fec_ini = fields.Date(
        string="Fecha de inicio del timbrado",
        related="company_id.fcws_timbrado_fec_ini",
        readonly=False,
    )
    fcws_test_user = fields.Char(
        string="Usuario Test",
        related="company_id.fcws_test_user",
        readonly=False,
    )
    fcws_test_password = fields.Char(
        string="Contraseña Test",
        related="company_id.fcws_test_password",
        readonly=False,
    )
    fcws_prod_user = fields.Char(
        string="Usuario Producción",
        related="company_id.fcws_prod_user",
        readonly=False,
    )
    fcws_prod_password = fields.Char(
        string="Contraseña Producción",
        related="company_id.fcws_prod_password",
        readonly=False,
    )

    # 🔹 Campo editable por sucursal
    fcws_branch_name = fields.Char(
        string="Nombre de Sucursal",
        related="company_id.fcws_branch_name",
        readonly=False,
    )
    economic_activity_code = fields.Char(
        string="Economic Activity Code",
        related="company_id.economic_activity_code",
        readonly=False,
    )
    economic_activity_description = fields.Char(
        string="Economic Activity Description",
        related="company_id.economic_activity_description",
        readonly=False,
    )
