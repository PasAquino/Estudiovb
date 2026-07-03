from odoo import fields, models


class ResDepartmentInherit(models.Model):
    _inherit = "res.country.state"

    district_ids = fields.One2many(
        "res.country.district", "state_id", string="Districts"
    )
