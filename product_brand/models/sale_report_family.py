# Copyright 2018 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    product_family_id = fields.Many2one(comodel_name="product.family", string="Familia")

    # pylint:disable=dangerous-default-value
    def _query(
        self, with_clause="", fields={}, groupby="", from_clause=""  # noqa: B006
    ):
        fields["product_family_id"] = ", t.product_family_id as product_family_id"
        groupby += ", t.product_family_id"
        return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)
