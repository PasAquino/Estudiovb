# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp


class AccountAccountInherit(models.Model):
    _inherit = "account.account"

    account_order = fields.Integer(string="Posición de la Cuenta")
