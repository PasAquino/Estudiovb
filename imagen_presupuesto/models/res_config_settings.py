# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_show_product_images = fields.Boolean(
        string='Mostrar Imágenes en Presupuestos por Defecto',
        config_parameter='sale.show_product_images_default',
        help='Si está activado, todos los nuevos presupuestos mostrarán imágenes de productos por defecto'
    )

    sale_product_image_size = fields.Selection([
        ('small', 'Pequeño (50px)'),
        ('medium', 'Mediano (80px)'),
        ('large', 'Grande (120px)'),
    ], string='Tamaño de Imagen en Reporte',
        default='medium',
        config_parameter='sale.product_image_size',
        help='Tamaño de las imágenes de productos en el reporte PDF')

