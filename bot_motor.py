# -*- coding: utf-8 -*-
"""
Motor de Procesamiento del Bot de WhatsApp para Diagnóstico Citopatológico INLE, C.A.
Dra. Aramís Romero Jurgensen - Maturín, Monagas
Incluye Normalizador Fonético Venezolano de alta tolerancia a errores de tipeo y abreviaturas.
"""

import os
import sys
import json
import unicodedata
import re

# Asegurar salida UTF-8 en terminales Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESPUESTAS_PATH = os.path.join(BASE_DIR, "respuestas.json")

def cargar_respuestas():
    with open(RESPUESTAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# Diccionario de abreviaturas y modismos comunes en WhatsApp venezolano
REEMPLAZOS_COLOQUIALES = {
    r'\bq\b': 'que',
    r'\bk\b': 'que',
    r'\bpq\b': 'porque',
    r'\bxq\b': 'porque',
    r'\bxk\b': 'porque',
    r'\bxfa\b': 'por favor',
    r'\bx\s*favor\b': 'por favor',
    r'\bcto\b': 'cuanto',
    r'\bcuanto sale\b': 'precio',
    r'\bcuanto vale\b': 'precio',
    r'\bque vale\b': 'precio',
    r'\bque sale\b': 'precio',
    r'\bq sale\b': 'precio',
    r'\bq cuesta\b': 'precio',
    r'\bq vale\b': 'precio',
    r'\bq cobran\b': 'precio',
    r'\bcuanto cobran\b': 'precio',
    r'\btiene costo\b': 'precio',
    r'\btiene precio\b': 'precio',
    r'\btarifa\b': 'precio',
    r'\btarifas\b': 'precio',
    r'\btasa\b': 'precio',
    r'\bbcv\b': 'precio',
    r'\bdivisa\b': 'precio',
    r'\bdivisas\b': 'precio',
    r'\bdolar\b': 'precio',
    r'\bdolares\b': 'precio',
    r'\bdls\b': 'precio',
    r'\bbolivares\b': 'precio',
    r'\bbs\b': 'precio',
    r'\bbss\b': 'precio',
    r'\bpago\s*movil\b': 'precio',
    r'\bpunto\s*de\s*venta\b': 'precio',
    r'\bzelle\b': 'precio',
    r'\btransferencia\b': 'precio',
    r'\befectivo\b': 'precio',
    r'\bmetodos\s*de\s*pago\b': 'precio',
    r'\bformas\s*de\s*pago\b': 'precio',

    # Tiempos de entrega
    r'\bcuanto\s+tarda\b': 'tiempo',
    r'\bcuantos\s+dias\b': 'tiempo',
    r'\bcuando\s+esta\b': 'tiempo',
    r'\bcuando\s+entregan\b': 'tiempo',
    r'\bcuando\s+me\s+lo\s+entregan\b': 'tiempo',
    r'\bcuanto\s+se\s+tarda\b': 'tiempo',
    r'\bcuanto\s+dura\b': 'tiempo',
    r'\bpara\s+cuando\s+esta\b': 'tiempo',
    r'\bdias\s+de\s+entrega\b': 'tiempo',
    r'\blapso\b': 'tiempo',
    r'\btardan\b': 'tiempo',
    r'\btardanza\b': 'tiempo',
    r'\bdemora\b': 'tiempo',

    # Errores en Biopsia
    r'\bbiopcia\b': 'biopsia',
    r'\bbiopcias\b': 'biopsia',
    r'\bviopsia\b': 'biopsia',
    r'\bviopcia\b': 'biopsia',
    r'\bbiobcia\b': 'biopsia',
    r'\bpedacito\b': 'biopsia',
    r'\bcarnecita\b': 'biopsia',
    r'\btejido\b': 'biopsia',
    r'\bpolipo\b': 'biopsia',
    r'\blunar\b': 'biopsia',
    r'\bvesicula\b': 'biopsia',
    r'\bapendice\b': 'biopsia',
    r'\bgastrica\b': 'biopsia',
    r'\bestomago\b': 'biopsia',

    # Errores en Citología
    r'\bsitologia\b': 'citologia',
    r'\bsitologias\b': 'citologia',
    r'\bcitolojia\b': 'citologia',
    r'\bsitolojia\b': 'citologia',
    r'\bcervical\b': 'citologia',
    r'\bpap\b': 'citologia',
    r'\bpapanicolau\b': 'citologia',
    r'\bpapanicolaou\b': 'citologia',
    r'\bpapanicolao\b': 'citologia',
    r'\bfrotis\b': 'citologia',
    r'\bvph\b': 'citologia',
    r'\bflujo\b': 'citologia',

    # Errores en Ubicación y Horarios
    r'\borario\b': 'horario',
    r'\borarios\b': 'horario',
    r'\ba\s*q\s*hora\b': 'horario',
    r'\ba\s*que\s*hora\b': 'horario',
    r'\babren\b': 'horario',
    r'\bcierran\b': 'horario',
    r'\bsavado\b': 'horario',
    r'\bsavados\b': 'horario',
    r'\bsabado\b': 'horario',
    r'\bsabados\b': 'horario',
    r'\bdomingo\b': 'horario',
    r'\bmedio\s*dia\b': 'horario',
    r'\balmuerzo\b': 'horario',
    r'\bestan\s*abiertos\b': 'horario',
    r'\bestan\s*trabajando\b': 'horario',
    r'\bastan\s*abiertos\b': 'horario',

    r'\bubicasion\b': 'ubicacion',
    r'\bubicasio\b': 'ubicacion',
    r'\bdirecion\b': 'ubicacion',
    r'\bdon\s*d\b': 'donde',
    r'\bdond\b': 'donde',
    r'\bkeda\b': 'queda',
    r'\bqda\b': 'queda',
    r'\bmulticentro\b': 'ubicacion',
    r'\bbicentenario\b': 'ubicacion',
    r'\bcomo\s+llego\b': 'ubicacion',
    r'\bcroquis\b': 'ubicacion',
    r'\bmapa\b': 'ubicacion',
    r'\bmaps\b': 'ubicacion',
    r'\bsede\b': 'ubicacion',
    r'\bdireccion\b': 'ubicacion',

    # Frasco y Formol
    r'\bformolito\b': 'formol',
    r'\bformalina\b': 'formol',
    r'\bfrasquito\b': 'frasco',
    r'\benvase\b': 'frasco',
    r'\bpote\b': 'frasco',
    r'\bpotecito\b': 'frasco',
    r'\bliquido\s*para\s*la\s*muestra\b': 'formol',
    r'\bcomo\s*llevo\b': 'requisitos',
    r'\bcomo\s*entrego\b': 'requisitos',
    r'\bque\s*se\s*necesita\b': 'requisitos',
    r'\bque\s*piden\b': 'requisitos',
    r'\borden\s*medica\b': 'requisitos',
    r'\brequisitos\b': 'requisitos',
    r'\brequisito\b': 'requisitos',

    # Resultados e Informes
    r'\bresultao\b': 'resultado',
    r'\bresultaos\b': 'resultado',
    r'\bresultados\b': 'resultado',
    r'\bresultado\b': 'resultado',
    r'\binforme\b': 'resultado',
    r'\binformes\b': 'resultado',
    r'\bya\s*salio\b': 'resultado',
    r'\bya\s*esta\s*listo\b': 'resultado',
    r'\bya\s*ta\s*listo\b': 'resultado',
    r'\besta\s*listo\b': 'resultado',
    r'\bretiro\b': 'resultado',
    r'\bretirar\b': 'resultado',
    r'\bmi\s*examen\b': 'resultado',

    # Doctora y contacto humano
    r'\bdra\b': 'doctora',
    r'\bdoctor\b': 'doctora',
    r'\baramis\b': 'doctora',
    r'\barami\b': 'doctora',
    r'\bpatologo\b': 'doctora',
    r'\bpatologa\b': 'doctora',
    r'\bsecretaria\b': 'doctora',
    r'\basistente\b': 'doctora',
    r'\bpersona\b': 'doctora',
    r'\bhumano\b': 'doctora',
    r'\bhablar\b': 'doctora',
    r'\bllamar\b': 'doctora',
    r'\btlf\b': 'telefono',
    r'\bnumero\b': 'telefono',

    # Saludos venezolanos comunes
    r'\bepale\b': 'hola',
    r'\bola\b': 'hola',
    r'\bholas\b': 'hola',
    r'\bbns\b': 'buenas',
    r'\bbnas\b': 'buenas',
    r'\bbuenas\s*tardes\b': 'buenas',
    r'\bbuenas\s*noches\b': 'buenas',
    r'\bbuen\s*dia\b': 'buenas',
    r'\bbuenos\s*dias\b': 'buenas',
    r'\bsaludos\b': 'hola',
    r'\bque\s*tal\b': 'hola',
}

def normalizar_texto_robusto(texto):
    """
    Normaliza el texto quitando acentos, caracteres especiales,
    resolviendo abreviaturas coloquiales y tolerando errores de ortografía.
    """
    if not texto:
        return ""
    
    # 1. Pasar a minúsculas
    txt = texto.lower().strip()
    
    # 2. Descomponer y quitar tildes
    txt = unicodedata.normalize('NFKD', txt).encode('ascii', 'ignore').decode('utf-8')
    
    # 3. Quitar signos de puntuación (dejar solo letras, números y espacios)
    txt = re.sub(r'[^a-z0-9\s]', ' ', txt)
    
    # 4. Normalizar espacios múltiples
    txt = ' '.join(txt.split())
    
    # 5. Aplicar reemplazos de modismos y abreviaturas (las frases más largas primero para evitar falsos cortes)
    patrones_ordenados = sorted(REEMPLAZOS_COLOQUIALES.items(), key=lambda x: len(x[0]), reverse=True)
    for patron, reemplazo in patrones_ordenados:
        txt = re.sub(patron, reemplazo, txt)
        
    # Limpieza final de espacios
    return ' '.join(txt.split())

def responder_mensaje(mensaje_usuario):
    """
    Analiza el mensaje normalizado del paciente y clasifica la intención con altísima tolerancia.
    """
    respuestas = cargar_respuestas()
    limpio = normalizar_texto_robusto(mensaje_usuario)

    if not limpio:
        return respuestas.get("menu_principal")

    # -------------------------------------------------------------
    # 1. NUMÉRICOS DIRECTOS (Menú)
    # -------------------------------------------------------------
    if limpio in ['0', 'menu', 'inicio', 'empezar', 'opciones']:
        return respuestas.get("menu_principal")
    if limpio == '1':
        return respuestas.get("opcion_1_servicios")
    if limpio == '2':
        return respuestas.get("precios_info")
    if limpio == '3':
        return respuestas.get("recepcion_foto_muestra")
    if limpio == '4':
        return respuestas.get("tiempos_entrega")
    if limpio == '5':
        return respuestas.get("opcion_2_requisitos")
    if limpio == '6':
        return respuestas.get("opcion_3_horarios_ubicacion")
    if limpio == '7':
        return respuestas.get("opcion_4_consulta_informe")
    if limpio == '8':
        return respuestas.get("opcion_5_atencion_humana")

    # -------------------------------------------------------------
    # 2. FOTOS DE ÓRDENES MÉDICAS Y FRASCOS DE MUESTRAS
    # -------------------------------------------------------------
    palabras_foto = ['foto', 'imagen', 'adjunto', 'adjunta', 'captura', 'orden medica', 'frasco de muestra', 'foto muestra', 'foto orden']
    if any(p in limpio for p in palabras_foto):
        return respuestas.get("recepcion_foto_muestra")

    # -------------------------------------------------------------
    # 2. PRECIOS, COSTOS, PRESUPUESTO Y MÉTODOS DE PAGO
    # -------------------------------------------------------------
    palabras_precios = [
        'precio', 'precios', 'costo', 'costos', 'presupuesto', 'cotizacion', 'dolar', 'dls', 'bolivares', 
        'pago', 'pagar', 'cuanto', 'tarifa', 'tarifas', 'punto', 'zelle', 'transferencia', 'bcv',
        'efectivo', 'pago movil', 'divisa', 'divisas', 'cuesta', 'cuestan', 'vale', 'valen', 'cobran', 'cobra'
    ]
    if any(p in limpio for p in palabras_precios):
        return respuestas.get("precios_info")

    # -------------------------------------------------------------
    # 3. TIEMPOS DE ENTREGA Y CUÁNTO TARDA
    # -------------------------------------------------------------
    palabras_tiempo = [
        'tiempo', 'dias', 'tarda', 'tardanza', 'demora', 'cuando entregan', 
        'cuanto dura', 'lapso', 'cuantos dias'
    ]
    if any(p in limpio for p in palabras_tiempo):
        return respuestas.get("tiempos_entrega")

    # -------------------------------------------------------------
    # 4. REQUISITOS DE MUESTRAS, FRASCO Y FORMOL
    # -------------------------------------------------------------
    palabras_requisitos = [
        'requisitos', 'formol', 'frasco', 'fijador', 'conservar', 'orden', 
        'llevar muestra', 'entregar muestra', 'alcohol', 'suero'
    ]
    if any(p in limpio for p in palabras_requisitos):
        return respuestas.get("opcion_2_requisitos")

    # -------------------------------------------------------------
    # 5. HORARIOS Y UBICACIÓN
    # -------------------------------------------------------------
    palabras_horarios = [
        'horario', 'hora', 'abren', 'cierran', 'sabado', 'domingo', 'medio dia', 
        'almuerzo', 'abierto'
    ]
    palabras_ubicacion = [
        'ubicacion', 'donde', 'queda', 'direccion', 'llegar', 'sede', 'multicentro', 
        'bicentenario', 'maturin', 'mapa', 'maps', 'croquis'
    ]
    if any(p in limpio for p in palabras_horarios) or any(p in limpio for p in palabras_ubicacion):
        return respuestas.get("opcion_3_horarios_ubicacion")

    # -------------------------------------------------------------
    # 6. CONSULTA DE RESULTADOS O INFORMES LISTOS
    # -------------------------------------------------------------
    palabras_resultados = [
        'resultado', 'informe', 'listo', 'retiro', 'retirar', 'salio', 'examen'
    ]
    if any(p in limpio for p in palabras_resultados):
        return respuestas.get("opcion_4_consulta_informe")

    # -------------------------------------------------------------
    # 7. ATENCIÓN HUMANA / DRA. ARAMÍS
    # -------------------------------------------------------------
    palabras_humanas = [
        'doctora', 'aramis', 'patologo', 'secretaria', 'asistente', 'humano', 
        'persona', 'hablar', 'llamar', 'telefono', 'contacto'
    ]
    if any(p in limpio for p in palabras_humanas):
        return respuestas.get("opcion_5_atencion_humana")

    # -------------------------------------------------------------
    # 8. SERVICIOS Y ESTUDIOS EN GENERAL
    # -------------------------------------------------------------
    palabras_servicios = [
        'servicio', 'servicios', 'citologia', 'biopsia', 'paaf', 'vph', 'inmuno', 
        'inmunohistoquimica', 'estudios', 'papanicolaou'
    ]
    if any(p in limpio for p in palabras_servicios):
        return respuestas.get("opcion_1_servicios")

    # -------------------------------------------------------------
    # 9. SALUDOS
    # -------------------------------------------------------------
    palabras_saludos = [
        'hola', 'buenas', 'buen dia', 'buenos dias', 'buenas tardes', 'buenas noches'
    ]
    if any(p in limpio for p in palabras_saludos):
        return respuestas.get("menu_principal")

    # -------------------------------------------------------------
    # 10. AGRADECIMIENTOS Y CORTESÍA
    # -------------------------------------------------------------
    palabras_gracias = [
        'gracias', 'muchas gracias', 'agradecido', 'perfecto', 'ok', 'vale', 
        'fino', 'chevere', 'listo', 'excelente'
    ]
    if any(p in limpio for p in palabras_gracias):
        return "Con mucho gusto. En *Diagnóstico Citopatológico INLE, C.A.* estamos para servirle. Si desea hacer otra consulta, escriba *MENU* o *PRECIOS*."

    # -------------------------------------------------------------
    # 11. RESPUESTA POR DEFECTO (Si no se reconoce)
    # -------------------------------------------------------------
    return respuestas.get("desconocido_fallback")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(responder_mensaje(" ".join(sys.argv[1:])))
        sys.exit(0)

    print("=" * 65)
    print(" BOT WHATSAPP - DIAGNÓSTICO CITOPATOLÓGICO INLE, C.A.")
    print(" Motor con Tolerancia Lingüística Coloquial y Tipeos Comunes.")
    print(" Escribe un mensaje de prueba (o 'salir' para terminar).")
    print("=" * 65 + "\n")
    
    while True:
        try:
            msg = input("Paciente > ")
            if msg.lower().strip() in ['salir', 'exit', 'quit']:
                break
            resp = responder_mensaje(msg)
            print(f"\nBot INLE >\n{resp}\n")
            print("-" * 65)
        except (KeyboardInterrupt, EOFError):
            break
