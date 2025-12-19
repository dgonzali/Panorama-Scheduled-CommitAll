# Panorama Out-of-Sync Commit Script

Este script automatiza la identificación y sincronización de dispositivos que se encuentran fuera de sincronización ("Out of Sync") en Palo Alto Networks Panorama utilizando su API XML.

## Objetivo

El script consulta a Panorama para identificar qué equipos tienen políticas pendientes de aplicar. Presenta un resumen al usuario (incluyendo el número de serie, el grupo de dispositivos y el estado de conexión) y permite ejecutar un comando `commit-all` de forma selectiva para sincronizar dichos equipos.

Permitiria la programacion automatica de la ejecucion diaria del commit-all a los equipos que esten en out of sync (para hacerlo fuera de horario de produccion por ejemplo). Para ello, habria que programar un job diario que ejecutara el script y deshabilitar la variable REQUIRE_CONFIRMATION.

## Requisitos

- Python 3.x
- Librerías listadas en `requirements.txt` (`requests`, `python-dotenv`)
- Acceso de red a la API de Panorama (puerto 443)

## Instalación

1. Clona o descarga este repositorio.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Configura el archivo `.env` con tus credenciales:
   ```env
   PAN_URL=https://tu-panorama-url
   PAN_API_KEY=tu_api_key
   REQUIRE_CONFIRMATION=false
   ```

## Configuración de Automatización

El script incluye una variable `REQUIRE_CONFIRMATION` que determina si el script debe esperar una confirmación manual antes de ejecutar el `commit-all`.

- **`true` (por defecto)**: El script mostrará el resumen y esperará a que el usuario escriba `Y`.
- **`false`**: El script ejecutará el `commit-all` automáticamente tras detectar equipos fuera de sincronización. Esto es ideal para tareas programadas (Cron jobs o Task Scheduler).

Puedes cambiar este valor directamente en el código o a través del archivo `.env`.

## Uso

Ejecuta el script principal:

```bash
python commit-all.py
```

### Flujo de Trabajo:
1. **Detección**: El script busca dispositivos con estado "Out of Sync".
2. **Resumen**: Muestra una lista de los equipos afectados y pregunta si deseas proceder.
3. **Commit**: Si confirmas con `Y`, envía un `commit-all` a Panorama.
4. **Monitoreo**: Realiza un seguimiento del progreso del Job de Panorama cada 10 segundos.
5. **Resultado**: Muestra el estado final de la operación para cada dispositivo involucrado.

## Seguridad

- El script utiliza el encabezado `X-PAN-KEY` para la autenticación, evitando pasar la API Key en la URL.
- (Opcional) La verificación de certificados SSL está desactivada por defecto (`verify=False`) para facilitar el uso con certificados internos, pero puede activarse en el código si se dispone de certificados válidos.
- La version actual solo tiene en cuenta los devices groups (no considera templates) 