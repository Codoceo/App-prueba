import flet as ft
import psycopg2
from datetime import datetime
import re
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONEXIÓN
# =============================================================================
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="bitacora",
        user="postgres",
        password="postgres"
    )

# =============================================================================
# TRIGGERS DE CATEGORÍA
# =============================================================================
TRIGGERS_COMIDA = [
    r'com[ií]', r'comimos',
    r'almorzamos', r'almorcé', r'almorzó', r'almorz[aá]',
    r'desayun[eé]', r'desayunó', r'desayunamos', r'desayun[oó]',
    r'cen[eé]', r'cenó', r'cenamos', r'cen[oó]',
    r'merendé', r'meriend[eé]',
    r'piqué', r'pedí',
    r'tomé desayuno', r'tomé once',
]

TRIGGERS_GIMNASIO = [
    r'hice', r'hicimos',
    r'entren[eé]', r'entrenó', r'entrenamos',
    r'ejercit[eé]', r'ejercitamos',
    r'fui al gym', r'\bgym\b',
    r'levanté', r'levant[eé]',
    r'corr[ií]', r'corrimos',
    r'salt[eé]', r'nad[eé]', r'pedaleé',
]

TRIGGERS_GASTOS = [
    r'compr[eé]', r'compramos', r'compró',
    r'pagu[eé]', r'pagamos', r'pagó',
    r'gasté', r'gastamos', r'gastó',
]

def detectar_categoria(texto: str) -> str | None:
    t = texto.lower()
    for p in TRIGGERS_COMIDA:
        if re.search(p, t):
            return "Comida"
    for p in TRIGGERS_GASTOS:
        if re.search(p, t):
            return "Gastos"
    for p in TRIGGERS_GIMNASIO:
        if re.search(p, t):
            return "Gimnasio"
    return None

# =============================================================================
# EXTRACCIÓN DE MONTO (soporta negativos y valores desde 3 dígitos: 300, 500...)
# =============================================================================
def extraer_monto_clp(texto: str) -> int:
    t = texto.lower()

    # Negativo con k/mil/lucas: "-5k", "-25 lucas"
    m = re.search(r'-\s*(\d+)\s*(k|mil|lucas)', t)
    if m:
        return -int(m.group(1)) * 1000

    # Positivo con k/mil/lucas (con posible "-" antes)
    m = re.search(r'(\d+)\s*(k|mil|lucas)', t)
    if m:
        pre   = t[:m.start()].rstrip()
        valor = int(m.group(1)) * 1000
        return -valor if pre.endswith('-') else valor

    # Negativo directo con 3+ dígitos: "-300", "-2500"
    m = re.search(r'-\s*(\d{3,10})', t)
    if m:
        return -int(m.group(1))

    # Positivo directo con 3+ dígitos: "300", "$5000", "chockman 300"
    m = re.search(r'\$?\s*(\d{3,10})', t)
    if m:
        return int(m.group(1))

    return 0

# =============================================================================
# EXTRACCIÓN DE CANTIDAD (1-2 dígitos, distinto del monto)
# =============================================================================
def extraer_cantidad(texto: str) -> int:
    t = texto.lower()
    t = re.sub(r'-?\s*\d+\s*(k|mil|lucas)', '', t)
    t = re.sub(r'-?\$?\s*\d{3,10}', '', t)
    m = re.search(r'\b(\d{1,2})\b', t)
    return int(m.group(1)) if m else 0

# =============================================================================
# EXTRACCIÓN DE COMIDA (solo el nombre, sin trigger ni cantidad)
# =============================================================================
def extraer_comida(texto: str) -> str:
    t = texto.lower()
    t = re.sub(r'-?\s*\d+\s*(k|mil|lucas)', '', t)
    t = re.sub(r'-?\$?\s*\d{3,10}', '', t)

    for p in TRIGGERS_COMIDA:
        # trigger + cantidad + comida: "comí 5 completos"
        m = re.search(p + r'\s+\d+\s+([a-záéíóúüñ]+(?:\s+[a-záéíóúüñ]+){0,2})', t)
        if m:
            return m.group(1).strip().title()
        # trigger + comida: "almorcé pizza"
        m = re.search(p + r'\s+([a-záéíóúüñ]{2,}(?:\s+[a-záéíóúüñ]+){0,2})', t)
        if m:
            word = m.group(1).strip()
            if not re.match(r'^\d+$', word):
                return word.title()
    return ""

# =============================================================================
# EXTRACCIÓN DE EJERCICIO (solo el nombre, sin "hice" ni cantidad)
# =============================================================================
def extraer_ejercicio(texto: str) -> str:
    t = texto.lower()
    t = re.sub(r'-?\s*\d+\s*(k|mil|lucas)', '', t)
    t = re.sub(r'-?\$?\s*\d{3,10}', '', t)

    for p in TRIGGERS_GIMNASIO:
        # trigger + cantidad + ejercicio: "hice 20 sentadillas"
        m = re.search(p + r'\s+\d+\s+([a-záéíóúüñ]+(?:\s+[a-záéíóúüñ]+){0,2})', t)
        if m:
            return m.group(1).strip().title()
        # trigger + ejercicio: "entrené natación"
        m = re.search(p + r'\s+([a-záéíóúüñ]{2,}(?:\s+[a-záéíóúüñ]+){0,2})', t)
        if m:
            word = m.group(1).strip()
            if not re.match(r'^\d+$', word):
                return word.title()
    return ""

# =============================================================================
# ANÁLISIS COMPLETO DEL TEXTO
# =============================================================================
def analizar_texto(texto: str) -> dict:
    cat = detectar_categoria(texto)
    return {
        "categoria": cat,
        "monto":     extraer_monto_clp(texto),
        "cantidad":  extraer_cantidad(texto),
        "comida":    extraer_comida(texto)    if cat == "Comida"   else "",
        "ejercicio": extraer_ejercicio(texto) if cat == "Gimnasio" else "",
    }

# =============================================================================
# BASE DE DATOS
# =============================================================================
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id        SERIAL PRIMARY KEY,
            fecha     TEXT,
            texto     TEXT,
            monto     INTEGER DEFAULT 0,
            categoria TEXT,
            comida    TEXT    DEFAULT '',
            cantidad  INTEGER DEFAULT 0,
            ejercicio TEXT    DEFAULT ''
        )
    ''')
    conn.commit()
    for col, defn in [("cantidad", "INTEGER DEFAULT 0"), ("ejercicio", "TEXT DEFAULT ''")]:
        try:
            c.execute(f"ALTER TABLE registros ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            conn.rollback()
    conn.close()

# =============================================================================
# PALETA OSCURA
# =============================================================================
PAGE_BG        = "#0D0D14"
HEADER_BG      = "#13131F"
CARD_BG        = "#1A1A28"
SURFACE        = "#1F1F30"
BORDER         = "#2A2A40"
TEXT_PRIMARY   = "#E8E8F0"
TEXT_SECONDARY = "#8888AA"
ACCENT         = "#7C6FE0"
BALANCE_COLOR  = "#FFD54F"

CATEGORIA_COLORES = {
    "Gimnasio": {"bg": "#081A14", "icon": "🏋️", "badge": "#1A7858", "chip_bg": "#0C2A1E", "chip_fg": "#2A9870"},
    "Comida":   {"bg": "#1A1408", "icon": "🍽️", "badge": "#786018", "chip_bg": "#2A2010", "chip_fg": "#A08028"},
    "Gastos":   {"bg": "#081820", "icon": "💸", "badge": "#1A6878", "chip_bg": "#0C2230", "chip_fg": "#2A8898"},
    "General":  {"bg": "#0A1018", "icon": "📋", "badge": "#2A5068", "chip_bg": "#101828", "chip_fg": "#3A7088"},
}

# =============================================================================
# MAIN
# =============================================================================
def main(page: ft.Page):
    page.title = "Mi Bitácora"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = PAGE_BG
    page.padding = 0
    page.fonts = {
        "DM Sans": "https://fonts.gstatic.com/s/dmsans/v15/rP2tp2ywxg089UriI5-g4vlH9VoD8Cmcqbm40F9JadbnoEwAkJxhTmf3ZGMZpg.woff2"
    }
    page.font_family = "DM Sans"

    init_db()

    estado = {"categoria": "General", "filtro": "Todos", "buscar": ""}

    # ── CONTROLES ─────────────────────────────────────────────────────────────
    input_texto = ft.TextField(
        hint_text="Ej: Comí 5 completos -2500  /  Hice 20 sentadillas",
        hint_style=ft.TextStyle(color=TEXT_SECONDARY),
        expand=True,
        border_radius=14,
        bgcolor=SURFACE,
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT_PRIMARY,
        cursor_color=ACCENT,
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
    )

    input_comida = ft.TextField(
        hint_text="¿Qué comida? (se detecta automáticamente)",
        hint_style=ft.TextStyle(color=TEXT_SECONDARY),
        expand=True,
        border_radius=14,
        bgcolor=SURFACE,
        border_color="#3A2200",
        focused_border_color="#FB8C00",
        color=TEXT_PRIMARY,
        cursor_color="#FB8C00",
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        visible=False,
    )

    chip_categoria = ft.Container(visible=False)
    chip_cantidad  = ft.Container(visible=False)
    chip_detalle   = ft.Container(visible=False)
    chip_monto     = ft.Container(visible=False)
    fila_preview   = ft.Row(
        [chip_categoria, chip_cantidad, chip_detalle, chip_monto],
        spacing=6, visible=False,
    )

    balance_texto = ft.Text("$ 0", size=17, weight="bold", color=BALANCE_COLOR)
    lista_registros = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=8)

    input_buscar = ft.TextField(
        hint_text="Buscar en registros...",
        hint_style=ft.TextStyle(color=TEXT_SECONDARY),
        expand=True,
        border_radius=14,
        bgcolor=SURFACE,
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT_PRIMARY,
        cursor_color=ACCENT,
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        height=42,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        visible=False,
    )

    def on_buscar_change(e):
        estado["buscar"] = input_buscar.value or ""
        cargar_datos(estado["filtro"])

    input_buscar.on_change = on_buscar_change

    def toggle_buscar(e):
        input_buscar.visible = not input_buscar.visible
        if not input_buscar.visible:
            input_buscar.value = ""
            estado["buscar"] = ""
            cargar_datos(estado["filtro"])
        page.update()

    btn_lupa = ft.Container(
        content=ft.Icon(ft.Icons.SEARCH, color=TEXT_SECONDARY, size=20),
        on_click=toggle_buscar,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=6, vertical=4),
        ink=True,
    )

    # ── BALANCE ───────────────────────────────────────────────────────────────
    def calcular_balance():
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT SUM(monto) FROM registros")
        total = c.fetchone()[0] or 0
        conn.close()
        return total

    def actualizar_balance():
        total = calcular_balance()
        color = "#66BB6A" if total >= 0 else "#EF5350"
        signo = "+" if total > 0 else ""
        balance_texto.value = f"{signo}$ {abs(total):,}".replace(",", ".")
        balance_texto.color = color

    # ── CARGAR DATOS ──────────────────────────────────────────────────────────
    def cargar_datos(filtro="Todos"):
        lista_registros.controls.clear()
        conn = get_conn()
        c = conn.cursor()
        buscar = estado["buscar"].strip()

        if filtro == "Todos" and not buscar:
            c.execute("""
                SELECT texto, fecha, monto, categoria, comida, cantidad, ejercicio
                FROM registros ORDER BY id DESC
            """)
        elif filtro == "Todos" and buscar:
            c.execute("""
                SELECT texto, fecha, monto, categoria, comida, cantidad, ejercicio
                FROM registros WHERE LOWER(texto) LIKE %s ORDER BY id DESC
            """, (f"%{buscar.lower()}%",))
        elif filtro != "Todos" and not buscar:
            c.execute("""
                SELECT texto, fecha, monto, categoria, comida, cantidad, ejercicio
                FROM registros WHERE categoria=%s ORDER BY id DESC
            """, (filtro,))
        else:
            c.execute("""
                SELECT texto, fecha, monto, categoria, comida, cantidad, ejercicio
                FROM registros WHERE categoria=%s AND LOWER(texto) LIKE %s ORDER BY id DESC
            """, (filtro, f"%{buscar.lower()}%"))

        rows = c.fetchall()
        conn.close()

        if not rows:
            lista_registros.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No hay registros aún.",
                        color=TEXT_SECONDARY, italic=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment(0, 0),
                    padding=30,
                )
            )
        else:
            for texto, fecha, monto, categoria, comida, cantidad, ejercicio in rows:
                cfg = CATEGORIA_COLORES.get(categoria, CATEGORIA_COLORES["General"])

                monto_color = "#66BB6A" if monto > 0 else ("#EF5350" if monto < 0 else TEXT_SECONDARY)
                monto_txt = ""
                if monto > 0:
                    monto_txt = f"+$ {monto:,}".replace(",", ".")
                elif monto < 0:
                    monto_txt = f"-$ {abs(monto):,}".replace(",", ".")

                chips_detalle = []

                if comida:
                    lbl = f"🍽 {comida}" + (f"  ×{cantidad}" if cantidad else "")
                    chips_detalle.append(ft.Container(
                        content=ft.Text(lbl, size=11, color=cfg["chip_fg"], weight="bold"),
                        bgcolor=cfg["chip_bg"], border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    ))

                if ejercicio:
                    lbl = f"💪 {ejercicio}" + (f"  ×{cantidad}" if cantidad else "")
                    chips_detalle.append(ft.Container(
                        content=ft.Text(lbl, size=11, color="#4E9452", weight="bold"),
                        bgcolor="#0A1C10", border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    ))

                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(cfg["icon"], size=16),
                                bgcolor=cfg["badge"],
                                border_radius=7,
                                padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            ),
                            ft.Text(categoria, size=12, color=cfg["badge"], weight="bold"),
                            ft.Container(expand=True),
                            ft.Text(monto_txt, color=monto_color, weight="bold", size=14),
                        ], alignment=ft.MainAxisAlignment.START),
                        # Chips arriba (comida/ejercicio destacado)
                        ft.Row([
                            *chips_detalle,
                        ], visible=bool(chips_detalle)) if chips_detalle else ft.Container(visible=False),
                        # Texto completo abajo
                        ft.Text(texto, size=12, color=TEXT_SECONDARY),
                        ft.Text(fecha, size=10, color=TEXT_SECONDARY, text_align=ft.TextAlign.RIGHT),
                    ], spacing=5),
                    bgcolor=cfg["bg"],
                    padding=13,
                    border_radius=13,
                    shadow=ft.BoxShadow(blur_radius=8, color="#00000040", offset=ft.Offset(0, 3)),
                )
                lista_registros.controls.append(card)

        actualizar_balance()
        page.update()

    # ── GUARDAR ───────────────────────────────────────────────────────────────
    def guardar(e):
        if not input_texto.value.strip():
            return

        texto     = input_texto.value.strip()
        analisis  = analizar_texto(texto)
        cat       = analisis["categoria"] or estado["categoria"]
        monto     = analisis["monto"]
        cantidad  = analisis["cantidad"]
        comida    = analisis["comida"] or (input_comida.value.strip() if cat == "Comida" else "")
        ejercicio = analisis["ejercicio"]
        fecha     = datetime.now().strftime("%d/%m/%Y %H:%M")

        conn = get_conn()
        c    = conn.cursor()
        c.execute(
            """INSERT INTO registros (fecha, texto, monto, categoria, comida, cantidad, ejercicio)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (fecha, texto, monto, cat, comida, cantidad, ejercicio)
        )
        conn.commit()
        conn.close()

        input_texto.value  = ""
        input_comida.value = ""
        limpiar_preview()
        cargar_datos(estado["filtro"])

    input_texto.on_submit = guardar

    # ── PREVIEW EN TIEMPO REAL ────────────────────────────────────────────────
    def limpiar_preview():
        fila_preview.visible = False
        for ch in [chip_categoria, chip_cantidad, chip_detalle, chip_monto]:
            ch.visible = False

    def _chip(chip, text, bg, fg):
        chip.content       = ft.Text(text, size=11, color=fg, weight="bold")
        chip.bgcolor       = bg
        chip.border_radius = 10
        chip.padding       = ft.Padding.symmetric(horizontal=9, vertical=4)
        chip.visible       = True

    def on_texto_change(e):
        texto = input_texto.value or ""
        if not texto.strip():
            limpiar_preview()
            page.update()
            return

        a   = analizar_texto(texto)
        cat = a["categoria"]

        if cat and cat != estado["categoria"]:
            cambiar_categoria(cat)

        if cat == "Comida" and a["comida"]:
            input_comida.value = a["comida"]

        hay = False

        if cat:
            cfg = CATEGORIA_COLORES[cat]
            _chip(chip_categoria, f"{cfg['icon']} {cat}", cfg["chip_bg"], cfg["chip_fg"])
            hay = True
        else:
            chip_categoria.visible = False

        if a["cantidad"] > 0:
            _chip(chip_cantidad, f"× {a['cantidad']}", "#1A1A35", "#A0A0D0")
            hay = True
        else:
            chip_cantidad.visible = False

        detalle = a["comida"] or a["ejercicio"]
        if detalle:
            _chip(chip_detalle, f"• {detalle}", "#1A1A30", TEXT_SECONDARY)
            hay = True
        else:
            chip_detalle.visible = False

        if a["monto"] != 0:
            pos   = a["monto"] > 0
            signo = "+" if pos else "-"
            txt   = f"{signo}$ {abs(a['monto']):,}".replace(",", ".")
            _chip(chip_monto, txt,
                  "#0D2818" if pos else "#2A0A0A",
                  "#66BB6A" if pos else "#EF5350")
            hay = True
        else:
            chip_monto.visible = False

        fila_preview.visible = hay
        page.update()

    input_texto.on_change = on_texto_change

    # ── MENÚ DE CATEGORÍAS ────────────────────────────────────────────────────
    botones_cat = []

    def cambiar_categoria(cat):
        estado["categoria"]  = cat
        input_comida.visible = (cat == "Comida")
        for btn in botones_cat:
            cfg = CATEGORIA_COLORES.get(btn.data, CATEGORIA_COLORES["General"])
            if btn.data == cat:
                btn.bgcolor                   = cfg["badge"]
                btn.content.controls[1].color = "#FFFFFF"
            else:
                btn.bgcolor                   = cfg["bg"]
                btn.content.controls[1].color = cfg["chip_fg"]
        page.update()

    for cat, cfg in CATEGORIA_COLORES.items():
        es_sel = (cat == estado["categoria"])
        btn = ft.Container(
            data=cat,
            content=ft.Row([
                ft.Text(cfg["icon"], size=13),
                ft.Text(cat, size=12, weight="bold",
                        color="#FFFFFF" if es_sel else cfg["chip_fg"]),
            ], spacing=4, tight=True),
            bgcolor=cfg["badge"] if es_sel else cfg["bg"],
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=12, vertical=7),
            on_click=lambda e, c=cat: cambiar_categoria(c),
            ink=True,
        )
        botones_cat.append(btn)

    fila_categorias = ft.Row(botones_cat, scroll=ft.ScrollMode.AUTO, spacing=8)

    # ── FILTROS DE VISTA ──────────────────────────────────────────────────────
    botones_filtro = []

    def cambiar_filtro(f):
        estado["filtro"] = f
        for fb in botones_filtro:
            if fb.data == f:
                fb.bgcolor       = ACCENT
                fb.content.color = "#FFFFFF"
            else:
                fb.bgcolor       = SURFACE
                fb.content.color = TEXT_SECONDARY
        cargar_datos(f)

    for op in ["Todos", "Gimnasio", "Comida", "Gastos", "General"]:
        fb = ft.Container(
            data=op,
            content=ft.Text(op, size=12, weight="bold",
                            color="#FFFFFF" if op == "Todos" else TEXT_SECONDARY),
            bgcolor=ACCENT if op == "Todos" else SURFACE,
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            on_click=lambda e, f=op: cambiar_filtro(f),
            ink=True,
        )
        botones_filtro.append(fb)

    fila_filtros = ft.Row(botones_filtro, scroll=ft.ScrollMode.AUTO, spacing=6)

    # ── LAYOUT PRINCIPAL ──────────────────────────────────────────────────────
    page.add(
        # Header
        ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("📓 Mi Bitácora", size=36, weight="bold", color=TEXT_PRIMARY),
                    ft.Text(
                        datetime.now().strftime("%A %d de %B, %Y"),
                        size=16, color=TEXT_SECONDARY,
                    ),
                ], spacing=2),
                ft.Container(expand=True),
                ft.Container(
                    content=balance_texto,
                    bgcolor=CARD_BG,
                    border_radius=11,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                    border=ft.border.all(1, BORDER),
                ),
            ]),
            bgcolor=HEADER_BG,
            padding=ft.Padding.symmetric(horizontal=20, vertical=16),
            border_radius=ft.BorderRadius.only(bottom_left=20, bottom_right=20),
            shadow=ft.BoxShadow(blur_radius=12, color="#00000060", offset=ft.Offset(0, 4)),
        ),

        # Formulario de entrada
        ft.Container(
            content=ft.Column([
                ft.Text("Nueva entrada", size=13, weight="bold", color=TEXT_SECONDARY),
                fila_categorias,
                ft.Row([
                    input_texto,
                    # Botón flecha en lugar de texto
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.ARROW_CIRCLE_RIGHT_ROUNDED,
                            color="#FFFFFF",
                            size=30,
                        ),
                        bgcolor=ACCENT,
                        border_radius=14,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                        on_click=guardar,
                        ink=True,
                    ),
                ], spacing=8),
                input_comida,
                fila_preview,
            ], spacing=10),
            bgcolor=CARD_BG,
            margin=ft.Margin.symmetric(horizontal=12, vertical=10),
            padding=16,
            border_radius=18,
            border=ft.border.all(1, BORDER),
            shadow=ft.BoxShadow(blur_radius=10, color="#00000050", offset=ft.Offset(0, 3)),
        ),

        # Filtros + buscador
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Registros recientes", size=13, weight="bold", color=TEXT_SECONDARY),
                    ft.Container(expand=True),
                    btn_lupa,
                ], alignment=ft.MainAxisAlignment.START),
                input_buscar,
                fila_filtros,
            ], spacing=8),
            padding=ft.Padding.symmetric(horizontal=16, vertical=6),
        ),

        # Lista de registros
        ft.Container(
            content=lista_registros,
            expand=True,
            padding=ft.Padding.symmetric(horizontal=12),
        ),
    )

    cargar_datos()

ft.run(main)
