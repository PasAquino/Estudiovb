# Copyright 2009 NetAndCo (<http://www.netandco.net>).
# Copyright 2011 Akretion Benoît Guillot <benoit.guillot@akretion.com>
# Copyright 2014 prisnet.ch Seraphine Lantible <s.lantible@gmail.com>
# Copyright 2016 Serpent Consulting Services Pvt. Ltd.
# Copyright 2018 Daniel Campos <danielcampos@avanzosc.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class ProductFamily(models.Model):
    _name = "product.family"
    _description = "Product Family"
    _order = "name"

    name = fields.Char("Familia", required=True)
    description = fields.Text(translate=True)
    logo = fields.Binary("Logo")
    product_ids = fields.One2many("product.template", "product_family_id", string="Productos de la familia")
    products_count = fields.Integer(string="Number of products", compute="_compute_products_count_type")

    @api.depends("product_ids")
    def _compute_products_count_type(self):
        for family in self:
            family.products_count = len(family.product_ids)
