# -*- coding: utf-8 -*-
"""
Generador de Estados de WhatsApp - Diagnóstico Citopatológico INLE, C.A.
Versión Final Perfeccionada:
- Incluye textualmente los 6 "Procesamientos de:" del cartel original:
  • Citomorfológico
  • Bloque celulares
  • Tipificación de VPH
  • Inmunohistoquímica
  • Citologías
  • Biopsias
- CERO texto amontonado: estructura espaciosa con 30-40px de separación entre bloques.
- ZONA SEGURA DE WHATSAPP:
  * Superior (0 a 195 px): libre de texto para foto de perfil, nombre y hora.
  * Inferior (1630 a 1920 px): libre de texto para barra de responder y botones de like/reacción.
  * Área útil: Y = 195 a Y = 1630 px.
- Paleta Oficial: Verde Institucional (#1b6b3e) + Rojo Vinotinto (#881c2c) + Blanco Limpio.
- Silueta de Microscopio claramente perceptible (18% opacidad).
"""

import os
import sys
import json
import urllib.request
import datetime
from PIL import Image, ImageDraw, ImageFont

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "estados_hoy")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Buscar logo en BASE_DIR primero o en las carpetas hermanas
LOGO_PATH = os.path.join(BASE_DIR, "logo_oficial.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(BASE_DIR, "..", "PAGINA_WEB_INLE", "assets", "logo_oficial.png")

# Colores Oficiales INLE
COLOR_VERDE = "#1b6b3e"        # Verde institucional clínico
COLOR_VINOTINTO = "#881c2c"    # Rojo vinotinto oficial
COLOR_VINOTINTO_BG = "#fdf2f4" # Fondo suave vinotinto
COLOR_VERDE_BG = "#f0fdf4"     # Fondo suave verde
COLOR_TEXTO_OSCURO = "#09101d" # Carbón oscuro nítido
COLOR_GRIS_MEDIO = "#4b5563"   # Gris medio legible

def get_font(name="segoeuib.ttf", size=36):
    """Busca fuentes en Windows o en Linux (Ubuntu) transparentemente."""
    # 1. En Windows
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
    if os.path.exists(win_fonts):
        p = os.path.join(win_fonts, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, int(size))
        p_alt = os.path.join(win_fonts, "arialbd.ttf" if "b" in name else "arial.ttf")
        if os.path.exists(p_alt):
            return ImageFont.truetype(p_alt, int(size))

    # 2. En Linux / Ubuntu
    linux_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for lp in linux_candidates:
        if os.path.exists(lp):
            try:
                return ImageFont.truetype(lp, int(size))
            except Exception:
                pass

    return ImageFont.load_default()

def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=int(width))

def formatear_monto_ve(monto):
    parts = f"{monto:,.2f}".split(".")
    entero = parts[0].replace(",", ".")
    decimal = parts[1]
    return f"{entero},{decimal}"

def get_microscope_watermark(size=(1050, 1050), opacity=0.18):
    """Marca de agua del microscopio bien visible con opacidad estética del 18%."""
    if not os.path.exists(LOGO_PATH):
        return None
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        alpha = logo.split()[3]
        tinted = Image.new("RGBA", logo.size, (27, 107, 62, int(255 * opacity)))
        watermark = Image.composite(tinted, Image.new("RGBA", logo.size, (0, 0, 0, 0)), alpha)
        return watermark.resize(size, Image.Resampling.LANCZOS)
    except Exception:
        return None

def obtener_tasas_bcv():
    tasas = {
        "usd": 896.12,
        "eur": 1004.96,
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d"),
        "fecha_texto": "Viernes, 06 de Noviembre de 2026"
    }

    dias_semana = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    meses = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    ahora = datetime.datetime.now()
    tasas["fecha_texto"] = f"{dias_semana[ahora.weekday()]}, {ahora.day:02d} de {meses[ahora.month]} de {ahora.year}"

    try:
        req_usd = urllib.request.Request("https://ve.dolarapi.com/v1/dolares/oficial", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_usd, timeout=5) as response:
            data_usd = json.loads(response.read().decode('utf-8'))
            tasas["usd"] = round(float(data_usd.get("promedio", 896.12)), 2)

        req_eur = urllib.request.Request("https://ve.dolarapi.com/v1/euros/oficial", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_eur, timeout=5) as response:
            data_eur = json.loads(response.read().decode('utf-8'))
            tasas["eur"] = round(float(data_eur.get("promedio", 1004.96)), 2)
        print(f"[OK] Tasas obtenidas online: USD {tasas['usd']} Bs | EUR {tasas['eur']} Bs")
    except Exception:
        print("[Aviso] Usando tasas oficiales registradas en el sistema.")

    with open(os.path.join(BASE_DIR, "ultima_tasa_bcv.json"), "w", encoding="utf-8") as f:
        json.dump(tasas, f, ensure_ascii=False, indent=2)

    return tasas

def crear_lienzo_base():
    """Lienzo blanco con detalles verde/vinotinto y silueta de microscopio visible."""
    img = Image.new("RGBA", (1080, 1920), "#ffffff")
    draw = ImageDraw.Draw(img)

    # Franjas decorativas
    draw.rectangle([(0, 0), (540, 14)], fill=COLOR_VERDE)
    draw.rectangle([(540, 0), (1080, 14)], fill=COLOR_VINOTINTO)

    # Silueta de microscopio
    wm = get_microscope_watermark(size=(1050, 1050), opacity=0.18)
    if wm:
        img.paste(wm, (540 - wm.width // 2, 600), wm)

    draw.rectangle([(0, 1906), (540, 1920)], fill=COLOR_VINOTINTO)
    draw.rectangle([(540, 1906), (1080, 1920)], fill=COLOR_VERDE)

    return img, draw

def dibujar_cabecera_zona_segura(img, draw):
    """Cabecera institucional ubicada a partir de Y = 195 px."""
    y_logo = 195
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
            draw.ellipse([(475, y_logo), (605, y_logo + 130)], fill="#ffffff", outline=COLOR_VINOTINTO, width=3)
            img.paste(logo, (540 - logo.width // 2, y_logo + 65 - logo.height // 2), logo)
        except Exception:
            pass

    font_brand = get_font("segoeuib.ttf", 38)
    font_sub = get_font("segoeuib.ttf", 26)
    draw.text((540, 340), "DIAGNÓSTICO CITOPATOLÓGICO INLE, C.A.", fill=COLOR_TEXTO_OSCURO, font=font_brand, anchor="mt")
    draw.text((540, 385), "Dra. Aramís Romero Jurgensen • Médico Anatomopatólogo", fill=COLOR_VINOTINTO, font=font_sub, anchor="mt")

def dibujar_pie_zona_segura(draw, y_top=1455):
    """
    Pie posicionado entre Y = 1455 y Y = 1630 px.
    Deja 290 px LIBRES al final para que la barra de WhatsApp no tape nada.
    """
    draw_rounded_rect(draw, [(50, y_top), (1030, y_top + 175)], radius=24, fill="#ffffff", outline=COLOR_VERDE, width=2.5)
    font_dir = get_font("segoeuib.ttf", 26)
    font_tel = get_font("segoeuib.ttf", 38)
    draw.text((540, y_top + 25), "Av. Bicentenario, Edif. Multicentro Profesional, Piso Mezzanina Local 03", fill=COLOR_TEXTO_OSCURO, font=font_dir, anchor="mt")
    draw.text((540, y_top + 85), "📞 (0426) 960.18.58  •  (0291) 317.97.30", fill=COLOR_VINOTINTO, font=font_tel, anchor="mt")


# ==============================================================================
# ESTADO 1: TASA BCV DEL DÍA (Cero Amontonamiento)
# ==============================================================================
def generar_estado_tasa_bcv(tasas):
    img, draw = crear_lienzo_base()
    dibujar_cabecera_zona_segura(img, draw)

    # 1. Cinta Vinotinto: BANCO CENTRAL DE VENEZUELA
    draw_rounded_rect(draw, [(50, 430), (1030, 535)], radius=22, fill=COLOR_VINOTINTO)
    draw.text((540, 452), "BANCO CENTRAL DE VENEZUELA", fill="#ffffff", font=get_font("segoeuib.ttf", 38), anchor="mt")
    draw.text((540, 498), "TIPO DE CAMBIO OFICIAL DE REFERENCIA", fill="#fecdd3", font=get_font("segoeuib.ttf", 26), anchor="mt")

    # 2. Fecha Valor
    draw_rounded_rect(draw, [(50, 550), (1030, 625)], radius=18, fill=COLOR_VERDE_BG, outline=COLOR_VERDE, width=2)
    draw.text((540, 560), "FECHA VALOR OFICIAL:", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeui.ttf", 20), anchor="mt")
    draw.text((540, 586), tasas.get("fecha_texto", "").upper(), fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 28), anchor="mt")

    # 3. Tarjeta DÓLAR USD (Monto 96px)
    draw_rounded_rect(draw, [(50, 645), (1030, 885)], radius=26, fill="#ffffff", outline=COLOR_VERDE, width=3.5)
    draw.ellipse([(85, 685), (215, 815)], fill=COLOR_VERDE)
    draw.text((150, 750), "$", fill="#ffffff", font=get_font("segoeuib.ttf", 80), anchor="mm")

    draw.text((245, 680), "DÓLAR OFICIAL (USD)", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 34))
    monto_usd_str = formatear_monto_ve(tasas["usd"])
    draw.text((245, 730), monto_usd_str, fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 96))
    pos_bs_x = 245 + get_font("segoeuib.ttf", 96).getbbox(monto_usd_str)[2] + 20
    draw.text((pos_bs_x, 780), "Bs.", fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 50))
    draw.text((245, 845), "1 USD = Tasa oficial promedio del BCV", fill=COLOR_GRIS_MEDIO, font=get_font("segoeui.ttf", 24))

    # 4. Tarjeta EURO EUR (Monto 96px)
    draw_rounded_rect(draw, [(50, 905), (1030, 1145)], radius=26, fill="#ffffff", outline=COLOR_VINOTINTO, width=3.5)
    draw.ellipse([(85, 945), (215, 1075)], fill=COLOR_VINOTINTO)
    draw.text((150, 1010), "€", fill="#ffffff", font=get_font("segoeuib.ttf", 80), anchor="mm")

    draw.text((245, 940), "EURO OFICIAL (EUR)", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 34))
    monto_eur_str = formatear_monto_ve(tasas["eur"])
    draw.text((245, 990), monto_eur_str, fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 96))
    pos_eur_bs = 245 + get_font("segoeuib.ttf", 96).getbbox(monto_eur_str)[2] + 20
    draw.text((pos_eur_bs, 1040), "Bs.", fill=COLOR_VINOTINTO, font=get_font("segoeuib.ttf", 50))
    draw.text((245, 1105), "1 EUR = Tasa de cambio oficial publicada por el BCV", fill=COLOR_GRIS_MEDIO, font=get_font("segoeui.ttf", 24))

    # 5. Métodos de Pago a Tasa BCV (Espaciado amplio)
    draw_rounded_rect(draw, [(50, 1165), (1030, 1435)], radius=24, fill=COLOR_VERDE_BG, outline=COLOR_VERDE, width=2.5)
    draw.text((540, 1188), "💳 MÉTODOS DE PAGO A TASA BCV", fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 34), anchor="mt")
    
    txt_items = [
        ("• Pago Móvil y Transferencias Bancarias", COLOR_TEXTO_OSCURO),
        ("• Punto de Venta con Tarjeta de Débito en Sede", COLOR_TEXTO_OSCURO),
        ("• Efectivo Divisas ($ / €) o Bolívares en Efectivo", COLOR_VINOTINTO)
    ]
    y_p = 1242
    for item, col in txt_items:
        draw.text((95, y_p), item, fill=col, font=get_font("segoeuib.ttf", 30))
        y_p += 48
    draw.text((540, 1395), "Facturación exacta a la tasa oficial del día", fill=COLOR_GRIS_MEDIO, font=get_font("segoeui.ttf", 24), anchor="mt")

    dibujar_pie_zona_segura(draw, y_top=1455)

    out_path = os.path.join(OUTPUT_DIR, "01_TASA_BCV_HOY.png")
    img.save(out_path, "PNG", quality=95)
    print(f"[OK] Generado: {out_path}")
    return out_path


# ==============================================================================
# ESTADO 2: SEDE OFICIAL Y UBICACIÓN (2 Bloques Amplios y Espaciosos)
# ==============================================================================
def generar_estado_sede_recepcion():
    img, draw = crear_lienzo_base()
    dibujar_cabecera_zona_segura(img, draw)

    # Banner Título Verde
    draw_rounded_rect(draw, [(50, 430), (1030, 535)], radius=22, fill=COLOR_VERDE)
    draw.text((540, 452), "SEDE CENTRAL Y RECEPCIÓN OFICIAL", fill="#ffffff", font=get_font("segoeuib.ttf", 38), anchor="mt")
    draw.text((540, 498), "Recepción de Muestras y Entrega de Informes", fill="#d1fae5", font=get_font("segoeuib.ttf", 26), anchor="mt")

    # Tarjeta 1: DIRECCIÓN Y PUNTOS DE REFERENCIA (Unificada y Espaciosa)
    draw_rounded_rect(draw, [(50, 555), (1030, 1005)], radius=26, fill="#ffffff", outline=COLOR_VERDE, width=2.5)
    draw.text((95, 580), "🏢 DIRECCIÓN Y PUNTOS DE REFERENCIA", fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 34))
    draw.text((95, 630), "Av. Bicentenario, Edif. Multicentro Profesional Bicentenario", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 30))
    
    # Destacado Piso Mezzanina en Vinotinto
    draw_rounded_rect(draw, [(95, 678), (985, 765)], radius=18, fill=COLOR_VINOTINTO_BG, outline=COLOR_VINOTINTO, width=2.5)
    draw.text((540, 698), "PISO MEZZANINA (MZN), LOCAL 03", fill=COLOR_VINOTINTO, font=get_font("segoeuib.ttf", 40), anchor="mt")
    
    draw.text((95, 785), "👉 Justo al subir la escalera principal de acceso", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 30))
    
    # Línea divisoria suave
    draw.line([(95, 835), (985, 835)], fill="#e2e8f0", width=2)

    draw.text((95, 855), "📍 Cerca del Hospital Manuel Núñez Tovar", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 32))
    draw.text((95, 910), "📍 Al lado de Comercial COBY y Agencia MRW", fill=COLOR_VINOTINTO, font=get_font("segoeuib.ttf", 32))
    draw.text((95, 960), "Zona céntrica de fácil acceso con estacionamiento", fill=COLOR_GRIS_MEDIO, font=get_font("segoeui.ttf", 25))

    # Tarjeta 2: HORARIO DE ATENCIÓN CORRIDO (Amplia y sin apretar)
    draw_rounded_rect(draw, [(50, 1030), (1030, 1430)], radius=26, fill=COLOR_VERDE_BG, outline=COLOR_VERDE, width=2.5)
    draw.text((95, 1055), "⏰ HORARIOS DE ATENCIÓN (JORNADA CORRIDA)", fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 34))
    draw.text((95, 1115), "• Lunes a Viernes:  8:30 AM a 5:30 PM", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 36))
    draw.text((125, 1165), "(Abierto al mediodía para recepción de muestras)", fill=COLOR_VINOTINTO, font=get_font("segoeuib.ttf", 28))
    draw.text((95, 1220), "• Sábados:  9:00 AM a 1:00 PM  (Domingos: Cerrado)", fill=COLOR_TEXTO_OSCURO, font=get_font("segoeuib.ttf", 32))
    
    # Mensaje de Cierre
    draw_rounded_rect(draw, [(95, 1290), (985, 1375)], radius=16, fill="#ffffff", outline=COLOR_VINOTINTO, width=2)
    draw.text((540, 1315), "🤝 ¡Gracias por preferirnos! Criterio de especialista.", fill=COLOR_VINOTINTO, font=get_font("segoeuib.ttf", 30), anchor="mt")

    dibujar_pie_zona_segura(draw, y_top=1455)

    out_path = os.path.join(OUTPUT_DIR, "02_SEDE_Y_RECEPCION_OFICIAL.png")
    img.save(out_path, "PNG", quality=95)
    print(f"[OK] Generado: {out_path}")
    return out_path


# ==============================================================================
# ESTADO 3: SERVICIOS CON LOS 6 "PROCESAMIENTOS DE:" EN LETRAS EXTRA GRANDES
# ==============================================================================
def generar_estado_servicios():
    img, draw = crear_lienzo_base()
    dibujar_cabecera_zona_segura(img, draw)

    # Banner Título Vinotinto
    draw_rounded_rect(draw, [(50, 425), (1030, 530)], radius=22, fill=COLOR_VINOTINTO)
    draw.text((540, 448), "ESTUDIOS CITOPATOLÓGICOS", fill="#ffffff", font=get_font("segoeuib.ttf", 40), anchor="mt")
    draw.text((540, 495), "Evaluación con Estricto Criterio Anatomopatológico", fill="#fecdd3", font=get_font("segoeuib.ttf", 26), anchor="mt")

    # Tarjeta Principal: LOS 6 "PROCESAMIENTOS DE:" EN LETRAS GIGANTES Y HOLGADAS
    # Y: 555 a 1260 (Altura 705px, con más de 95px de altura por línea y cero amontonamiento)
    draw_rounded_rect(draw, [(50, 555), (1030, 1260)], radius=26, fill="#ffffff", outline=COLOR_VERDE, width=2.5)
    
    # Encabezado "Procesamientos de:"
    draw.text((100, 580), "🔬 Procesamientos de:", fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 42))
    draw.line([(100, 635), (980, 635)], fill="#e2e8f0", width=2)

    # Los 6 ítems exactos del cartel en LETRAS EXTRA GRANDES (48px BOLD)
    lista_procesamientos = [
        ("• Citomorfológico", COLOR_TEXTO_OSCURO),
        ("• Bloque celulares", COLOR_VINOTINTO),
        ("• Tipificación de VPH", COLOR_TEXTO_OSCURO),
        ("• Inmunohistoquímica", COLOR_VINOTINTO),
        ("• Citologías", COLOR_TEXTO_OSCURO),
        ("• Biopsias", COLOR_VINOTINTO)
    ]

    font_item = get_font("segoeuib.ttf", 48)
    y_item = 665
    for item_texto, color_item in lista_procesamientos:
        # Fila sutil tipo listado clínico limpio
        draw.text((110, y_item), item_texto, fill=color_item, font=font_item)
        y_item += 95

    # Banner "ESTAMOS A SU SERVICIO" (Holgado, Y: 1285 a 1445 px)
    draw_rounded_rect(draw, [(50, 1285), (1030, 1445)], radius=24, fill=COLOR_VERDE_BG, outline=COLOR_VERDE, width=3)
    draw.text((540, 1310), "✨ ESTAMOS A SU SERVICIO", fill=COLOR_VERDE, font=get_font("segoeuib.ttf", 42), anchor="mt")
    draw.text((540, 1375), "Más de 48.400 Casos Evaluados • 20+ Años de Experiencia", fill=COLOR_VINOTINTO, font=get_font("segoeuib.ttf", 28), anchor="mt")

    # Pie institucional (termina en Y = 1630 px, dejando 290px libres al final)
    dibujar_pie_zona_segura(draw, y_top=1470)

    out_path = os.path.join(OUTPUT_DIR, "03_SERVICIOS_ESPECIALIZADOS.png")
    img.save(out_path, "PNG", quality=95)
    print(f"[OK] Generado: {out_path}")
    return out_path


def generar_todos_los_estados():
    print("=" * 65)
    print(" GENERANDO ESTADOS OFICIALES PERFECCIONADOS (1080 x 1920)")
    print(" Diagnóstico Citopatológico INLE, C.A.")
    print("=" * 65)

    tasas = obtener_tasas_bcv()
    rutas = [
        generar_estado_tasa_bcv(tasas),
        generar_estado_sede_recepcion(),
        generar_estado_servicios()
    ]

    print("\n[ÉXITO] Se generaron los 3 estados oficiales:")
    for r in rutas:
        print(f" -> {r}")
    return rutas

if __name__ == "__main__":
    generar_todos_los_estados()
