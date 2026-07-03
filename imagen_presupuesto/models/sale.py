# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    show_product_images = fields.Boolean(
        string='Mostrar Imágenes de Productos',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'sale.show_product_images_default', 'True') == 'True',
        help='Si está activado, mostrará las imágenes de los productos en el reporte PDF'
    )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_product_image(self):
        """Retorna la imagen del producto o False si no tiene"""
        self.ensure_one()
        if self.product_id and self.product_id.image_128:
            return self.product_id.image_128
        return False