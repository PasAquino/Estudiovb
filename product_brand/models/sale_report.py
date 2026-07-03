# Copyright 2018 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    product_brand_id = fields.Many2one(comodel_name="product.brand", string="Marca")
    product_partnumber_id = fields.Many2one(comodel_name="product.partnumber", string="Part#")

    # pylint:disable=dangerous-default-value
    def _query(
            self, with_clause="", fields={}, groupby="", from_clause=""  # noqa: B006
    ):
        fields[
            "product_brand_id", "product_chip_id", "product_partnumber_id"] = \
            ", t.product_brand_id as product_brand_id, t.product_partnumber_id"
        groupby += ", t.product_brand_id, t.product_partnumber_id"
        return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)
