// Script de prueba de conexión directa en Node.js
// Utilízalo para comprobar en 5 segundos que tu bot y tu grupo funcionan
const TOKEN = process.env.TELEGRAM_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT_ID;

if (!TOKEN || !CHAT_ID) {
  console.error("❌ ERROR: Debes definir TELEGRAM_TOKEN y TELEGRAM_CHAT_ID antes de ejecutar.");
  console.log("\nEn PowerShell:");
  console.log('  $env:TELEGRAM_TOKEN="tu_token_aqui"');
  console.log('  $env:TELEGRAM_CHAT_ID="-1003843621218"');
  console.log('  node test_bot.js\n');
  process.exit(1);
}

async function run() {
  console.log("1. Probando conexión con la API de Telegram...");
  const meRes = await fetch(`https://api.telegram.org/bot${TOKEN}/getMe`);
  const meData = await meRes.json();
  if (!meData.ok) {
    throw new Error(`Telegram error: ${JSON.stringify(meData)}`);
  }
  console.log(`   ✅ Bot reconocido: @${meData.result.username} (${meData.result.first_name})`);

  console.log("\n2. Enviando mensaje de prueba al grupo de Telegram...");
  const sendRes = await fetch(`https://api.telegram.org/bot${TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: CHAT_ID,
      text: "🤖 ¡Hola! Mensaje de prueba: el bot de convocatorias de Policía Local está configurado correctamente."
    })
  });
  const sendData = await sendRes.json();
  if (!sendData.ok) {
    throw new Error(`Error enviando mensaje al chat ${CHAT_ID}: ${JSON.stringify(sendData)}`);
  }
  console.log("   ✅ ¡Mensaje de prueba entregado en el grupo con éxito!");

  console.log("\n3. Probando lectura web de OpoBusca (Castilla-La Mancha)...");
  try {
    const opoRes = await fetch("https://www.opobusca.com/convocatorias/castilla-la-mancha", {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
      }
    });
    console.log(`   Estado respuesta OpoBusca: ${opoRes.status} (${opoRes.statusText})`);
    if (opoRes.ok) {
      console.log("   ✅ Conexión con OpoBusca completada sin bloqueo.");
    }
  } catch (e) {
    console.log(`   (Aviso al conectar con OpoBusca: ${e.message})`);
  }

  console.log("\n🎉 ¡Todo funciona correctamente! Ya puedes subirlo a GitHub Actions.");
}

run().catch(err => {
  console.error("\n❌ Error durante la prueba:", err.message);
  process.exit(1);
});
