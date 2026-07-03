# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo import fields, models, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    establishment_code = fields.Char(
        'Cod. Establecimiento',
        help='Numero de establecimiento que representa este diario',
        copy=False
    )
    shipping_point = fields.Char(
        'Cod. Punto de Expedición',
        help='Punto de expedición que representa este diario',
        copy=False
    )
    py_sequence_ids = fields.One2many(
        'ir.sequence',
        'py_latam_journal_id',
        string="Sequences"
    )
    req_doc = fields.Boolean('Control Documentos')
    # check_cheq_diferido = fields.Boolean(
    #     'Cheques Diferidos', default=False,
    #     help='si esta tildado, el diario activa en la forma de pago los campos fecha y listado de banco'
    # )
    # check_cheq_hoy = fields.Boolean(
    #     'Cheques al día', default=False
    # )
    # diario_cheque = fields.Boolean(
    #     'Diario Cheque',
    #     default=False
    # )
    # cheque_cobro = fields.Boolean(
    #     'Cheque Tipo Cobro', default=False
    # )
    # cheque_pago = fields.Boolean(
    #     'Cheques Tipo Pago', default=False
    # )

    _sql_constraints = [
        ('diario-unico-sucursal-expedicion-type',
         'unique(py_establecimiento,py_punto_expedicion,type)',
         "Otro diario ya tiene los mismos codigos de sucursal y expedicion!!")
    ]

    @staticmethod
    def _format(value):
        try:
            intvalue = int(value)
        except ValueError:
            raise ValidationError('Esperabamos un numero')
        return '{0:03}'.format(intvalue)

    @api.onchange('establishment_code')
    def onchange_point(self):
        self.ensure_one()
        self.establishment_code = self._format(self.establishment_code)

    @api.onchange('shipping_point')
    def onchange_code(self):
        self.ensure_one()
        self.shipping_point = self._format(self.shipping_point)

    def _get_journal_codes(self):
        self.ensure_one()
        usual_codes = ['FAC', 'ND', 'NC']
        internal_codes = ['AF', 'PLS', 'CING', 'VUI', 'CUI', 'NCI', 'SUEL']
        expo_codes = ['DESP', 'INV', 'FEXP']
        if self.type != 'sale':
            return []
        return usual_codes + internal_codes + expo_codes

    @api.model
    def create(self, values):
        """ Create Document sequences after create the journal
        """
        res = super().create(values)
        res._ctrm_py_create_document_sequences()
        return res

    def write(self, values):
        """ Update Document sequences after update journal
            si cambia alguno de los campos to_check, entonces regeneramos las
            secuencias.
        """
        to_check = set(['type',
                        'shipping_point',
                        'establishment_code',
                        'req_doc'])
        res = super().write(values)
        if to_check.intersection(set(values.keys())):
            for rec in self:
                rec._ctrm_py_create_document_sequences()
        return res

    @api.constrains('type', 'shipping_point',
                    'establishment_code', 'req_doc')
    def _check_afip_configurations(self):
        """ Do not let to update journal if already have confirmed invoices
        """
        self.ensure_one()
        if self.company_id.country_id != self.env.ref('base.py'):
            return True
        if self.type != 'sale' and self._origin.type != 'sale':
            return True
        invoices = self.env['account.move'].search(
            [('journal_id', '=', self.id),
             ('state', '!=', 'draft')])
        if invoices:
            inv = invoices[:5]
            raise ValidationError(_(
                'No puede cambiar la configuracion de un diario que ya tiene'
                'facturas validadas, mostramos algunas:\n' +
                '- %s' % ('\n- '.join(inv.mapped('display_name')))))


    def _ctrm_py_create_document_sequences(self):
        """ IF Configuration change try to review if this can be done and then
            create / update the document sequences
        """
        self.ensure_one()
        if self.company_id.country_id != self.env.ref('base.py'):
            return True
        if not self.type == 'sale' or not self.req_doc:
            return False

        sequences = self.py_sequence_ids
        sequences.unlink()

        # Create Sequences
        internal_types = ['invoice', 'debit_note', 'credit_note']
        domain = [('internal_type', 'in', internal_types)]

        codes = self._get_journal_codes()
        if codes:
            domain.append(('code', 'in', codes))

        documents = self.env['account.tip.doc'].search(domain)
        for document in documents:
            if self.py_sequence_ids.filtered(
                    lambda x: x.id == document.id):
                continue

            sequences |= self.env['ir.sequence'].create(
                document._get_document_sequence_vals(self))
        return sequences