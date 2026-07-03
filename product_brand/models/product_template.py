# Copyright 2009 NetAndCo (<http://www.netandco.net>).
# Copyright 2011 Akretion Benoît Guillot <benoit.guillot@akretion.com>
# Copyright 2014 prisnet.ch Seraphine Lantible <s.lantible@gmail.com>
# Copyright 2016 Serpent Consulting Services Pvt. Ltd.
# Copyright 2018 Daniel Campos <danielcampos@avanzosc.es>
# Copyright 2019 Kaushal Prajapati <kbprajapati@live.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_brand_id = fields.Many2one("product.brand", string="Marca", help="Select a brand for this product")
    product_type_id = fields.Many2one("product.type", string="Tipo", help="Select a type for this product")
    product_family_id = fields.Many2one("product.family", string="Familia", help="Select a family for this product")
    product_partnumber_id = fields.Many2one("product.partnumber", string="PART#", help="Select a PART# for this product")