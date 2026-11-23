"""Interfaz Radar 2.0: Auth, CV seguro, búsqueda automática y evaluación manual."""
from __future__ import annotations

import streamlit as st

from src.evaluation.service import evaluate_job_offer
from src.config import get_settings
from src.cv.service import ingest_cv_upload
from src.db.client import get_supabase_client
from src.search.ingestion import DEFAULT_SOURCES, DEFAULT_TARGET_ROLES
from src.search.processing import MINIMUM_AFFINITY_SCORE, classify_sector
from src.search.task_runner import start_search_task
from src.search.sources import SOURCE_REGISTRY
from src.search.role_families import derive_role_families

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

# Perfil ocupacional derivado de fragmentos ya almacenados del CV activo.
derived_profile = {"families": [], "roles": [], "evidence_count": 0}
try:
    active_cv_version = (
        client.table("cv_versions").select("id")
        .eq("user_id", user["id"]).eq("is_active", True).limit(1).execute().data or []
    )
    if active_cv_version:
        cv_evidence = (
            client.table("cv_chunks").select("content")
            .eq("user_id", user["id"])
            .eq("cv_version_id", active_cv_version[0]["id"])
            .limit(500).execute().data or []
        )
        derived_profile = derive_role_families(cv_evidence)
except Exception as exc:
    st.warning(f"No se pudo derivar el perfil de cargos desde el CV: {type(exc).__name__}. Se conservarán los cargos objetivo manuales.")

st.subheader("Mi currículum")
st.write("Cargue su CV en PDF. El archivo se procesa temporalmente en el servidor y se elimina al terminar; solo se guardan el texto extraído, sus fragmentos y embeddings, protegidos por su cuenta.")
uploaded_cv = st.file_uploader("Seleccionar CV (PDF, máximo 15 MB)", type=["pdf"], key="cv_pdf_upload")
st.caption(
    f"Embeddings: {settings.embedding_model} · {settings.embedding_dimensions} dimensiones · "
    f"Presupuesto preventivo: {settings.max_daily_job_chunks} fragmentos y "
    f"{settings.max_daily_evaluations} evaluaciones por 24 h."
)
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
    "LinkedIn se consulta mediante resultados públicos de JobSpy, sin iniciar sesión en su cuenta. " 
    "Se descartan avisos con fecha verificable superior a 14 días; los portales que no informan fecha se identifican por separado."
)

source_labels = {key: label for key, (label, _) in SOURCE_REGISTRY.items()}
selected_sources = st.multiselect(
    "Portales y buscadores",
    options=list(SOURCE_REGISTRY),
    default=DEFAULT_SOURCES,
    format_func=lambda value: source_labels[value],
)
generated_roles = derived_profile.get("roles", [])
role_options = list(dict.fromkeys(generated_roles + DEFAULT_TARGET_ROLES))
default_roles = generated_roles or DEFAULT_TARGET_ROLES
selected_roles = st.multiselect(
    "Cargos y funciones para buscar (derivados del CV + objetivos adicionales)",
    options=role_options,
    default=default_roles,
    help="Las familias derivadas amplían la búsqueda; los cargos objetivo anteriores siguen disponibles como señales adicionales.",
)
role_context = [
    {
        "family_id": family["id"],
        "family_name": family["name"],
        "priority": family["priority"],
        "titles": family["titles"],
        "evidence": family["evidence"],
    }
    for family in derived_profile.get("families", [])
]
limit_per_query = st.slider(
    "Máximo de resultados por consulta y portal",
    min_value=5,
    max_value=30,
    value=10,
    step=5,
)
estimated_queries = sum(
    1 if source == "linkedin" else len(selected_roles)
    for source in selected_sources
)
st.caption(
    f"El barrido ejecutará hasta {estimated_queries} consultas de búsqueda. "
    "LinkedIn agrupa los cargos en una sola consulta para reducir bloqueos por ráfagas."
)
if derived_profile.get("families"):
    with st.expander("Familias funcionales detectadas en su CV", expanded=True):
        st.caption("Análisis local de evidencia ya guardada; no consume Gemini ni vuelve a generar embeddings.")
        for family in derived_profile["families"]:
            st.markdown(
                f"**P{family['priority']} · {family['name']}** — "
                f"{', '.join(family['titles'])}"
            )
            st.caption("Señales encontradas: " + ", ".join(family["evidence"]))
else:
    st.warning("No se pudieron derivar familias del CV activo. Se mantienen disponibles los cargos objetivo anteriores; revise que el CV esté procesado.")

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

active_search_task = st.session_state.get("radar_search_task")
search_already_running = active_search_task is not None and not active_search_task.finished
run_pipeline = st.button(
    "🚀 Buscar y evaluar ofertas automáticamente",
    type="primary",
    disabled=not selected_sources or not selected_roles or not active_cv or search_already_running,
    use_container_width=True,
)
if run_pipeline:
    st.session_state.radar_search_task = start_search_task(
        client,
        user_id=user["id"],
        roles=selected_roles,
        sources=selected_sources,
        limit_per_query=limit_per_query,
        role_context=role_context,
    )

@st.fragment(run_every="1s")
def render_search_task():
    task = st.session_state.get("radar_search_task")
    if task is None:
        return

    while True:
        try:
            event = task.events.get_nowait()
        except Exception:
            break
        if event["type"] == "progress":
            task.latest_progress = event["data"]
        elif event["type"] == "offer":
            recent = getattr(task, "recent_offers", [])
            recent.append(event["data"])
            task.recent_offers = recent[-8:]
        elif event["type"] == "message":
            task.latest_message = event["data"]

    event = getattr(task, "latest_progress", {})
    stage = event.get("stage", "discovery")
    stage_names = {
        "discovery": "1/3 · Búsqueda multifuente",
        "preparation": "2/3 · Preparación semántica",
        "evaluation": "3/3 · Evaluación de afinidad",
    }
    stage_label = stage_names.get(stage, "Proceso integral")
    st.subheader("Estado de la búsqueda")
    if not task.finished:
        if task.stop_requested:
            st.info("Detención solicitada. Radar terminará la consulta actual y continuará con preparación y evaluación.")
        if event.get("last_updated_at"):
            st.caption(f"Última actualización real: {event['last_updated_at']}")
        if stage == "discovery":
            total = max(1, int(event.get("queries_total", estimated_queries)))
            completed = min(total, int(event.get("queries_completed", 0)) + int(event.get("queries_skipped", 0)))
            fraction = completed / total
            st.progress(fraction / 3, text=f"{stage_label} · {completed}/{total} consultas resueltas")
            st.write(
                f"**Portal:** {event.get('source_label', 'Preparando')} · "
                f"**Cargo/consulta:** {event.get('query', '—')}"
            )
        elif stage == "preparation":
            fraction = 1 / 3 if event.get("status") == "running" else 2 / 3
            st.progress(fraction, text=stage_label)
            st.write(
                f"Ofertas preparadas: **{event.get('offers_prepared', 0)}** · "
                f"Fragmentos guardados: **{event.get('chunks_saved', 0)}** · "
                f"Pendientes: **{event.get('pending_remaining', 'calculando')}**"
            )
            if event.get("chunks_total"):
                st.progress(
                    min(1.0, event.get("chunks_saved", 0) / max(1, event.get("chunks_total", 1))),
                    text=f"Lote de embeddings {event.get('embedding_batch', '—')}: "
                         f"{event.get('chunks_saved', 0)}/{event.get('chunks_total', 0)} fragmentos persistidos",
                )
        else:
            fraction = 2 / 3 if event.get("status") != "completed" else 1.0
            st.progress(fraction, text=stage_label)
            st.write(
                f"Evaluadas: **{event.get('evaluated', 0)}** · "
                f"Preseleccionadas: **{event.get('ranked', 0)}** · "
                f"Incidencias: **{event.get('errors', 0)}**"
            )
            if event.get("offers_total"):
                st.progress(
                    min(1.0, event.get("offers_processed", 0) / max(1, event.get("offers_total", 1))),
                    text=f"Ofertas revisadas en este lote: {event.get('offers_processed', 0)}/"
                         f"{event.get('offers_total', 0)}",
                )

        if stage == "discovery":
            metric_cols = st.columns(5)
            metric_cols[0].metric("Consultas", f"{event.get('queries_completed', 0) + event.get('queries_skipped', 0)}/{event.get('queries_total', estimated_queries)}")
            metric_cols[1].metric("Encontradas", event.get("offers_found", 0))
            metric_cols[2].metric("Nuevas guardadas", event.get("offers_saved", 0))
            metric_cols[3].metric("Duplicadas", event.get("duplicates", 0))
            metric_cols[4].metric("Errores", event.get("errors", 0))
            st.caption(
                f"Consultas omitidas por fallos repetidos: {event.get('queries_skipped', 0)} · "
                f"Fuera de 14 días: {event.get('stale_skipped', 0)} · "
                f"Fecha no informada: {event.get('publication_date_unknown', 0)} · "
                f"Tiempo transcurrido: {event.get('elapsed_seconds', 0)} s"
            )
            if not task.stop_requested and st.button(
                "⏹ Detener búsqueda y procesar resultados recopilados",
                type="secondary",
                key="radar_stop_search",
                use_container_width=True,
            ):
                task.request_stop()
                st.warning("Detención solicitada. Se cerrará la consulta actual y luego se prepararán y evaluarán las ofertas guardadas.")
        elif task.stop_requested:
            st.info("La búsqueda se detuvo de forma controlada; Radar está procesando las ofertas recopiladas.")

        recent = getattr(task, "recent_offers", [])
        if recent:
            st.markdown("**Últimas ofertas nuevas guardadas**")
            for offer in reversed(recent[-5:]):
                freshness = "fecha verificada" if offer.get("publication_date_status") == "verified_recent" else "fecha no informada"
                st.write(
                    f"- **{offer.get('title', 'Cargo sin título')}** · "
                    f"{offer.get('company') or 'Empresa no informada'} · "
                    f"{offer.get('source', 'portal')} · {freshness}"
                )
        if getattr(task, "latest_message", None):
            st.caption(task.latest_message)
    else:
        if task.error:
            st.error(f"No se pudo completar el proceso: {task.error}")
            st.info("Las ofertas y los lotes confirmados permanecen guardados. Puede volver a ejecutar el botón; Radar reutilizará el trabajo ya persistido.")
        else:
            result = task.result or {}
            discovery = result.get("discovery", {})
            preparation = result.get("preparation", {})
            evaluation = result.get("evaluation", {})
            if result.get("stopped_early"):
                st.warning("Búsqueda detenida a solicitud. Las ofertas recopiladas se procesaron automáticamente.")
            elif result.get("completed"):
                st.success("Búsqueda, preparación y evaluación finalizadas.")
            elif result.get("paused_for_api_quota"):
                st.warning("La preparación quedó pausada por el límite temporal de Gemini. Los lotes guardados se conservaron.")
            elif result.get("paused_for_free_quota"):
                st.warning("Se alcanzó el presupuesto preventivo gratuito. Los resultados se conservaron y el trabajo pendiente puede reanudarse.")
            else:
                st.info("El proceso terminó con incidencias. Los resultados persistidos se conservaron.")
            cols = st.columns(5)
            cols[0].metric("Encontradas", discovery.get("total_found", 0))
            cols[1].metric("Nuevas guardadas", discovery.get("saved", 0))
            cols[2].metric("Preparadas", preparation.get("offers_chunked", 0))
            cols[3].metric("Evaluadas", evaluation.get("evaluated", 0))
            cols[4].metric("Afinidad ≥85%", len(evaluation.get("results", [])))
            st.caption(
                f"Duplicadas: {discovery.get('duplicates', 0)} · "
                f"Consultas omitidas por fallos repetidos: {discovery.get('queries_skipped', 0)} · "
                f"Fuera de 14 días: {discovery.get('stale_skipped', 0)} · "
                f"Fecha no informada: {discovery.get('publication_date_unknown', 0)} · "
                f"Errores de búsqueda: {discovery.get('errors', 0)}"
            )
            st.caption(
                f"Pendientes de preparación: {preparation.get('pending_remaining', 0)} · "
                f"Evaluaciones con incidencias: {len(evaluation.get('errors', []))}"
            )
            for source, values in discovery.get("by_source", {}).items():
                st.write(
                    f"**{source_labels.get(source, source)}:** "
                    f"{values.get('found', 0)} encontradas · {values.get('saved', 0)} nuevas · "
                    f"{values.get('duplicates', 0)} duplicadas · {values.get('errors', 0)} errores"
                )
            if discovery.get("error_details") or evaluation.get("errors"):
                with st.expander("Ver incidencias"):
                    for error in discovery.get("error_details", []):
                        st.write(f"- {error}")
                    for error in evaluation.get("errors", []):
                        st.write(f"- {error}")
        if st.button("Cerrar resumen de ejecución", key="radar_close_search_summary"):
            st.session_state.radar_search_task = None
            st.rerun()

if st.session_state.get("radar_search_task") is not None:
    render_search_task()

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
            search_origin = (item.get("raw_metadata") or {}).get("search_origin") or {}
            origin_families = search_origin.get("families") or []
            if origin_families:
                st.caption("Familia de búsqueda: " + ", ".join(
                    family.get("name", family.get("id", ""))
                    for family in origin_families if family
                ))
            publication_status = (item.get("raw_metadata") or {}).get("publication_date_status")
            if publication_status == "unknown":
                st.caption("Fecha de publicación no informada por el portal; antigüedad no verificable.")
            elif publication_status == "verified_recent":
                st.caption("Fecha de publicación verificada: dentro de los últimos 14 días.")
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
                    similarity = item.get("similarity")
                    evidence_label = (
                        f"similitud {similarity:.3f}"
                        if similarity is not None
                        else "evidencia recuperada del historial"
                    )
                    with st.expander(f"{item['section']} · {evidence_label}"):
                        st.write(item["text"])
                st.caption(f"Modelo: {result['model']} · Prompt: {result['prompt_version']} · ID evaluación: {result['evaluation_id']}")
                if result.get("cached"):
                    st.caption("Resultado recuperado del historial; no se realizaron llamadas a Gemini.")
            except Exception as exc:
                st.error(f"No se pudo completar la evaluación: {exc}")
