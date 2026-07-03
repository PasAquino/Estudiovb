from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentReceiptbook(models.Model):
    _name = 'account.payment.receiptbook'
    _description = 'Account payment Receiptbook'
    _order = 'name asc'

    name = fields.Char('Nombre', size=64, required=True, index=True, )
    partner_type = fields.Selection([('customer', 'Cliente'), ('supplier', 'Proveedor')], string="Tipo de Talonario", required=True, index=True)
    next_number = fields.Integer(related='sequence_id.number_next_actual', string="Siguiente Numero", readonly=False)
    sequence_type = fields.Selection([('automatic', 'Automatico'), ('manual', 'Manual')],
                                     string='Tipo de secuencia', readonly=False, default='automatic')
    sequence_id = fields.Many2one('ir.sequence', 'Secuencia de entrada', help="Este campo contiene la información relacionada con la numeración "
                                                                              "de las entradas de recibo de este talonario de recibos.", copy=False)
    company_id = fields.Many2one('res.company', 'Compañia', required=True, index=True, default=lambda self: self.env.company)
    prefix = fields.Char('Prefijo')
    padding = fields.Integer('Relleno numérico',
                             help="agrega automáticamente un '0' a la izquierda del 'Número' para obtener el tamaño de relleno requerido.")
    active = fields.Boolean('Activo', default=True)

    @api.model
    def create(self, vals):
        sequence_type = vals.get('sequence_type', self._context.get('default_sequence_type', False))
        prefix = vals.get('prefix', self._context.get('default_prefix', False))
        company_id = vals.get('company_id', self._context.get('default_company_id', False))
        if sequence_type == 'automatic' and not vals.get('sequence_id', False) and company_id:
            seq_vals = {'name': vals['name'],
                        'implementation': 'no_gap',
                        'prefix': prefix,
                        'padding': vals['padding'],
                        'number_increment': 1}
            sequence = self.env['ir.sequence'].sudo().create(seq_vals)
            vals.update({'sequence_id': sequence.id})
        return super(AccountPaymentReceiptbook, self).create(vals)
