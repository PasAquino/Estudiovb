# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    product_image = fields.Image(string='Imagen del producto',related='product_id.image_128', readonly=True)
