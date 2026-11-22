# Despliegue en Streamlit Community Cloud

## Estado
Preparación de código en revisión. No declarar el despliegue operativo hasta completar las pruebas de aceptación y la autorización de GitHub/Streamlit por parte del propietario.

## Restricciones obligatorias
- El repositorio `JaimePatricioTapia/radar-empleos-v2` permanece privado.
- Usar solo el proyecto Supabase independiente Radar 2.0; nunca conectar el proyecto antiguo.
- Configurar únicamente una Supabase publishable key o anon legacy key. Nunca usar service_role ni secret key.
- No almacenar CV, `.env`, secretos ni tokens en GitHub.
- El cliente Supabase se crea y conserva dentro de `st.session_state` de cada sesión de navegador.
- El PDF se procesa en un temporal del servidor, con máximo de 15 MB y eliminación en bloque `finally`; no se persiste el binario.
- El texto extraído, chunks y embeddings se guardan en Supabase bajo RLS.

## Configuración de secretos
En Streamlit Community Cloud > app > Settings > Secrets, agregar valores reales desde el panel de Supabase y Google AI Studio. Nunca pegarlos en el repositorio ni en el chat.

```toml
SUPABASE_URL = "https://<PROJECT_REF>.supabase.co"
SUPABASE_KEY = "<PUBLISHABLE_OR_ANON_KEY>"
GEMINI_API_KEY = "<GEMINI_API_KEY>"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_EMBEDDING_DIMENSIONS = "3072"
APP_ENV = "cloud"
```

No usar literalmente los marcadores de posición. No añadir service_role ni secretos administrativos.

## Pasos de despliegue
1. Confirmar que el repositorio sigue en modo **Private**.
2. Abrir https://share.streamlit.io/ e iniciar sesión con GitHub.
3. En Streamlit Community Cloud, conectar GitHub y conceder acceso al repositorio privado solo después de revisar el alcance OAuth solicitado. Streamlit requiere permisos adicionales para repositorios privados.
4. Crear app seleccionando:
   - Repository: `JaimePatricioTapia/radar-empleos-v2`
   - Branch: `feature/streamlit-cloud-deployment` (solo para prueba controlada)
   - Main file path: `app.py`
   - Python: `3.11` (alineado con CI)
5. En Advanced settings, cargar los secretos anteriores y desplegar.
6. Confirmar que la app inicia y probar autenticación, carga de CV, bandeja y búsqueda integral.
7. No invitar terceros ni habilitar pruebas multiusuario hasta completar QA-022 y revisar RLS.

## Pruebas antes de uso real
- CI: `pytest -q`.
- QA-021: verificar que los secretos no aparecen en el repositorio, interfaz ni logs.
- QA-022: probar dos usuarios con sesiones distintas y comprobar aislamiento RLS.
- QA-023: subir PDF válido, PDF corrupto y archivo >15 MB; confirmar que solo se activa el CV del usuario autenticado y se elimina el temporal.
- QA-024: smoke test en Community Cloud y comprobación de la URL asignada.
- Ejecutar el flujo de búsqueda solo después de confirmar que el CV activo pertenece al usuario y revisar el consumo de Gemini/JobSpy.

## Riesgo y limitación de privacidad
El PDF se transmite desde el navegador al servidor de Streamlit para su procesamiento. El código elimina el archivo temporal después de procesarlo, pero esto no equivale a mantener el PDF exclusivamente en el dispositivo local. No cargar documentos que no se quiera transmitir al proveedor de hosting. La app no debe abrir registros a terceros hasta completar las pruebas de aislamiento y revisar las condiciones de privacidad del hosting.

## Rollback
Si falla el despliegue, detener la app en Community Cloud y volver a la versión estable aprobada. No fusionar esta rama ni alterar el esquema Supabase como solución rápida. Registrar logs técnicos sin copiar secretos, tokens ni contenido del CV.
