# For copyright and license notices, see __manifest__.py file in module root

from odoo import fields, models
from num2words import num2words


class AccountMove(models.Model):
    _inherit = "account.move"

    amount_total_in_words = fields.Char(
        compute='_compute_amount_tax',
        readonly=True,
        help='Total a pagar en letras'
    )
    amount_total_py = fields.Integer(
        compute='_compute_amount_tax',
        readonly=True,
        help='Total a pagar'
    )
    amount_tax_free_py = fields.Integer(
        compute='_compute_amount_tax',
        readonly=True,
        help='Total excento'
    )
    amount_tax_5_py = fields.Integer(
        compute='_compute_amount_tax',
        readonly=True,
        help='Total iva al 5%'
    )
    amount_tax_10_py = fields.Integer(
        compute='_compute_amount_tax',
        readonly=True,
        help='Total iva al 10%'
    )
    tax_5 = fields.Integer(
        compute='_compute_amount_tax',
        readonly=True,
        help='Liquidacion iva al 5%'
    )
    tax_10 = fields.Integer(
        compute='_compute_amount_tax',
        readonly=True,
        help='Liquidacion iva al 10%'
    )

    def _compute_amount_tax(self):
        for rec in self:
            tax_free = tax_5 = tax_10 = 0

            for line in rec.invoice_line_ids:
                tax_free += line.tax_free
                tax_5 += line.tax_5
                tax_10 += line.tax_10

            rec.amount_total_py = rec.amount_total
            rec.amount_tax_free_py = tax_free
            rec.amount_tax_5_py = tax_5
            rec.amount_tax_10_py = tax_10
            rec.amount_total_in_words = \
                'GUARANIES ' + num2words(rec.amount_total_py,
                                         lang=self.env.user.lang[:2]).upper()

            rec.tax_5 = rec.amount_tax_5_py * (1 - 1/1.05)
            rec.tax_10 = rec.amount_tax_10_py * (1 - 1/1.1)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    tax_free = fields.Integer(
        string='Excento',
        compute='_compute_prices'
    )
    tax_5 = fields.Integer(
        string='IVA 5%',
        compute='_compute_prices'
    )
    tax_10 = fields.Integer(
        string='IVA 10%',
        compute='_compute_prices'
    )

    def _compute_prices(self):
        for rec in self:
            if not rec.tax_ids:
                rec.tax_free = int(rec.price_total)
                rec.tax_5 = 0
                rec.tax_10 = 0
            elif rec.tax_ids[0].amount == 5:
                rec.tax_free = 0
                rec.tax_5 = int(rec.price_total)
                rec.tax_10 = 0
            elif rec.tax_ids[0].amount == 10:
                rec.tax_free = 0
                rec.tax_5 = 0
                rec.tax_10 = int(rec.price_total)
            else:
                rec.tax_free = 1
                rec.tax_5 = 1
                rec.tax_10 = 1
