# -*- coding: utf-8 -*-
"""
Generador de Nota de Remisión en PDF usando ReportLab.
Soporta caracteres acentuados sin problemas (Helvetica + WinAnsiEncoding).
"""
import io
import base64

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image as RLImage,
)

# ── Colores ──────────────────────────────────────────────────────────────────
BLACK = colors.black
GRAY = colors.Color(0.83, 0.83, 0.83)   # cabeceras de tabla #d3d3d3

# ── Estilos tipográficos ──────────────────────────────────────────────────────
def _s(name, **kw):
    return ParagraphStyle(name, **kw)

NM  = _s('nm',  fontName='Helvetica',      fontSize=8,    leading=10)
BD  = _s('bd',  fontName='Helvetica-Bold', fontSize=8,    leading=10)
SM  = _s('sm',  fontName='Helvetica',      fontSize=7,    leading=9)
SB  = _s('sb',  fontName='Helvetica-Bold', fontSize=7,    leading=9)
CT  = _s('ct',  fontName='Helvetica',      fontSize=8,    leading=10, alignment=TA_CENTER)
CTB = _s('ctb', fontName='Helvetica-Bold', fontSize=8,    leading=10, alignment=TA_CENTER)
TR  = _s('tr',  fontName='Helvetica',      fontSize=7.5,  leading=9,  alignment=TA_RIGHT)
TRB = _s('trb', fontName='Helvetica-Bold', fontSize=7.5,  leading=9,  alignment=TA_RIGHT)
BIG = _s('big', fontName='Helvetica-Bold', fontSize=13,   leading=16, alignment=TA_CENTER)
MED = _s('med', fontName='Helvetica-Bold', fontSize=11,   leading=13, alignment=TA_CENTER)
XS  = _s('xs',  fontName='Helvetica',      fontSize=6.5,  leading=8,  alignment=TA_CENTER)
CN  = _s('cn',  fontName='Helvetica-Bold', fontSize=10,   leading=12)

PAD   = 2 * mm
PAD_S = 1.5 * mm

# ── Utilidades ────────────────────────────────────────────────────────────────

def _p(text, style=NM):
    return Paragraph(text, style)


def _lv(label, value, style=NM):
    """Párrafo con etiqueta en negrita + valor."""
    val = str(value) if value else ''
    return _p(f'<b>{label}:</b> {val}', style)


def _cb(motivo, key):
    """Checkbox marcado o vacío."""
    return '[X]' if motivo == key else '[ ]'


def _ts(cmds):
    return TableStyle(cmds)


BASE_CELL = [
    ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING',    (0, 0), (-1, -1), PAD),
    ('RIGHTPADDING',   (0, 0), (-1, -1), PAD),
    ('TOPPADDING',     (0, 0), (-1, -1), PAD_S),
    ('BOTTOMPADDING',  (0, 0), (-1, -1), PAD_S),
]


# ── Generador principal ───────────────────────────────────────────────────────

def generate_nota_remision_pdf(picking):
    """
    Recibe un record stock.picking y retorna el PDF como bytes.
    """
    buf = io.BytesIO()

    W, H = A4
    LM = RM = 12 * mm
    TM = 12 * mm
    BM =  8 * mm
    UW = W - LM - RM       # 186 mm aprox.

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=TM, bottomMargin=BM,
    )

    o       = picking
    company = o.company_id
    motivo  = o.remision_motivo or ''
    story   = []

    # ══════════════════════════════════════════════════════════════════════════
    # 1.  CABECERA
    # ══════════════════════════════════════════════════════════════════════════
    LW = UW * 0.44    # columna empresa
    RW = UW - LW      # columna timbrado

    # --- Logo ---
    logo_elem = _p('', NM)
    if company.logo:
        try:
            logo_bytes = base64.b64decode(company.logo)
            logo_elem = RLImage(io.BytesIO(logo_bytes),
                                width=28 * mm, height=20 * mm, kind='bound')
        except Exception:
            pass

    # --- Datos empresa (col izq) ---
    t_empresa = Table(
        [[logo_elem,
          Table(
              [[_p(f'<b>{company.name}</b>', CN)],
               [_p(company.partner_id.country_id.name or 'Paraguay', NM)],
               [_p(f'Tel.: {company.phone}' if company.phone else '', NM)]],
              colWidths=[LW - 32 * mm],
              style=_ts([('LEFTPADDING', (0,0), (-1,-1), 2),
                         ('RIGHTPADDING', (0,0), (-1,-1), 2),
                         ('TOPPADDING', (0,0), (-1,-1), 1),
                         ('BOTTOMPADDING', (0,0), (-1,-1), 1)]),
          )]],
        colWidths=[30 * mm, LW - 30 * mm],
        style=_ts([('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                   *BASE_CELL]),
    )

    # --- Timbrado (col der, bordeada) ---
    sn  = o.remision_stamp_number or ''
    vi  = o.remision_stamp_vigencia_ini.strftime('%d/%m/%Y') if o.remision_stamp_vigencia_ini else ''
    vf  = o.remision_stamp_vigencia_fin.strftime('%d/%m/%Y') if o.remision_stamp_vigencia_fin else ''
    ruc = company.vat or ''
    num = o.remision_number or ''

    t_timbrado = Table(
        [[_p(f'<b>TIMBRADO N\u00ba:</b> {sn}', TRB)],
         [_p(f'Vigencia: {vi} al {vf}', TR)],
         [_p(f'<b>R.U.C.:</b> {ruc}', _s('rc', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=TA_CENTER))],
         [_p('NOTA DE REMISI\u00d3N', BIG)],
         [_p(f'N\u00ba {num}', MED)]],
        colWidths=[RW],
        style=_ts([('BOX', (0,0), (-1,-1), 0.7, BLACK),
                   *BASE_CELL]),
    )

    t_header = Table(
        [[t_empresa, t_timbrado]],
        colWidths=[LW, RW],
        style=_ts([('BOX',        (0,0), (-1,-1), 0.7, BLACK),
                   ('LINEBEFORE', (1,0), (1,-1),  0.7, BLACK),
                   ('LEFTPADDING',   (0,0), (-1,-1), 0),
                   ('RIGHTPADDING',  (0,0), (-1,-1), 0),
                   ('TOPPADDING',    (0,0), (-1,-1), 0),
                   ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                   ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]),
    )
    story.append(t_header)

    # ══════════════════════════════════════════════════════════════════════════
    # 2.  GRILLA DE DATOS
    # ══════════════════════════════════════════════════════════════════════════
    HW = UW / 2

    def fv(label, val):
        return _lv(label, val, NM)

    fi = o.remision_fecha_inicio.strftime('%d/%m/%Y') if o.remision_fecha_inicio else ''
    ff = o.remision_fecha_fin.strftime('%d/%m/%Y')    if o.remision_fecha_fin    else ''

    grid_data = [
        [fv('Fecha de inicio del traslado', fi),
         fv('Fecha de t\u00e9rmino del traslado', ff)],

        [fv('RUC o C.I. del Destinatario', o.remision_ruc_destinatario),
         fv('Orden de Trabajo', o.remision_orden_trabajo)],

        [fv('Nombre o Raz\u00f3n Social', o.remision_nombre_razon_social), ''],
        [fv('Nombre de Fantas\u00eda', o.remision_nombre_fantasia), ''],
        [fv('Direcci\u00f3n punto de partida', o.remision_dir_partida), ''],
        [fv('Direcci\u00f3n punto de llegada', o.remision_dir_llegada), ''],

        [fv('Marca del veh\u00edculo de transporte', o.remision_marca_vehiculo),
         fv('RUA del remolque/tractor/semirremolque', o.remision_rua_remolque)],

        [fv('Nombre o Raz\u00f3n Social del Transportista', o.remision_nombre_transportista),
         fv('RUC del Transportista', o.remision_ruc_transportista)],

        [fv('Nombre del Conductor', o.remision_nombre_conductor),
         fv('C.I. del Conductor', o.remision_ci_conductor)],

        [fv('Domicilio del Conductor', o.remision_domicilio_conductor),
         fv('Factura N\u00ba', o.remision_factura_nro)],
    ]

    t_grid = Table(grid_data, colWidths=[HW, HW])
    t_grid.setStyle(_ts([
        ('GRID',  (0,0), (-1,-1), 0.5, BLACK),
        ('SPAN',  (0,2), (1,2)),   # Razón Social  – fila 2
        ('SPAN',  (0,3), (1,3)),   # Fantasía       – fila 3
        ('SPAN',  (0,4), (1,4)),   # Dir partida    – fila 4
        ('SPAN',  (0,5), (1,5)),   # Dir llegada    – fila 5
        *BASE_CELL,
    ]))
    story.append(t_grid)

    # ══════════════════════════════════════════════════════════════════════════
    # 3.  MOTIVO DEL TRASLADO
    # ══════════════════════════════════════════════════════════════════════════
    CW = UW / 4
    otros_txt = o.remision_motivo_otros or ''

    def mc(key, label):
        return _p(f'{_cb(motivo, key)} {label}', SM)

    mot_data = [
        [_p('<b>MOTIVO DEL TRASLADO</b> '
            '<font size="6.5">(marque una sola opci\u00f3n, deber\u00e1 usar un '
            'documento por cada motivo)</font>',
            _s('mh', fontName='Helvetica', fontSize=7.5, leading=9.5))],

        [mc('venta',         'Venta'),
         mc('importacion',   'Importaci\u00f3n'),
         mc('traslado_local','Traslado locales empresa'),
         mc('emisor_movil',  'Emisor m\u00f3vil')],

        [mc('exportacion',   'Exportaci\u00f3n'),
         mc('consignacion',  'Consignaci\u00f3n'),
         mc('transformacion','Transformaci\u00f3n'),
         mc('exhibicion',    'Exhibici\u00f3n')],

        [mc('compra',        'Compra'),
         mc('devolucion',    'Devoluci\u00f3n'),
         mc('reparacion',    'Reparaci\u00f3n'),
         mc('ferias',        'Ferias')],

        [_p(f'<b>Otros (indique motivos):</b> '
            f'{otros_txt if motivo == "otros" else ""}', SM),
         mc('garantia',      'Garant\u00eda'),
         mc('gentileza',     'Gentileza'),
         mc('instalacion',   'Instalaci\u00f3n')],
    ]

    t_mot = Table(mot_data, colWidths=[CW, CW, CW, CW])
    t_mot.setStyle(_ts([
        ('GRID',       (0,0), (-1,-1), 0.5, BLACK),
        ('SPAN',       (0,0), (3,0)),          # header full width
        ('BACKGROUND', (0,0), (3,0), GRAY),
        *BASE_CELL,
    ]))
    story.append(t_mot)

    # ══════════════════════════════════════════════════════════════════════════
    # 4.  TABLA DE PRODUCTOS
    # ══════════════════════════════════════════════════════════════════════════
    MIN_ROWS = 12
    CW_QTY  = 20 * mm
    CW_DESC = UW - CW_QTY

    prod_data = [
        [_p('<b>Cantidad</b>', CTB),
         _p('<b>DESCRIPCI\u00d3N DETALLADA</b> (Incluir cantidad o porcentaje de '
            'tolerancia de quiebre o merma) Datos de relevancia de la mercader\u00eda',
            CTB)],
    ]

    lines = o.move_ids_without_package.filtered(lambda m: m.state != 'cancel')
    for line in lines:
        qty   = line.quantity_done if line.quantity_done else line.product_uom_qty
        desc  = line.product_id.display_name or ''
        if line.product_uom and line.product_uom.name not in ('Units', 'Unidades', 'u', 'Unit'):
            desc += f' ({line.product_uom.name})'
        if line.description_picking:
            desc += f' - {line.description_picking}'
        prod_data.append([_p(f'{qty:.2f}', CT), _p(desc, NM)])

    # Filas vacías hasta MIN_ROWS
    for _ in range(max(0, MIN_ROWS - len(lines))):
        prod_data.append([_p('', NM), _p('', NM)])

    row_h = [None] + [7 * mm] * (len(prod_data) - 1)
    t_prod = Table(prod_data, colWidths=[CW_QTY, CW_DESC], rowHeights=row_h)
    t_prod.setStyle(_ts([
        ('GRID',       (0,0), (-1,-1), 0.5, BLACK),
        ('BACKGROUND', (0,0), (1,0),   GRAY),
        *BASE_CELL,
    ]))
    story.append(t_prod)

    # ══════════════════════════════════════════════════════════════════════════
    # 5.  RECEPCIÓN Y FIRMAS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 4 * mm))
    story.append(_p('<b>RECEPCI\u00d3N DE LA MERCADER\u00cdA:</b>', BD))
    story.append(Spacer(1, 14 * mm))

    FW = UW / 3
    firma_data = [
        [_p('Firma', CT), _p('Aclaraci\u00f3n', CT), _p('Fecha', CT)],
    ]
    t_firma = Table(firma_data, colWidths=[FW, FW, FW], rowHeights=[6 * mm])
    t_firma.setStyle(_ts([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, BLACK),   # línea de firma
        ('ALIGN',     (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',    (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING',   (0,0), (-1,-1), PAD),
        ('RIGHTPADDING',  (0,0), (-1,-1), PAD),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_firma)

    # ══════════════════════════════════════════════════════════════════════════
    # 6.  PIE – COPIAS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 4 * mm))
    story.append(_p(
        'Original (Blanco): Destinatario \u00b7 '
        'Duplicado (Color): Remitente \u00b7 '
        'Triplicado (Color): SET \u00b7 '
        'Cuadruplicado (Color): Transportista',
        XS,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()

