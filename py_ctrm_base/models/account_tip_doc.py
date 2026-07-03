# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import fields, models


class accounttipdoc(models.Model):
    _name = "account.tip.doc"
    _description = "Tipos de Documentos"

    name = fields.Char(string="Descripción")
    code = fields.Char(string="Código"
    )
    code_hck = fields.Char(string="Código Hechauka"
                       )
    tipdoc = fields.Selection(
        selection=[
            ('sale', 'Ingreso'),
            ('purchase', 'Gasto'),
        ],
        string="Tipo Operacion"
    )
    internal_type = fields.Selection(
        selection=[
            ('invoice', 'Factura'),
            ('debit_note', 'Nota de Debito'),
            ('credit_note', 'Nota de Credito'),
        ],
        string = "Tipo Documento"
    )
    vatbook = fields.Boolean('Libro IVA?')
    req_timbrado = fields.Boolean('Control Timbrado')

    def _get_document_sequence_vals(self, journal):
        """ Values to create the sequences """
        #values = super()._get_document_sequence_vals(journal)
        #if self.country_id != self.env.ref('base.py'):
        #    return values
        values = {}
        values.update(
            {'name': 'Secuencia de %s %s-%s-' % (journal.name,
                                                 journal.establishment_code,
                                                 journal.shipping_point),
             'code': 'INV',
             'implementation': 'no_gap',
             'prefix': "%s-%s-" % (journal.establishment_code,
                                   journal.shipping_point),
             'suffix': '',
             'padding': 7,
             'company_id': journal.company_id.id,
             'py_latam_journal_id': journal.id}
        )

        #values.update({'name': '%s - %s' % (journal.name, self.name),
        #               'account_tip_doc_id': self.id})
        return values

    def _format_document_number(self, document_number):
        """ Make validation of Import Dispatch Number
          * making validations on the document_number. If it is wrong it
            should raise an exception
          * format the document_number against a pattern and return it
        """
        self.ensure_one()
        if self.country_id != self.env.ref('base.py'):
            return super()._format_document_number(document_number)

        if not document_number:
            return False

        msg = "'%s' " + _("no es un valor valido para el "
                          "documento") + " '%s'.\n%s"

        # Invoice Number Validator (.i.e: 3-4-123)
        failed = False
        args = document_number.split('-')
        if len(args) != 3:
            failed = True
        else:
            suc, exp, number = args
            if len(suc) > 3 or not suc.isdigit():
                failed = True
            elif len(exp) > 3 or not number.isdigit():
                failed = True
            elif len(number) > 7 or not number.isdigit():
                failed = True

            mask = '{:>03s}-{:>03s}-{:>07s}'
            document_number = mask.format(suc, exp, number)
        if failed:
            raise UserError(msg % (document_number, self.name, _(
                'El numero de documento debe ser ingresado separando con el '
                'signo menos (-) cada parte, debe tener un maximo de 3 '
                'digitos para Codigo de Establecimiento y Punto de Expedicion '
                'y un maximo de 7 digitos para el numero de documento. '
                'Los siguientes son ejemplos de numeros validos:\n'
                '* 1-1-1\n'
                '* 003-001-0000087\n'
                '* 25-45-885')))

        return document_number
