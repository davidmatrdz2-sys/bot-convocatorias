import os
import re
import json
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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

# Nos quedamos solo con entradas cuyo enlace contenga alguna de estas palabras clave
PALABRAS = ("policia-local", "policia-municipal")
SEEN_FILE = "seen.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def obtener(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    resultado = {}
    
    for a in soup.find_all("a", href=True):
        enlace = urljoin(url, a["href"])
        # Formato de enlace habitual en OpoBusca: /(convocatorias|ofertas)/tipo/municipio/id
        m = re.search(r"/(convocatorias|ofertas)/([^/]+)/([^/]+)/(\d+)(?:[/?#]|$)", enlace)
        if not m:
            continue
        clase, tipo, lugar, id_num = m.groups()
        tipo_lower = tipo.lower()
        if not any(p in tipo_lower for p in PALABRAS):
            continue
            
        titulo = a.get("title") or " ".join(a.get_text(" ", strip=True).split())
        if not titulo:
            municipio_limpio = lugar.replace("-", " ").title()
            titulo = f"Policía en {municipio_limpio}"

        resultado[f"{clase}-{id_num}"] = {
            "clase": clase,
            "url": enlace,
            "titulo": titulo,
            "lugar": lugar.replace("-", " ").title()
        }
    return resultado

def enviar_telegram(texto, silencioso=False):
    if not TOKEN or not CHAT_ID:
        raise ValueError("Variables TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configuradas.")
        
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "disable_notification": silencioso,
        "disable_web_page_preview": False
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()

def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("ERROR: Debes definir las variables de entorno TELEGRAM_TOKEN y TELEGRAM_CHAT_ID")

    primera_vez = not os.path.exists(SEEN_FILE)
    vistos = set()
    if not primera_vez:
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                vistos = set(json.load(f))
        except Exception as e:
            print(f"Aviso al leer {SEEN_FILE}: {e}. Se reiniciará la lista de vistos.")

    nuevas = []
    errores = []

    for zona, urls in PAGINAS.items():
        for url in urls:
            try:
                encontradas = obtener(url)
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

    if primera_vez:
        print(f"\nPrimera ejecución: guardando {len(nuevas)} entradas previas para no saturar el grupo...")
        msg = (
            f"✅ *Bot de Avisos Activado*\n\n"
            f"Se han registrado {len(nuevas)} publicaciones ya existentes en OpoBusca.\n\n"
            f"A partir de ahora, solo avisaré cuando aparezca una novedad:\n"
            f"• 🚨 *Convocatorias (C):* aviso con sonido (plazo abierto para instancias).\n"
            f"• 📢 *Ofertas OEP (O):* aviso silencioso (plazas aprobadas en previsión)."
        )
        try:
            enviar_telegram(msg)
            print("Mensaje de activación enviado a Telegram con éxito.")
        except Exception as e:
            print(f"Error al enviar mensaje inicial a Telegram: {e}")
    else:
        print(f"\nEnviando avisos de {len(nuevas)} nuevas publicaciones...")
        for zona, clave, datos in nuevas:
            if datos["clase"] == "convocatorias":
                texto = (
                    f"🚨 NUEVA CONVOCATORIA ({zona})\n"
                    f"Proceso abierto: revisar bases y plazo de instancias.\n\n"
                    f"📌 {datos['titulo']}\n\n"
                    f"🔗 {datos['url']}"
                )
                enviar_telegram(texto, silencioso=False)
            else:
                texto = (
                    f"📢 NUEVA OFERTA DE EMPLEO PÚBLICO ({zona})\n"
                    f"Plazas previstas (OEP): todavía no se pueden presentar instancias.\n\n"
                    f"📌 {datos['titulo']}\n\n"
                    f"🔗 {datos['url']}"
                )
                enviar_telegram(texto, silencioso=True)
            time.sleep(1)

    vistos.update(clave for _, clave, _ in nuevas)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(vistos), f, indent=2, ensure_ascii=False)
    print(f"\nHistorial actualizado en {SEEN_FILE}. Total registros guardados: {len(vistos)}")

    if errores:
        raise SystemExit("Fallaron algunas páginas:\n" + "\n".join(errores))

if __name__ == "__main__":
    main()
