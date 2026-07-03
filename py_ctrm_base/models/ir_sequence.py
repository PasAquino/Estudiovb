# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class IrSequence(models.Model):

    _inherit = 'ir.sequence'

    py_latam_journal_id = fields.Many2one('account.journal', 'Journal')
    account_tip_doc_id = fields.Many2one('account.tip.doc', 'Document Type')