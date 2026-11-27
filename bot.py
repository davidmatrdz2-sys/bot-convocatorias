import os
import re
import json
import time
import html
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FORZAR_ENVIO = os.environ.get("FORZAR_ENVIO", "").lower() in ("true", "1", "yes")

# Páginas de OpoBusca que revisamos (convocatorias y ofertas de cada comunidad)
PAGINAS = {
    "Castilla-La Mancha": [
        "https://www.opobusca.com/convocatorias/castilla-la-mancha",
        "https://www.opobusca.com/ofertas/castilla-la-mancha",
    ],
    "Madrid": [
        "https://www.opobusca.com/convocatorias/madrid",
        "https://www.opobusca.com/ofertas/madrid",
    ],
}

# Filtros de oposición exactos:
# 1. "Policía local"
# 2. "Policía Local de Castilla La Mancha"
# 3. "Policía Municipal de Madrid"
FILTROS_OPOSICIONES = (
    "policia-local",
    "policia-local-de-castilla-la-mancha",
    "policia-municipal-de-madrid",
)
SEEN_FILE = "seen.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

session = requests.Session()
session.headers.update(HEADERS)

def obtener(url_base, max_paginas=2):
    """
    Recorre las páginas (máximo 2 páginas recientes por sección) y extrae las
    convocatorias u ofertas de Policía Local / Municipal.
    """
    resultado = {}
    url_actual = url_base
    pagina = 1

    while url_actual and pagina <= max_paginas:
        try:
            print(f" -> Consultando {url_actual} (página {pagina})...", flush=True)
            r = session.get(url_actual, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"Aviso al cargar {url_actual}: {e}", flush=True)
            break

        for a in soup.find_all("a", href=True):
            enlace = urljoin(url_actual, a["href"])
            m = re.search(r"/(convocatorias|ofertas)/([^/]+)/([^/]+)/(\d+)(?:[/?#]|$)", enlace)
            if not m:
                continue
            clase, tipo, lugar, id_num = m.groups()
            titulo = a.get("title") or " ".join(a.get_text(" ", strip=True).split())
            titulo_lower = titulo.lower()

            # Comprobar si coincide con alguno de los filtros tanto en el enlace como en el título
            coincide = (
                any(f in tipo_lower for f in FILTROS_OPOSICIONES) or
                any(f.replace("-", " ") in titulo_lower for f in FILTROS_OPOSICIONES)
            )
            if not coincide:
                continue
            if not titulo or len(titulo) < 5:
                titulo = f"Policía en {lugar.replace('-', ' ').title()}"

            resultado[f"{clase}-{id_num}"] = {
                "clase": clase,
                "url": enlace,
                "titulo": titulo,
                "lugar_slug": lugar,
                "tipo_slug": tipo,
            }

        # Buscar botón o enlace 'Siguiente' asegurando que pertenece a la misma sección
        siguiente = None
        for a in soup.find_all("a", href=True):
            texto = a.get_text(" ", strip=True).lower()
            rel = a.get("rel", [])
            aria = a.get("aria-label", "").lower()
            if "siguiente" in texto or "next" in rel or "siguiente" in aria:
                candidato = urljoin(url_actual, a["href"])
                # Seguridad: no salir de la misma sección base
                if candidato.startswith(url_base) and candidato != url_actual:
                    siguiente = candidato
                    break

        if siguiente:
            url_actual = siguiente
            pagina += 1
        else:
            break

    return resultado

def extraer_lugar(titulo, slug_lugar):
    """Extrae el nombre limpio del municipio y provincia."""
    m = re.search(r"\ben\s+([A-Za-zÁÉÍÓÚáéíóúñÑüÜ\s\(\)\.\-]+?)(?:\s*[\:\-]|\s*$)", titulo)
    if m:
        candidato = m.group(1).strip()
        if len(candidato) > 2 and not any(w in candidato.lower() for w in ["oposiciones", "policía", "policia"]):
            return candidato

    partes = slug_lugar.split("-")
    if len(partes) >= 2:
        municipio = " ".join(partes[:-1]).title()
        provincia = partes[-1].title()
        return f"{municipio} ({provincia})"
    return slug_lugar.replace("-", " ").title()

def extraer_plazas(titulo, texto_pagina):
    """Extrae el número de plazas del título o del cuerpo de la página."""
    m = re.search(r"(\d+)\s+plazas?", titulo, re.IGNORECASE)
    if m:
        num = m.group(1)
        return f"{num} {'plaza' if num == '1' else 'plazas'}"
    if texto_pagina:
        m2 = re.search(r"(?:número de plazas|nº de plazas|nº plazas|plazas?)[:\s]*(\d+)", texto_pagina, re.IGNORECASE)
        if m2:
            num = m2.group(1)
            return f"{num} {'plaza' if num == '1' else 'plazas'}"
        m3 = re.search(r"(\d+)\s+plazas?", texto_pagina, re.IGNORECASE)
        if m3:
            num = m3.group(1)
            return f"{num} {'plaza' if num == '1' else 'plazas'}"
    return "No especificado (consultar bases)"

def extraer_plazo(soup, texto_pagina):
    """Extrae el rango completo del plazo de presentación de instancias (inicio y fin)."""
    if not soup:
        return "20 días hábiles tras publicación en BOE (consultar bases)"

    for elem in soup.find_all(["p", "div", "li", "span", "td", "dd"]):
        t = elem.get_text(" ", strip=True)
        if any(w in t.lower() for w in ["plazo", "instancias", "presentación", "fecha fin", "límite"]):
            # 1. Buscar si hay dos fechas numéricas en el mismo elemento (ej. 15/11/2026 - 15/12/2026)
            fechas = re.findall(r"[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4}", t)
            if len(fechas) >= 2:
                return f"Del {fechas[0]} al {fechas[1]}"
            elif len(fechas) == 1:
                return f"Hasta el {fechas[0]}"

            # 2. Buscar rangos con fechas en texto (ej. 15 de noviembre de 2026 al 15 de diciembre de 2026)
            fechas_txt = re.findall(r"[0-9]{1,2}\s+de\s+[a-zA-ZáéíóúÁÉÍÓÚ]+\s+de\s+[0-9]{4}", t)
            if len(fechas_txt) >= 2:
                return f"Del {fechas_txt[0]} al {fechas_txt[1]}"
            elif len(fechas_txt) == 1:
                return f"Hasta el {fechas_txt[0]}"

            if "20 d" in t.lower() or "días hábiles" in t.lower():
                return "20 días hábiles desde publicación en BOE"

    return "20 días hábiles tras publicación en BOE (consultar bases)"

def extraer_bases(soup, url_ficha):
    """Busca el enlace directo al boletín oficial (BOE/DOCM/BOCM) o archivo PDF de bases."""
    if not soup:
        return url_ficha

    keywords = ["bases", "boletin", "boletín", "boe", "docm", "bocm", "bop", "descargar", "oficial"]

    # 1. Enlace a boletín oficial oficial o PDF
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        href_lower = href.lower()
        texto_link = a.get_text(" ", strip=True).lower()
        if any(b in href_lower for b in ["boe.es", "docm.", "bocm.", "madrid.org", "sede.", "bop"]):
            return urljoin(url_ficha, href)
        if href_lower.endswith(".pdf") and any(kw in (texto_link + href_lower) for kw in keywords):
            return urljoin(url_ficha, href)

    # 2. Enlace cuyo texto indique bases
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        texto_link = a.get_text(" ", strip=True).lower()
        if any(kw in texto_link for kw in ["bases", "boletín oficial", "descargar bases"]):
            if not href.startswith("#") and "javascript" not in href.lower():
                return urljoin(url_ficha, href)

    return url_ficha

def obtener_detalle_individual(datos):
    """Entra en la ficha concreta para sacar municipio, plazas, plazo y enlace de bases."""
    url = datos["url"]
    titulo = datos["titulo"]
    slug_lugar = datos["lugar_slug"]

    lugar = extraer_lugar(titulo, slug_lugar)

    soup = None
    texto_pagina = ""
    try:
        r = session.get(url, timeout=10)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            texto_pagina = soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"Aviso al descargar ficha {url}: {e}", flush=True)

    plazas = extraer_plazas(titulo, texto_pagina)
    plazo = extraer_plazo(soup, texto_pagina) if soup else "20 días hábiles tras publicación en BOE"
    enlace_bases = extraer_bases(soup, url) if soup else url

    return {
        "lugar": lugar,
        "plazas": plazas,
        "plazo": plazo,
        "enlace_bases": enlace_bases
    }

def enviar_telegram(texto, silencioso=False):
    """Envía un mensaje con formato HTML a Telegram."""
    if not TOKEN or not CHAT_ID:
        raise ValueError("Variables TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configuradas.")

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_notification": silencioso,
        "disable_web_page_preview": False
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()

def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("ERROR: Debes definir las variables de entorno TELEGRAM_TOKEN y TELEGRAM_CHAT_ID")

    vistos = set()
    if not FORZAR_ENVIO and os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                vistos = set(json.load(f))
        except Exception as e:
            print(f"Aviso al leer {SEEN_FILE}: {e}. Se reiniciará la lista de vistos.", flush=True)
    elif FORZAR_ENVIO:
        print("⚡ Modo reenvío forzado activo: se reenviarán todas las plazas publicadas.", flush=True)

    nuevas = []
    errores = []

    for zona, urls in PAGINAS.items():
        for url in urls:
            try:
                encontradas = obtener(url, max_paginas=4)
            except Exception as e:
                errores.append(f"{url}: {e}")
                print(f"ERROR al consultar {url}: {e}")
                continue

            tipo_seccion = "Ofertas" if "ofertas" in url else "Convocatorias"
            print(f"\n{zona} - {tipo_seccion} ({url}): {len(encontradas)} encontradas")
            for datos in encontradas.values():
                print(f"  - [{datos['clase'].upper()}] {datos['titulo']}")

            for clave, datos in encontradas.items():
                if clave not in vistos and clave not in [n[1] for n in nuevas]:
                    nuevas.append((zona, clave, datos))

    if not nuevas:
        print("\nNo hay nuevas convocatorias ni ofertas pendientes de avisar.")
        return

    print(f"\nProcesando y enviando avisos detallados de {len(nuevas)} publicaciones a Telegram...")

    # Separar Convocatorias de Ofertas
    convocatorias = [item for item in nuevas if item[2]["clase"] == "convocatorias"]
    ofertas = [item for item in nuevas if item[2]["clase"] == "ofertas"]

    # 1. Enviar Convocatorias: una a una (con sonido y máximo detalle urgente)
    for zona, clave, datos in convocatorias:
        detalle = obtener_detalle_individual(datos)

        lugar_txt = html.escape(detalle["lugar"])
        plazas_txt = html.escape(detalle["plazas"])
        plazo_txt = html.escape(detalle["plazo"])
        url_bases = detalle["enlace_bases"]
        url_ficha = datos["url"]

        texto = (
            f"🚨 <b>NUEVA CONVOCATORIA ({html.escape(zona.upper())})</b>\n"
            f"<i>Proceso selectivo abierto: plazo de presentación de instancias</i>\n\n"
            f"📍 <b>Municipio / Lugar:</b> {lugar_txt}\n"
            f"👥 <b>Número de plazas:</b> {plazas_txt}\n"
            f"⏳ <b>Plazo de instancias:</b> {plazo_txt}\n"
            f"📄 <b>Documento Oficial Bases:</b> <a href=\"{url_bases}\">Ver Documento Oficial</a>\n\n"
            f"🔗 <b>Ficha de la convocatoria:</b> <a href=\"{url_ficha}\">Abrir en OpoBusca</a>"
        )
        enviar_telegram(texto, silencioso=False)
        vistos.add(clave)
        time.sleep(1.5)

    # 2. Enviar Ofertas de Empleo Público: TODAS AGRUPADAS en un solo mensaje silencioso
    if ofertas:
        bloques_ofertas = []
        for zona, clave, datos in ofertas:
            detalle = obtener_detalle_individual(datos)
            lugar_txt = html.escape(detalle["lugar"])
            plazas_txt = html.escape(detalle["plazas"])
            url_ficha = datos["url"]

            bloques_ofertas.append(
                f"🏛️ <b>{lugar_txt}</b> ({html.escape(zona)})\n"
                f"   👥 <b>Plazas:</b> {plazas_txt}\n"
                f"   🔗 <a href=\"{url_ficha}\">Ver ficha en OpoBusca</a>"
            )
            vistos.add(clave)

        cabecera = (
            f"📢 <b>RESUMEN DE OFERTAS DE EMPLEO PÚBLICO ({len(ofertas)} encontradas)</b>\n"
            f"<i>Plazas aprobadas en OEP (en previsión administrativa, aún sin instancias):</i>\n\n"
        )
        cuerpo = "\n\n".join(bloques_ofertas)
        texto_completo = cabecera + cuerpo

        # Si supera el límite de longitud de Telegram (4096 caracteres), se envía en bloques seguros
        if len(texto_completo) <= 4000:
            enviar_telegram(texto_completo, silencioso=True)
        else:
            trozos = []
            actual = cabecera
            for b in bloques_ofertas:
                if len(actual) + len(b) + 2 > 3800:
                    trozos.append(actual)
                    actual = b + "\n\n"
                else:
                    actual += b + "\n\n"
            if actual.strip():
                trozos.append(actual.strip())
            for t in trozos:
                enviar_telegram(t, silencioso=True)
                time.sleep(1)

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(vistos), f, indent=2, ensure_ascii=False)
    print(f"\nHistorial actualizado en {SEEN_FILE}. Total registrados: {len(vistos)}")

    if errores:
        raise SystemExit("Fallaron algunas páginas:\n" + "\n".join(errores))

if __name__ == "__main__":
    main()
