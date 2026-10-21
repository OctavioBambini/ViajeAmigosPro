# ViajeAmigos Pro — edición web local

Página web adaptable a celulares, sin Firebase ni compilación APK. Solo necesita HTML, CSS y JavaScript; los datos se guardan con `localStorage` en **ese navegador**.

## Publicar gratis en GitHub Pages (usando tu repositorio actual)

1. Entrá a `https://github.com/OctavioBambini/ViajeAmigosPro` y abrí **Code**.
2. Tocá **Add file → Upload files** y subí estos cinco archivos a la **raíz del repositorio** (junto a `main.py`): `index.html`, `manifest.webmanifest`, `sw.js`, `icon-192.png`, `icon-512.png`. No subas la carpeta que los contiene; deben quedar directamente en la raíz.
3. Confirmá con **Commit changes**. No hace falta tocar el código Python ni Actions.
4. Entrá a **Settings → Pages**. En **Build and deployment**, elegí **Deploy from a branch**. Seleccioná rama `main`, carpeta `/(root)` y guardá con **Save**.
5. Esperá a que GitHub publique el sitio. Abrí la dirección:

   `https://octaviobambini.github.io/ViajeAmigosPro/`

   GitHub Pages puede tardar unos minutos en habilitar el enlace, y los nombres de usuario/repositorio deben coincidir exactamente.
6. En tu celular Android abrí ese enlace en Chrome. Podés elegir en el menú **Agregar a pantalla principal** o **Instalar app** (si Chrome ofrece la opción).

## Funciones

- Inicio: estadísticas, presentación y viaje activo.
- Grupo: crear y editar viajes, agregar integrantes y elegir el viaje activo.
- Agenda: actividades con fecha, hora, lugar y notas.
- Fotos: capturar desde el celular o importar desde la galería; se comprimen y se almacenan localmente en el navegador.
- Mapa: OpenStreetMap/Leaflet con lugares guardados, coordenadas **manuales** de integrantes y botón de GPS propio con permiso del usuario.
- Respaldo: menú `⋯` para exportar/importar un JSON con viajes, integrantes, fotos, lugares y agenda.
- Pantalla principal trae datos de **demostración** claramente marcados como tales; podés crear tu propio viaje.

## Restricciones importantes

- **No hay sincronización entre teléfonos**, ni GPS compartido en tiempo real. No requiere cuentas; los datos permanecen solo en el navegador en el que se crearon.
- Las fotos usan espacio limitado de `localStorage`: no subas demasiadas fotos. El respaldo JSON permite conservarlas.
- El mapa necesita **internet para cargar las imágenes de mapa**. El resto de la app puede seguir funcionando después de una primera visita, si el navegador conserva sus archivos.
- El GPS requiere **HTTPS** y permiso del navegador. GitHub Pages usa HTTPS.
- **No se necesita APK**: es una página web y opcionalmente se puede añadir al inicio como acceso directo o PWA.
- Si usás modo incógnito o borrás los datos del navegador, podés perder datos locales.
