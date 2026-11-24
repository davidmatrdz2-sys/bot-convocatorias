# Bot de Avisos: Convocatorias y Ofertas de Policía Local (CLM y Madrid)

Bot automatizado para rastrear en OpoBusca las nuevas convocatorias y ofertas de empleo público de Policía Local en Castilla-La Mancha y Policía Municipal / Local en la Comunidad de Madrid, enviando notificaciones automáticas a un canal o grupo de Telegram.

---

## 🚀 Cómo funciona

1. Cada 3 horas, **GitHub Actions** ejecuta el script de forma 100% gratuita y en la nube (sin necesidad de tener tu ordenador encendido).
2. Consulta las páginas de **Castilla-La Mancha** y **Madrid** tanto de *Convocatorias* como de *Ofertas*.
3. Filtra únicamente las plazas de `Policía Local` y `Policía Municipal`.
4. Distingue los dos tipos de publicaciones:
   - 🚨 **Convocatoria (C):** Alerta normal con sonido. Proceso selectivo abierto con plazo para presentar instancias.
   - 📢 **Oferta de Empleo Público (O / OEP):** Alerta silenciosa (`disable_notification: true`). Plazas aprobadas en previsión presupuestaria (hasta 3 años para ser convocadas).
5. Compara los identificadores con el archivo `seen.json`. Si hay novedades, las envía a Telegram y actualiza el archivo en el repositorio.

---

## 🛠️ Estructura del Proyecto

```
bot-convocatorias/
├── .github/
│   └── workflows/
│       └── revisar.yml      <- Automatización programada (GitHub Actions)
├── bot.py                   <- Código principal en Python
├── requirements.txt         <- Dependencias (requests, beautifulsoup4)
├── test_bot.js              <- Test rápido de conexión (Node.js)
├── .gitignore
└── README.md
```

---

## 📋 Pasos para Ponerlo en Marcha

### 1. Seguridad del Token de Telegram
Como el token inicial se compartió en texto plano en conversaciones previas:
1. Abre Telegram y habla con [@BotFather](https://t.me/BotFather).
2. Envía `/revoke` y selecciona tu bot `@BuscaPlazasPLBot`.
3. Te entregará un **Token nuevo**. Guarda ese token nuevo en un lugar privado.

### 2. Probar la Conexión (Opcional - Rápido desde tu Terminal)
Ya tienes **Node.js** instalado en tu sistema, así que puedes probar la conexión sin necesidad de configurar Python localmente:
1. Abre la terminal en esta carpeta (`bot-convocatorias`).
2. Configura las variables temporalmente (sustituye por tu nuevo token):
   ```powershell
   $env:TELEGRAM_TOKEN="TU_NUEVO_TOKEN"
   $env:TELEGRAM_CHAT_ID="-1003843621218"
   node test_bot.js
   ```
3. Si el mensaje de prueba llega al grupo, ¡la integración está 100% lista!

### 3. Crear el Repositorio en GitHub
1. Entra en tu cuenta de [GitHub](https://github.com/new).
2. Crea un nuevo repositorio:
   - **Repository name:** `bot-convocatorias` (o el nombre que prefieras).
   - **Visibilidad:** Privado (*Private*).
   - No marques añadir README ni .gitignore (ya los tenemos creados aquí).
3. Sube los archivos de esta carpeta a ese nuevo repositorio en GitHub:
   ```powershell
   git init
   git add .
   git commit -m "Initial commit - Bot avisos convocatorias"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/bot-convocatorias.git
   git push -u origin main
   ```

### 4. Configurar los Secretos en GitHub
Para que GitHub Actions pueda usar tu bot de Telegram sin hacer público tu token:
1. En tu repositorio de GitHub, ve a **Settings** (pestaña superior).
2. En el menú de la izquierda, entra en **Secrets and variables** → **Actions**.
3. Pulsa el botón verde **New repository secret** y añade dos secretos:
   - Nombre: `TELEGRAM_TOKEN` | Valor: Tu nuevo token de BotFather.
   - Nombre: `TELEGRAM_CHAT_ID` | Valor: `-1003843621218`

### 5. Dar Permisos de Escritura al Workflow
Para que GitHub Actions pueda guardar y actualizar el archivo `seen.json` en el repositorio:
1. En el repositorio de GitHub, ve a **Settings** → **Actions** → **General**.
2. Baja hasta la sección **Workflow permissions**.
3. Selecciona la opción **Read and write permissions**.
4. Haz clic en **Save**.

### 6. Ejecutar la Primera Prueba en la Nube
1. Ve a la pestaña **Actions** en tu repositorio de GitHub.
2. En la lista de la izquierda, pulsa en **Revisar convocatorias de Policía**.
3. Haz clic en el botón **Run workflow** → **Run workflow**.
4. Verás la ejecución en verde (✔️). Al terminar:
   - Llegará el mensaje al grupo: `✅ Bot de Avisos Activado. Se han registrado X publicaciones previas...`
   - Se creará en el repositorio el archivo `seen.json` con todas las convocatorias y ofertas actuales guardadas.
5. A partir de ese momento, la acción se ejecutará sola cada 3 horas y solo avisará de las que sean estrictamente nuevas.
