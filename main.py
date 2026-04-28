import flet as ft
import sqlite3
from datetime import datetime
import re

# --- EXTRACCIÓN DE MONTO CLP (soporta negativos) ---
def extraer_monto_clp(texto):
    texto_lower = texto.lower()
    negativo = False

    if re.match(r'^\s*-', texto_lower):
        negativo = True

    match = re.search(r'-?\s*(\d+)\s*(k|mil|lucas)', texto_lower)
    if match:
        valor = int(match.group(1)) * 1000
        return -valor if negativo else valor

    match_directo = re.search(r'-\s*(\d{4,10})', texto_lower)
    if match_directo:
        return -int(match_directo.group(1))

    match_directo2 = re.search(r'\$?\s*(\d{4,10})', texto_lower)
    if match_directo2:
        return -int(match_directo2.group(1)) if negativo else int(match_directo2.group(1))

    return 0

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect("bitacora.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY,
                    fecha TEXT,
                    texto TEXT,
                    monto INTEGER,
                    categoria TEXT,
                    comida TEXT
                )''')
    conn.commit()
    conn.close()

# --- COLORES POR CATEGORÍA ---
CATEGORIA_COLORES = {
    "Gimnasio": {"bg": "#E8F5E9", "icon": "🏋️", "badge": "#2E7D32"},
    "Comida":   {"bg": "#FFF8E1", "icon": "🍽️", "badge": "#F57F17"},
    "Gastos":   {"bg": "#FFEBEE", "icon": "💸", "badge": "#C62828"},
    "General":  {"bg": "#E3F2FD", "icon": "📋", "badge": "#1565C0"},
}

def main(page: ft.Page):
    page.title = "Mi Bitácora Pro"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F0F2F5"
    page.padding = 0

    init_db()

    # --- ESTADO (sin ft.Ref, usando dict simple) ---
    estado = {"categoria": "General", "filtro": "Todos"}

    # --- COMPONENTES ---
    input_texto = ft.TextField(
        hint_text="Describe tu actividad... (ej: Almorcé pizza, gasté 5k)",
        expand=True,
        border_radius=15,
        bgcolor="white",
        border_color="#BBDEFB",
        focused_border_color="#1A237E",
    )

    input_comida = ft.TextField(
        hint_text="¿Qué comida? (ej: Pizza, Sushi, Completo...)",
        expand=True,
        border_radius=15,
        bgcolor="white",
        border_color="#FFE082",
        focused_border_color="#F57F17",
        visible=False,
    )

    balance_texto = ft.Text("Balance: $ 0", size=18, weight="bold", color="#1A237E")
    lista_registros = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=8)

    # --- BALANCE ---
    def calcular_balance():
        conn = sqlite3.connect("bitacora.db")
        c = conn.cursor()
        c.execute("SELECT SUM(monto) FROM registros")
        total = c.fetchone()[0] or 0
        conn.close()
        return total

    def actualizar_balance():
        total = calcular_balance()
        color = "#2E7D32" if total >= 0 else "#C62828"
        signo = "+" if total > 0 else ""
        balance_texto.value = f"Balance: {signo}$ {abs(total):,}".replace(",", ".")
        balance_texto.color = color

    # --- CARGA DE DATOS ---
    def cargar_datos(filtro="Todos"):
        lista_registros.controls.clear()
        conn = sqlite3.connect("bitacora.db")
        c = conn.cursor()

        if filtro == "Todos":
            c.execute("SELECT texto, fecha, monto, categoria, comida FROM registros ORDER BY id DESC")
        else:
            c.execute("SELECT texto, fecha, monto, categoria, comida FROM registros WHERE categoria=? ORDER BY id DESC", (filtro,))

        rows = c.fetchall()
        conn.close()

        if not rows:
            lista_registros.controls.append(
                ft.Container(
                    content=ft.Text("No hay registros aún.", color="grey", italic=True, text_align=ft.TextAlign.CENTER),
                    alignment=ft.Alignment.CENTER,
                    padding=30,
                )
            )
        else:
            for texto, fecha, monto, categoria, comida in rows:
                cfg = CATEGORIA_COLORES.get(categoria, CATEGORIA_COLORES["General"])

                monto_color = "#2E7D32" if monto > 0 else ("#C62828" if monto < 0 else "grey")
                monto_txt = ""
                if monto > 0:
                    monto_txt = f"+ $ {monto:,}".replace(",", ".")
                elif monto < 0:
                    monto_txt = f"- $ {abs(monto):,}".replace(",", ".")

                comida_chip = ft.Container(
                    content=ft.Text(f"🍽️ {comida}", size=11, color="#F57F17", weight="bold"),
                    bgcolor="#FFF3CD",
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    visible=bool(comida),
                )

                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(cfg["icon"], size=18),
                                bgcolor=cfg["badge"],
                                border_radius=8,
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            ),
                            ft.Text(categoria, size=12, color=cfg["badge"], weight="bold"),
                            ft.Container(expand=True),
                            ft.Text(monto_txt, color=monto_color, weight="bold", size=14),
                        ], alignment=ft.MainAxisAlignment.START),
                        ft.Text(texto, size=15, weight="w500"),
                        ft.Row([
                            comida_chip,
                            ft.Container(expand=True),
                            ft.Text(fecha, size=11, color="grey"),
                        ], alignment=ft.MainAxisAlignment.START),
                    ], spacing=5),
                    bgcolor=cfg["bg"],
                    padding=14,
                    border_radius=14,
                    shadow=ft.BoxShadow(blur_radius=6, color="black12", offset=ft.Offset(0, 2)),
                )
                lista_registros.controls.append(card)

        actualizar_balance()
        page.update()

    # --- GUARDAR ---
    def guardar(e):
        if not input_texto.value.strip():
            return

        texto = input_texto.value.strip()
        monto = extraer_monto_clp(texto)
        
        
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        cat = estado["categoria"]
        comida = input_comida.value.strip() if cat == "Comida" else ""

        conn = sqlite3.connect("bitacora.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO registros (fecha, texto, monto, categoria, comida) VALUES (?, ?, ?, ?, ?)",
            (fecha, texto, monto, cat, comida)
        )
        conn.commit()
        conn.close()

        input_texto.value = ""
        input_comida.value = ""
        cargar_datos(estado["filtro"])

    input_texto.on_submit = guardar

    # --- MENÚ DE CATEGORÍAS ---
    botones_cat = []

    def cambiar_categoria(cat):
        estado["categoria"] = cat
        input_comida.visible = (cat == "Comida")
        for btn in botones_cat:
            cfg = CATEGORIA_COLORES.get(btn.data, CATEGORIA_COLORES["General"])
            if btn.data == cat:
                btn.bgcolor = cfg["badge"]
                btn.content.controls[1].color = "white"
            else:
                btn.bgcolor = cfg["bg"]
                btn.content.controls[1].color = cfg["badge"]
        page.update()

    for cat, cfg in CATEGORIA_COLORES.items():
        es_seleccionado = (cat == estado["categoria"])
        btn = ft.Container(
            data=cat,
            content=ft.Row([
                ft.Text(cfg["icon"], size=14),
                ft.Text(cat, size=13, weight="bold",
                        color="white" if es_seleccionado else cfg["badge"]),
            ], spacing=4, tight=True),
            bgcolor=cfg["badge"] if es_seleccionado else cfg["bg"],
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=12, vertical=7),
            on_click=lambda e, c=cat: cambiar_categoria(c),
            ink=True,
        )
        botones_cat.append(btn)

    fila_categorias = ft.Row(botones_cat, scroll=ft.ScrollMode.AUTO, spacing=8)

    # --- FILTROS DE VISTA ---
    botones_filtro = []

    def cambiar_filtro(f):
        estado["filtro"] = f
        for fb in botones_filtro:
            if fb.data == f:
                fb.bgcolor = "#1A237E"
                fb.content.color = "white"
            else:
                fb.bgcolor = "#E8EAF6"
                fb.content.color = "#1A237E"
        cargar_datos(f)

    for op in ["Todos", "Gimnasio", "Comida", "Gastos", "General"]:
        fb = ft.Container(
            data=op,
            content=ft.Text(op, size=12, weight="bold",
                            color="white" if op == "Todos" else "#1A237E"),
            bgcolor="#1A237E" if op == "Todos" else "#E8EAF6",
            border_radius=15,
            padding=ft.padding.symmetric(horizontal=11, vertical=6),
            on_click=lambda e, f=op: cambiar_filtro(f),
            ink=True,
        )
        botones_filtro.append(fb)

    fila_filtros = ft.Row(botones_filtro, scroll=ft.ScrollMode.AUTO, spacing=6)

    # --- LAYOUT PRINCIPAL ---
    page.add(
        # Header
        ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("📓 Mi Bitácora", size=26, weight="bold", color="white"),
                    ft.Text(datetime.now().strftime("%A %d de %B, %Y"), size=12, color="#90CAF9"),
                ], spacing=2),
                ft.Container(expand=True),
                ft.Container(
                    content=balance_texto,
                    bgcolor="#0D1B6E",
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                ),
            ]),
            bgcolor="#1A237E",
            padding=ft.padding.symmetric(horizontal=20, vertical=18),
            border_radius=ft.border_radius.only(bottom_left=20, bottom_right=20),
        ),

        # Formulario de ingreso
        ft.Container(
            content=ft.Column([
                ft.Text("Nueva entrada", size=14, weight="bold", color="#455A64"),
                fila_categorias,
                ft.Row([input_texto], spacing=8),
                input_comida,
                ft.Row([
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color="white", size=18),
                            ft.Text("Guardar", color="white", weight="bold"),
                        ], tight=True, spacing=6),
                        on_click=guardar,
                        bgcolor="#1A237E",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    )
                ]),
            ], spacing=10),
            bgcolor="white",
            margin=ft.margin.symmetric(horizontal=12, vertical=10),
            padding=16,
            border_radius=18,
            shadow=ft.BoxShadow(blur_radius=10, color="black12", offset=ft.Offset(0, 3)),
        ),

        # Filtros de vista
        ft.Container(
            content=ft.Column([
                ft.Text("Registros recientes", size=14, weight="bold", color="#455A64"),
                fila_filtros,
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
        ),

        # Lista de registros
        ft.Container(
            content=lista_registros,
            expand=True,
            padding=ft.padding.symmetric(horizontal=12),
        ),
    )

    cargar_datos()

ft.app(target=main)