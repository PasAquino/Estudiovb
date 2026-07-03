from odoo import fields, models


class EdipyBilling(models.Model):
    _inherit = "res.city"

    edi_code = fields.Char(string="EDI Code")
    district_id = fields.Many2one("res.country.district", string="District")
