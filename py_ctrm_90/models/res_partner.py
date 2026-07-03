from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PartnerAdded(models.Model):
    _inherit = 'res.partner'

    consumidor_final = fields.Boolean(string="Consumidor final?")
