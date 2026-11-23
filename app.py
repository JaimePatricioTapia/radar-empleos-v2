"""Interfaz Radar 2.0: Auth, CV seguro, búsqueda automática y evaluación manual."""
from __future__ import annotations

import streamlit as st

from src.evaluation.service import evaluate_job_offer
from src.config import get_settings
from src.cv.service import ingest_cv_upload
from src.db.client import get_supabase_client
from src.search.ingestion import DEFAULT_SOURCES, DEFAULT_TARGET_ROLES
from src.search.processing import MINIMUM_AFFINITY_SCORE, classify_sector
from src.search.pipeline import run_full_search_pipeline
from src.search.sources import SOURCE_REGISTRY

st.set_page_config(page_title="Radar de Empleos 2.0", page_icon="🎯", layout="wide")
st.title("Radar de Empleos 2.0")
st.caption("Buscador multifuente y evaluador inteligente · Entorno independiente de desarrollo")

settings = get_settings()
if "supabase_client" not in st.session_state:
    try:
        # Cada sesión de Streamlit conserva su propio cliente y estado Auth.
        st.session_state.supabase_client = get_supabase_client()
    except Exception as exc:
        st.error(f"No se pudo configurar Supabase: {type(exc).__name__}.")
        st.info("Configure SUPABASE_URL y SUPABASE_KEY en los secretos de Streamlit Cloud o en .env local.")
        st.stop()
client = st.session_state.supabase_client

if "radar_user" not in st.session_state:
    st.session_state.radar_user = None

if st.session_state.radar_user is None:
    st.subheader("Acceso")
    login_tab, signup_tab = st.tabs(["Iniciar sesión", "Crear cuenta"])
    with login_tab:
        with st.form("radar_login"):
            email = st.text_input("Correo electrónico", key="login_email")
            password = st.text_input("Contraseña", type="password", key="login_password")
            submitted = st.form_submit_button("Ingresar", type="primary")
        if submitted:
            try:
                auth = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
                if auth.user:
                    st.session_state.radar_user = {"id": auth.user.id, "email": auth.user.email}
                    st.rerun()
                st.error("No se pudo iniciar sesión. Verifique sus credenciales.")
            except Exception:
                st.error("No se pudo iniciar sesión. Revise el correo, contraseña y configuración de Supabase Auth.")
    with signup_tab:
        with st.form("radar_signup"):
            new_email = st.text_input("Correo electrónico", key="signup_email")
            new_password = st.text_input("Contraseña (mínimo 8 caracteres)", type="password", key="signup_password")
            confirm_password = st.text_input("Repita la contraseña", type="password", key="signup_confirm")
            create_account = st.form_submit_button("Crear cuenta")
        if create_account:
            if new_password != confirm_password:
                st.error("Las contraseñas no coinciden.")
            elif len(new_password) < 8:
                st.error("La contraseña debe tener al menos 8 caracteres.")
            else:
                try:
                    auth = client.auth.sign_up({"email": new_email.strip(), "password": new_password})
                    if auth.session and auth.user:
                        st.session_state.radar_user = {"id": auth.user.id, "email": auth.user.email}
                        st.rerun()
                    st.success("Cuenta creada. Si la confirmación de correo está habilitada, revise su bandeja y luego inicie sesión.")
                except Exception:
                    st.error("No se pudo crear la cuenta. Revise el correo e inténtelo nuevamente.")
    st.stop()

user = st.session_state.radar_user
with st.sidebar:
    st.success("Sesión iniciada")
    st.caption(user.get("email") or "Usuario autenticado")
    if st.button("Cerrar sesión"):
        try:
            client.auth.sign_out()
        finally:
            st.session_state.radar_user = None
            st.session_state.pop("supabase_client", None)
            st.rerun()

st.subheader("Mi currículum")
st.write("Cargue su CV en PDF. El archivo se procesa temporalmente en el servidor y se elimina al terminar; solo se guardan el texto extraído, sus fragmentos y embeddings, protegidos por su cuenta.")
uploaded_cv = st.file_uploader("Seleccionar CV (PDF, máximo 15 MB)", type=["pdf"], key="cv_pdf_upload")
if st.button("Procesar mi CV", type="primary", disabled=uploaded_cv is None):
    with st.spinner("Leyendo CV, generando embeddings y guardando información..."):
        try:
            result = ingest_cv_upload(uploaded_cv.getvalue(), uploaded_cv.name, client=client, user_id=user["id"])
            st.success(
                "CV ya procesado: se reutilizaron sus embeddings existentes sin consumir cuota."
                if result.get("cached")
                else "CV procesado y guardado correctamente."
            )
            st.metric("Fragmentos guardados", result["chunk_count"])
            st.caption(f"Versión: {result['cv_version_id']} · Modelo: {result['embedding_model']}")
            st.caption(f"SHA-256: {result['cv_hash']}")
            if result.get("cached"):
                st.caption("Caché activa por hash SHA-256 y modelo de embeddings.")
        except Exception as exc:
            st.error(f"No se pudo procesar el CV: {type(exc).__name__}: {exc}")
st.divider()
st.header("🔎 Búsqueda y evaluación automática")
st.write(
    "Una sola acción consulta los portales seleccionados, guarda las ofertas nuevas, "
    "prepara sus descripciones y embeddings, las compara con la evidencia de su CV "
    "y actualiza la bandeja priorizada. No necesita ejecutar etapas intermedias."
)
st.info(
    f"Umbral de recomendación: **{MINIMUM_AFFINITY_SCORE}%**. "
    "La afinidad se calcula contrastando los requisitos de cada oferta con evidencia "
    "verificable del currículum; las brechas no demostradas no se dan por cumplidas."
)
st.warning(
    "La cobertura depende de la disponibilidad y estructura de cada portal. "
    "LinkedIn se consulta mediante resultados públicos de JobSpy, sin iniciar sesión en su cuenta."
)

source_labels = {key: label for key, (label, _) in SOURCE_REGISTRY.items()}
selected_sources = st.multiselect(
    "Portales y buscadores",
    options=list(SOURCE_REGISTRY),
    default=DEFAULT_SOURCES,
    format_func=lambda value: source_labels[value],
)
selected_roles = st.multiselect(
    "Cargos objetivo",
    options=DEFAULT_TARGET_ROLES,
    default=DEFAULT_TARGET_ROLES,
)
limit_per_query = st.slider(
    "Máximo de resultados por cargo y portal",
    min_value=5,
    max_value=30,
    value=10,
    step=5,
)
estimated_queries = len(selected_sources) * len(selected_roles)
st.caption(f"El barrido ejecutará hasta {estimated_queries} consultas de búsqueda.")

try:
    active_cv = (
        client.table("cv_versions")
        .select("id")
        .eq("user_id", user["id"])
        .eq("is_active", True)
        .limit(1)
        .execute()
        .data
        or []
    )
except Exception as exc:
    active_cv = []
    st.error(f"No se pudo verificar el currículum activo: {exc}")

if not active_cv:
    st.warning("Antes de iniciar, procese su currículum en la sección «Mi currículum».")

run_pipeline = st.button(
    "🚀 Buscar y evaluar ofertas automáticamente",
    type="primary",
    disabled=not selected_sources or not selected_roles or not active_cv,
    use_container_width=True,
)
if run_pipeline:
    status = st.status("Iniciando búsqueda integral…", expanded=True)
    progress_line = st.empty()
    try:
        result = run_full_search_pipeline(
            client,
            user_id=user["id"],
            roles=selected_roles,
            sources=selected_sources,
            limit_per_query=limit_per_query,
            progress=lambda message: progress_line.write(message),
        )
        discovery = result["discovery"]
        preparation = result["preparation"]
        evaluation = result["evaluation"]
        status.update(
            label=(
                "Proceso pausado por protección de cuota gratuita"
                if result.get("paused_for_free_quota")
                else "Proceso integral finalizado" if result["completed"]
                else "Proceso finalizado con incidencias"
            ),
            state="complete" if result["completed"] or result.get("paused_for_free_quota") else "error",
            expanded=not result["completed"],
        )
        st.subheader("Resumen de esta ejecución")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ofertas encontradas", discovery["total_found"])
        c2.metric("Nuevas guardadas", discovery["saved"])
        c3.metric("Ofertas preparadas", preparation["offers_chunked"])
        c4.metric("Evaluadas con Gemini", evaluation["evaluated"])
        c5.metric(f"Recomendables ≥{MINIMUM_AFFINITY_SCORE}%", len(evaluation["results"]))
        st.caption(
            f"Duplicadas: {discovery['duplicates']} · "
            f"Descripciones insuficientes: {preparation['insufficient']} · "
            f"Excluidas por preferencias: {preparation['excluded']} · "
            f"Evaluaciones bajo el umbral: {evaluation['below_threshold']}"
        )
        st.caption(
            f"Lotes de preparación: {preparation['batches']} · "
            f"Lotes de evaluación: {evaluation['batches']} · "
            f"Ofertas pendientes de preparación: {preparation['pending_remaining']}"
        )
        if result.get("paused_for_free_quota"):
            st.warning(
                "Se alcanzó el límite preventivo gratuito configurado en Radar. "
                "No se hicieron más llamadas a Gemini. Los resultados y fragmentos "
                "ya guardados se conservaron; las ofertas pendientes se podrán "
                "procesar cuando se renueve la ventana móvil de 24 horas."
            )
            st.caption(
                f"Embeddings: {preparation.get('chunks_embedded_last_24h', 0)}/{settings.max_daily_job_chunks} "
                f"fragmentos en las últimas 24 h · "
                f"Evaluaciones: {settings.max_daily_evaluations - evaluation.get('budget_remaining', 0)}/{settings.max_daily_evaluations} "
                "en las últimas 24 h."
            )
        st.subheader("Resultado por portal")
        for source, values in discovery["by_source"].items():
            st.write(
                f"**{source_labels.get(source, source)}:** {values['found']} encontradas · "
                f"{values['saved']} nuevas · {values['duplicates']} duplicadas · "
                f"{values['errors']} errores"
            )
        if evaluation["errors"] or discovery["error_details"]:
            with st.expander("Ver incidencias del proceso"):
                for error in evaluation["errors"]:
                    st.write(f"- {error}")
                for error in discovery["error_details"]:
                    st.write(f"- {error}")
        if result["completed"]:
            st.success(
                f"La bandeja priorizada se actualizó con las ofertas que alcanzan el {MINIMUM_AFFINITY_SCORE}%."
            )
        elif result.get("paused_for_free_quota"):
            st.info("La búsqueda quedó pausada de forma segura para proteger la cuota gratuita. Los resultados parciales están disponibles en la bandeja.")
        else:
            st.info("Los resultados parciales quedaron guardados. Revise las incidencias antes de reintentar.")
    except Exception as exc:
        status.update(label="El proceso se detuvo; se conservaron los resultados guardados", state="error")
        st.error(f"No se pudo completar el proceso integral: {type(exc).__name__}: {exc}")
        st.info("Puede volver a ejecutar el mismo botón. Las ofertas guardadas y evaluaciones existentes no deberían duplicarse.")

st.divider()
st.header("📌 Bandeja priorizada")
st.caption(
    f"Solo se muestran ofertas NUEVAS con afinidad profesional igual o superior a "
    f"{MINIMUM_AFFINITY_SCORE}%. El orden prioriza afinidad; el sector solo desempata."
)
sector_filter = st.selectbox(
    "Filtro sectorial",
    options=["Todos los sectores", "Solo minería"],
    key="inbox_sector_filter",
)
try:
    inbox_query = (client.table("job_offers")
                   .select("id,title,company,location,source,source_url,description,lifecycle_status,sector_category,affinity_score,priority_score,raw_metadata")
                   .eq("user_id", user["id"]).eq("lifecycle_status", "NUEVA")
                   .gte("affinity_score", MINIMUM_AFFINITY_SCORE)
                   .order("affinity_score", desc=True)
                   .order("priority_score", desc=True))
    inbox = inbox_query.limit(1000).execute().data or []
    # Recalcular en memoria con el clasificador vigente para no depender de
    # categorías antiguas que pudieron quedar mal asignadas.
    for item in inbox:
        item["sector_category"] = classify_sector(item)
    inbox = [item for item in inbox if not (item.get("raw_metadata") or {}).get("evaluation_filter")]
    if sector_filter == "Solo minería":
        inbox = [item for item in inbox if item["sector_category"] in ("MINERIA", "PROVEEDOR_MINERO")]
    inbox.sort(
        key=lambda item: (item.get("affinity_score") or -1, item.get("priority_score") or -1),
        reverse=True,
    )
    if not inbox:
        if sector_filter == "Solo minería":
            st.info(f"No hay ofertas mineras NUEVAS con afinidad igual o superior a {MINIMUM_AFFINITY_SCORE}%.")
        else:
            st.info(f"No hay ofertas NUEVAS con afinidad igual o superior a {MINIMUM_AFFINITY_SCORE}%. Prepare y evalúe más ofertas para ampliar las recomendaciones.")
    for item in inbox:
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.write(
                f"{item.get('company') or 'Empresa no informada'} · "
                f"{item.get('sector_category') or 'POR_CLASIFICAR'}"
            )
            if item.get("affinity_score") is not None:
                st.write(
                    f"Afinidad: **{item['affinity_score']}%** · "
                    f"Prioridad: **{item.get('priority_score') or 0}/100**"
                )
            else:
                st.caption("Pendiente de evaluación")
            if item.get("source_url"):
                st.link_button("Abrir publicación", item["source_url"])
            with st.form(f"lifecycle_{item['id']}"):
                new_status = st.selectbox(
                    "Estado", ["NUEVA", "POSTULADO", "DESCARTADO", "CADUCADO", "ERROR"],
                    index=0, key=f"status_{item['id']}"
                )
                reason = st.text_input("Motivo / nota (opcional)", key=f"reason_{item['id']}")
                save_status = st.form_submit_button("Guardar estado")
            if save_status and new_status != item["lifecycle_status"]:
                try:
                    client.rpc("set_job_offer_lifecycle_status", {
                        "target_job_offer_id": item["id"],
                        "new_status": new_status,
                        "reason": reason.strip() or None
                    }).execute()
                    if new_status == "POSTULADO":
                        client.table("applications").upsert({
                            "user_id": user["id"], "job_offer_id": item["id"],
                            "status": "postulado", "notes": reason.strip() or None
                        }, on_conflict="user_id,job_offer_id").execute()
                    st.success("Estado actualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"No se pudo actualizar el estado: {exc}")
except Exception as exc:
    st.error(f"No se pudo cargar la bandeja: {exc}")

st.divider()
st.subheader("Evaluar una oferta manualmente")
st.write("Función complementaria: puede pegar un aviso que encontró por su cuenta. No reemplaza la búsqueda automática.")
with st.form("evaluate_offer_form"):
    offer_title = st.text_input("Cargo", placeholder="Business Analyst Senior")
    offer_company = st.text_input("Empresa (opcional)")
    offer_location = st.text_input("Ubicación (opcional)")
    offer_url = st.text_input("URL del aviso (opcional)")
    offer_description = st.text_area("Descripción y requisitos", height=200, placeholder="Pegue aquí el contenido completo del aviso...")
    evaluate_submitted = st.form_submit_button("Evaluar compatibilidad")
if evaluate_submitted:
    if not offer_title.strip() or not offer_description.strip():
        st.warning("Debe ingresar el cargo y la descripción de la oferta.")
    else:
        payload = {
            "title": offer_title, "company": offer_company or None,
            "location": offer_location or None, "source_url": offer_url or None,
            "source": "manual", "description": offer_description,
        }
        with st.spinner("Buscando evidencia en su CV y evaluando con Gemini..."):
            try:
                result = evaluate_job_offer(payload, client=client, user_id=user["id"])
                evaluation = result["evaluation"]
                st.success("Evaluación guardada en Radar 2.0.")
                score_col, verdict_col = st.columns(2)
                score_col.metric("Compatibilidad estimada", f"{evaluation['score_match']}/100")
                verdict_col.metric("Recomendación", evaluation["verdict"])
                st.markdown("**Fortalezas identificadas**")
                for item in evaluation.get("strengths", []):
                    st.write(f"- {item}")
                st.markdown("**Brechas identificadas**")
                for item in evaluation.get("gaps", []):
                    st.write(f"- {item}")
                st.markdown("**Evidencia recuperada del CV**")
                for item in result["evidence"]:
                    with st.expander(f"{item['section']} · similitud {item.get('similarity', 0):.3f}"):
                        st.write(item["text"])
                st.caption(f"Modelo: {result['model']} · Prompt: {result['prompt_version']} · ID evaluación: {result['evaluation_id']}")
                if result.get("cached"):
                    st.caption("Resultado recuperado del historial; no se realizaron llamadas a Gemini.")
            except Exception as exc:
                st.error(f"No se pudo completar la evaluación: {exc}")
