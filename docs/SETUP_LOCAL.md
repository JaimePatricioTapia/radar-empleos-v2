# Puesta en marcha local — Radar 2.0

## 1. Preparar entorno

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

En Windows, active el entorno con `.venv\\Scripts\\activate`.

## 2. Configurar variables en .env

- `GEMINI_API_KEY`: clave de Google AI Studio.
- `SUPABASE_URL`: URL del proyecto Radar Empleos 2.0.
- `SUPABASE_KEY`: publishable key (o anon legacy) del proyecto nuevo. Nunca use `service_role` ni secret key en la aplicación.
- `CV_PDF_PATH`: ruta local al PDF del CV.

No suba `.env` ni el PDF al repositorio.

## 3. Habilitar registro

En Supabase Dashboard > Authentication > Providers, confirme que Email esté habilitado. Si la confirmación de correo está activa, confirme el mensaje recibido antes de iniciar sesión.

## 4. Ejecutar

```bash
streamlit run app.py
```

La aplicación permite crear una cuenta o iniciar sesión. Luego, **Procesar mi CV** lee el PDF local, calcula SHA-256, crea fragmentos y embeddings Gemini y guarda texto/embeddings en el proyecto independiente. El archivo PDF binario no se carga.

## Seguridad

- Se utiliza la sesión Auth del usuario y políticas RLS.
- No configure claves `service_role` ni secret keys en el cliente.
- No comparta contraseñas, claves ni el archivo `.env` en el chat.
- La primera ingesta de un CV genera consumo de Gemini por embeddings.
