# ViajeAmigos Pro · Edición LOCAL (proyecto final)

Aplicación Kivy para Windows y Android. **No usa Firebase, Google ni cuentas**. Los viajes, integrantes, fotos, agenda y lugares se guardan en el dispositivo mediante SQLite.

**IMPORTANTE:** el ZIP es el **código fuente**, **no un APK**. Para instalarlo en Android hay que compilarlo con Buildozer. Se incluyen `buildozer.spec`, un script para Ubuntu y un flujo de GitHub Actions que intenta compilarlo y publica el APK como artefacto.

## Funciones

- **Inicio:** muestra el viaje activo.
- **Grupo:** crea, selecciona y elimina viajes; agrega y quita amigos; guarda coordenadas **manuales** de amigos.
- **Mapa:** mapas de OpenStreetMap, marcadores de amigos y lugares guardados. Botón **Mi GPS** (Android, requiere permiso) para mostrar **tu propia ubicación**.
- **Fotos:** toma fotos en Android mediante la cámara del sistema (Android Intent / PyJNIus, imagen de vista previa); en Windows usa la webcam Kivy e importa JPG/PNG. Archivos almacenados en el espacio privado de la app.
- **Agenda:** crea/elimina actividades, fecha y hora, descripción; persiste en SQLite sin conexión.
- **Respaldos:** exporta un ZIP con agenda, amigos, lugares y fotos. En **Windows** también se puede importar un respaldo. **En Android el ZIP exportado queda dentro del directorio privado**: esta edición aún no tiene selector Android para extraerlo o importarlo desde otra aplicación.

### Limitaciones sinceras

- **No existe sincronización entre teléfonos ni posiciones en vivo de otros amigos.** Los marcadores de los amigos son coordenadas cargadas manualmente.
- **La agenda no se comparte automáticamente entre teléfonos**; todos los integrantes de un viaje se administran en una sola instalación local. Los respaldos se pueden trasladar manualmente desde Windows.
- **El mapa necesita acceso a internet** para descargar mosaicos nuevos; la base de datos, agenda y fotos no necesitan internet.
- La cámara y el GPS en Android necesitan probarse en un teléfono después de compilar el APK. La foto Android se obtiene como **imagen de vista previa**, no como fotografía de máxima resolución; esto evita depender de un FileProvider Android externo.

## 1. Ejecutar en Windows (VS Code)

Abrí esta carpeta en VS Code y ejecutá **en PowerShell**:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Si ya existe `.venv`, podés omitir el primer comando. En VS Code seleccioná el intérprete `.venv\Scripts\python.exe` desde **Python: Select Interpreter**.

**Migración de tu versión anterior:** Si ya habías guardado actividades/fotos en el mismo directorio de datos de Kivy, se copian al **primer viaje** que crees. No reemplaces ni borres el directorio local de datos de tu app anterior. Los grupos de Firebase no se migran, ya que esta versión no los usa.

## 2. Crear APK desde Windows con Ubuntu/WSL2 (recomendado)

El APK **no se crea con `python main.py`**; Buildozer requiere Linux/macOS. En Windows usá WSL2. Se necesita internet durante la compilación para descargar Android SDK/NDK y dependencias.

1. Abrí **PowerShell como administrador** en Windows:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

   Reiniciá si lo solicita, iniciá Ubuntu y creá usuario/contraseña.

2. Con Ubuntu 24.04 abierto, copiá el proyecto **al disco Linux**. Cambiá `pc20` si tu usuario es distinto y verificá dónde descomprimiste el ZIP:

   ```bash
   mkdir -p ~/ViajeAmigosProLocal
   cp -r /mnt/c/Users/pc20/Downloads/ViajeAmigosPro_Local/. ~/ViajeAmigosProLocal/
   cd ~/ViajeAmigosProLocal
   ls
   ```

   Deberías ver `main.py`, `storage.py`, `backup.py` y `buildozer.spec`.

3. Compilá el APK (**puede tardar bastante la primera vez**):

   ```bash
   bash compilar_apk_ubuntu.sh
   ```

   Si Ubuntu te pide contraseña, es la del usuario de Ubuntu (aunque no veas caracteres mientras escribís).

4. Cuando termine **sin errores**, localizá el APK:

   ```bash
   ls -lh bin/*.apk
   ```

5. Copialo a Descargas de Windows:

   ```bash
   cp bin/*.apk /mnt/c/Users/pc20/Downloads/
   ```

6. Pasá ese `.apk` al teléfono mediante cable USB o un medio de transferencia de archivos. Abrilo desde **Archivos** y autorizá **Instalar apps desconocidas** para ese origen si Android lo solicita. Instalá **solo el APK que vos mismo compilaste**.

> Si Buildozer falla, conservá las últimas 40 líneas de la terminal para identificar el problema. El archivo `buildozer.spec` está configurado para Android `arm64-v8a`.

## 3. Alternativa: compilar con GitHub Actions (sin WSL)

Si tenés una cuenta de GitHub, podés compilar desde la nube sin usar Firebase ni cambiar el código.

1. Creá un repositorio en GitHub.
2. Subí **los archivos dentro de esta carpeta**, de modo que `main.py`, `buildozer.spec` y `.github/workflows/compilar-apk.yml` estén en la **raíz del repositorio**.
3. Abrí **Actions → Compilar APK ViajeAmigos Pro → Run workflow**.
4. Esperá a que termine el proceso. Si el trabajo resulta exitoso, abajo en **Artifacts** aparecerá `ViajeAmigosProLocal-APK`.
5. Descargá el artefacto: GitHub entrega un **ZIP que contiene un APK**. Descomprimilo, transferí el archivo `.apk` a tu Android e instalalo.

**Aviso:** no hay garantía de que un build nuevo de Python-for-Android termine sin ajustes por cambios en SDK/NDK. Si la acción falla, habrá que revisar el registro antes de obtener un instalador.

## 4. Cómo utilizar el programa

1. En **Grupo**, creá un viaje, por ejemplo *Viaje a Córdoba*.
2. Agregá los integrantes. Si querés marcadores en el mapa, cargá coordenadas manualmente desde **Ubicación** (no se rastrea a nadie).
3. En **Agenda**, agregá actividades.
4. En **Mapa**, mirá marcadores, guardá lugares y, en Android, tocá **Mi GPS** para ver tu posición en tu propio teléfono.
5. En **Fotos**, tocá **Abrir cámara**. En Windows también podés importar fotos.
6. Para tener más de un viaje, creá otro desde **Grupo** y seleccioná cuál usar.

## 5. Archivos

| Archivo | Para qué sirve |
|---|---|
| `main.py` | Interfaz y funciones de la app |
| `android_camera.py` | Captura de imagen desde la cámara Android mediante un Intent |
| `storage.py` | Base local SQLite |
| `backup.py` | Exportación/importación ZIP local |
| `assets/icon.png` | Ícono de la app |
| `requirements.txt` | Dependencias de Windows |
| `buildozer.spec` | Configuración Android |
| `compilar_apk_ubuntu.sh` | Script para compilar con Ubuntu/WSL |
| `.github/workflows/compilar-apk.yml` | Compilación opcional en GitHub |
| `tests/test_local.py` | Pruebas del almacenamiento |

Pruebas sin instalar Kivy:

```bash
python -m unittest discover -s tests -v
```

## 6. Relación con la actividad escolar (APIs)

- **Ubicación:** Android Location API expuesta por Plyer/GPS, con permiso explícito del dueño del teléfono. Los otros miembros son puntos manuales, no datos reales en tiempo real.
- **Fotografía:** interfaz de cámara del sistema Android expuesta mediante PyJNIus/Intent, sin subir fotos a ningún servicio.
- **Calendario:** implementación local propia con SQLite para agenda y recordatorio de horarios. No se usa Google Calendar API ni sincronización con otros usuarios.
- **Mapa:** widgets MapView con mosaicos de OpenStreetMap; descarga de mapa por internet cuando hace falta.

Esta adaptación fue hecha para cumplir la consigna **en modo local** autorizada por el profesor, sin prometer sincronización remota.
