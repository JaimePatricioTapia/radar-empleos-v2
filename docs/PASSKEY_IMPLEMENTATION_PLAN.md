# Diseño técnico — Passkeys / Touch ID para Radar 2.0

- **ID:** ADR-AUTH-002
- **Fecha:** 2026-11-21
- **Rama:** `feature/biometric-passkeys`
- **Estado:** Diseño previo a implementación y validación

## 1. Objetivo

Incorporar autenticación mediante Passkeys/WebAuthn en Radar 2.0. En equipos Apple compatibles, el autenticador del sistema puede solicitar Touch ID. La huella o el dato biométrico permanece en el dispositivo; Radar y Supabase reciben la prueba criptográfica WebAuthn, no la huella.

## 2. Arquitectura actual observada

- Aplicación Python con Streamlit.
- Autenticación actual mediante `supabase.auth.sign_in_with_password`.
- Cliente Supabase Python compartido por proceso mediante caché.
- El estado de sesión de la interfaz se mantiene en `st.session_state.radar_user`.
- Dependencias actuales declaran `supabase>=2.0.0` y `streamlit>=1.35.0`.

## 3. Restricción técnica relevante

La guía oficial de Supabase documenta Passkeys en `supabase-js` v2.105.0 o posterior y marca la API como experimental. Incluye `registerPasskey()`, `signInWithPasskey()` y administración de credenciales. La API documentada es JavaScript; no se debe asumir que el cliente Python instalado expone esos métodos.

Por tanto, la integración con Streamlit requiere un componente de navegador que ejecute WebAuthn y use el cliente JavaScript oficial de Supabase. El puente navegador-servidor debe transmitir únicamente el resultado necesario para establecer la sesión; nunca una contraseña, clave privilegiada ni material biométrico.

## 4. Flujo propuesto

### Registro
1. El usuario inicia sesión con el método actual.
2. Abre Seguridad de la cuenta y selecciona «Registrar Passkey».
3. El componente de navegador invoca `supabase.auth.registerPasskey()`.
4. El navegador solicita Touch ID, PIN del dispositivo o autenticador disponible.
5. Supabase Auth verifica y registra la credencial.
6. Radar informa el resultado y permite identificar la credencial registrada.

### Inicio de sesión
1. En la pantalla de acceso se ofrece «Ingresar con Passkey».
2. El navegador ejecuta `supabase.auth.signInWithPasskey()`.
3. WebAuthn solicita autenticación al usuario.
4. Supabase Auth valida la firma y devuelve la sesión.
5. Radar establece la sesión de usuario con el contexto autenticado, sin exponer claves privilegiadas.

### Alternativa y recuperación
- Mantener correo/contraseña mientras Passkeys esté en etapa experimental.
- La cancelación o indisponibilidad de WebAuthn no debe bloquear el acceso alternativo.
- Incluir cierre de sesión y expiración de sesión en las pruebas.

## 5. Orígenes y dominios

- WebAuthn requiere contexto seguro: HTTPS en dominios publicados.
- Para desarrollo local, loopback/localhost es una excepción permitida.
- El RP ID debe ser el dominio base final, sin protocolo, puerto ni ruta.
- Los orígenes permitidos deben enumerar los entornos autorizados.
- El RP ID debe elegirse cuidadosamente: cambiarlo invalida las Passkeys ya registradas para el RP anterior.
- No registrar una Passkey definitiva hasta decidir el dominio de producción.

## 6. Decisiones de seguridad

- Repositorio GitHub privado.
- La clave publishable/anon puede estar disponible en el cliente conforme al diseño de Supabase; las políticas RLS son obligatorias.
- Nunca incluir service-role/secret key en el componente de navegador.
- No almacenar tokens en logs ni mostrarlos en pantalla.
- No compartir estado de sesión entre usuarios por el cliente global cacheado; revisar el ciclo de vida del cliente antes de producción multiusuario.
- La sesión y cada consulta deben quedar vinculadas al usuario autenticado.
- Las Passkeys se administran para el usuario actual; la revocación administrativa, si se incorpora, debe ejecutarse exclusivamente en servidor confiable.

## 7. Pruebas de aceptación

| ID | Prueba | Resultado esperado |
|---|---|---|
| PK-001 | Registrar Passkey con usuario autenticado | Credencial registrada en Supabase Auth. |
| PK-002 | Intentar registrar sin sesión | Operación denegada. |
| PK-003 | Iniciar sesión con Passkey registrada | Sesión válida para el usuario correcto. |
| PK-004 | Cancelar el diálogo biométrico | Mensaje controlado; no se rompe la pantalla. |
| PK-005 | Navegador/dispositivo sin WebAuthn | Se informa y permanece el acceso alternativo. |
| PK-006 | Cerrar sesión y volver a ingresar | La sesión anterior no se reutiliza indebidamente. |
| PK-007 | Credencial de otro usuario | No permite suplantación ni acceso a datos ajenos. |
| PK-008 | Origen no autorizado | Supabase rechaza la ceremonia. |
| PK-009 | Verificar repositorio y frontend | No hay claves secretas ni tokens en código, logs o capturas. |
| PK-010 | Expiración/renovación | Sesión expirada se maneja sin dejar datos privados visibles. |

## 8. Condiciones para integrar

- La versión de `supabase-js` debe cumplir el mínimo oficial vigente.
- Configuración Passkey habilitada en Supabase Auth para el proyecto de Radar 2.0.
- RP ID y orígenes definidos para cada entorno.
- Pruebas locales aprobadas y luego repetidas en el dominio HTTPS definitivo.
- Acceso alternativo probado.
- Aislamiento multiusuario probado.
- Pull Request revisado y aprobado antes del merge.

## 9. Fuente oficial

Supabase — Passkey authentication:
https://supabase.com/docs/guides/auth/passkeys

La API es experimental y puede cambiar. Antes de integrar, verificar de nuevo la documentación y las versiones efectivamente instaladas.
