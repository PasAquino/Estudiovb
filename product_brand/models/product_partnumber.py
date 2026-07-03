from odoo import api, fields, models


class ProductPartNumber(models.Model):
    _name = "product.partnumber"
    _description = "Product PART#"
    _order = "name"

    name = fields.Char("PART#", required=True)
    description = fields.Text(translate=True)
    partner_id = fields.Many2one("res.partner", string="Partner", help="Select a partner for this brand if any.", ondelete="restrict")
    logo = fields.Binary("Logo")
    product_ids = fields.One2many("product.template", "product_partnumber_id", string="Productos de marca")
    products_count = fields.Integer(string="Número de productos", compute="_compute_products_count")

    @api.depends("product_ids")
    def _compute_products_count(self):
        for brand in self:
            brand.products_count = len(brand.product_ids)
