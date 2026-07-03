from odoo.exceptions import ValidationError
from odoo import fields, models, api, _


class TalonarioCheques(models.Model):
    _name = "account.checkbooks"
    _description = 'Cartera de Cheques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "cuenta_bank"

    name = fields.Char(string="Número de Cuenta", unique=True, size=8, tracking=True)
    cuenta_bank = fields.Many2one('res.partner.bank', string="Cuenta Bancaria", required=True, tracking=True)
    serie = fields.Char(string="Serie", tracking=True)
    bank_id = fields.Many2one('res.bank', string="Banco", tracking=True)
    number_start = fields.Integer(string='Rango Desde', required=True, tracking=True)
    number_end = fields.Integer(string='Rango Hasta', required=True, tracking=True)
    active = fields.Boolean(string='Activo', tracking=True)
    active_state = fields.Selection([('active', 'Activo'), ('inactive', 'Inactivo')], default='active', copy=False,
                                    tracking=True, string="Estado")
    current_number = fields.Integer(string='Próximo Número', required=True)
    number_used = fields.Integer(string="Ultimo Número Utilizado")
    company_id = fields.Many2one('res.company', 'Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)

    @api.constrains('active', 'active_state')
    def is_active(self):
        active = self.active
        if active and self.active_state == 'active':
            checkbooks = self.env['account.checkbooks'].search([('company_id', '=', self.company_id.id),
                                                                ('cuenta_bank', '=', self.cuenta_bank.id),
                                                                ('bank_id', '=', self.bank_id.id),
                                                                ('number_start', '=', self.number_start),
                                                                ('number_end', '=', self.number_end),
                                                                ('active', '=', True),
                                                                ('active_state', '=', 'active')])
            if checkbooks:
                for talonario in checkbooks:
                    if talonario.id != self.id:
                        raise ValidationError('No se pueden tener dos Cheques del mismo tipo activos en el sistema')
