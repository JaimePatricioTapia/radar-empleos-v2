# Despliegue en Streamlit Community Cloud

## Estado actualizado — 2026-11-23
- La rama desplegable `feature/streamlit-cloud-deployment` recibió el PR #10 con optimizaciones para plan gratuito; merge commit: `b6ee22f8a69d792d3ab863c036048d25121bc0d4`.
- GitHub Actions ejecutó `pytest -q`: **51 pruebas aprobadas**.
- Repositorio GitHub: privado. Aplicación Streamlit Community Cloud: pública, con autenticación obligatoria y datos privados por usuario mediante RLS, según autorización del propietario.
- La URL pública asignada por Streamlit no está registrada en este repositorio ni quedó disponible en la conversación. El smoke test real de inicio de sesión, CV y búsqueda permanece pendiente de confirmar desde esa URL.
- La fusión actualiza la rama que Streamlit Community Cloud tiene configurada; no equivale por sí sola a verificar que el servicio haya terminado de reconstruirse.

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
4. Si la app ya existe, abrir sus Settings y confirmar:
   - Repository: `JaimePatricioTapia/radar-empleos-v2`
   - Branch: `feature/streamlit-cloud-deployment`
   - Main file path: `app.py`
   - Python: `3.11` (alineado con CI)
   Si todavía no existe, crearla con esos mismos valores.
5. Confirmar que los secretos estén cargados en Advanced settings. No copiar ni compartir sus valores. Streamlit reconstruye la app al actualizarse la rama.
6. Confirmar que la app inicia y probar autenticación, carga de CV, bandeja y búsqueda integral.
7. La app es pública, pero el acceso a información requiere autenticación; no compartir credenciales ni habilitar registros de terceros hasta completar QA-022 y revisar RLS.

## Pruebas antes de uso real
- CI: `pytest -q` — **51 pruebas aprobadas en 2026-11-23**.
- QA-021: verificar que los secretos no aparecen en el repositorio, interfaz ni logs.
- QA-022: probar dos usuarios con sesiones distintas y comprobar aislamiento RLS.
- QA-023: subir PDF válido, PDF corrupto y archivo >15 MB; confirmar que solo se activa el CV del usuario autenticado y se elimina el temporal.
- QA-024: smoke test en Community Cloud y comprobación de la URL asignada.
- Ejecutar el flujo de búsqueda solo después de confirmar que el CV activo pertenece al usuario y revisar el consumo de Gemini/JobSpy.
- Confirmar visualmente en la URL pública que la app termina de iniciar, permite login y muestra el modelo de embeddings activo. El valor visible debe ser el modelo configurado en Secrets; no compartir la clave API.
- Primera ejecución protegida por topes internos: 250 fragmentos y 15 evaluaciones por ventana móvil de 24 horas. No aumentar esos topes sin revisar la cuota gratuita real.

## Riesgo y limitación de privacidad
El PDF se transmite desde el navegador al servidor de Streamlit para su procesamiento. El código elimina el archivo temporal después de procesarlo, pero esto no equivale a mantener el PDF exclusivamente en el dispositivo local. No cargar documentos que no se quiera transmitir al proveedor de hosting. La app no debe abrir registros a terceros hasta completar las pruebas de aislamiento y revisar las condiciones de privacidad del hosting.

## Rollback
Si la reconstrucción de Streamlit falla, revisar logs de despliegue sin copiar secretos, tokens ni contenido del CV. El commit anterior de la rama desplegable era `ce6a3955b4684ff97a02c90ca14e8d1e460bef43`; puede revertirse el merge `b6ee22f8a69d792d3ab863c036048d25121bc0d4` desde GitHub. No alterar el esquema Supabase ni borrar registros como solución rápida.
