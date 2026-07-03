# Copyright 2009 NetAndCo (<http://www.netandco.net>).
# Copyright 2011 Akretion Benoît Guillot <benoit.guillot@akretion.com>
# Copyright 2014 prisnet.ch Seraphine Lantible <s.lantible@gmail.com>
# Copyright 2016 Serpent Consulting Services Pvt. Ltd.
# Copyright 2018 Daniel Campos <danielcampos@avanzosc.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class ProductType(models.Model):
    _name = "product.type"
    _description = "Product Type"
    _order = "name"

    name = fields.Char("Tipo", required=True)
    description = fields.Text(translate=True)
    logo = fields.Binary("Logo")
    product_ids = fields.One2many("product.template", "product_type_id", string="Tipo Productos")
    products_count = fields.Integer(string="Número de productos", compute="_compute_products_count")

    @api.depends("product_ids")
    def _compute_products_count(self):
        for type in self:
            type.products_count = len(type.product_ids)
