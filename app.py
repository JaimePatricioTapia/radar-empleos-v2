"""Interfaz Radar 2.0: Auth, CV local, búsqueda automática y evaluación manual."""
from __future__ import annotations

import streamlit as st

from src.evaluation.service import evaluate_job_offer
from src.config import get_settings
from src.cv.service import ingest_cv
from src.db.client import get_supabase_client
from src.search.ingestion import DEFAULT_SOURCES, DEFAULT_TARGET_ROLES, run_discovery
from src.search.processing import build_job_chunks, evaluate_top_offers, get_processing_status
from src.search.sources import SOURCE_REGISTRY

st.set_page_config(page_title="Radar de Empleos 2.0", page_icon="🎯", layout="wide")
st.title("Radar de Empleos 2.0")
st.caption("Buscador multifuente y evaluador inteligente · Entorno independiente de desarrollo")

settings = get_settings()
try:
    client = get_supabase_client()
except Exception as exc:
    st.error(f"No se pudo configurar Supabase: {exc}")
    st.info("Revise SUPABASE_URL y SUPABASE_KEY en su archivo .env.")
    st.stop()

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
            st.rerun()

st.subheader("Mi currículum")
st.write("El PDF se procesa desde su computador. Solo se guardan el texto extraído, sus fragmentos y embeddings; el archivo original no se sube.")
cv_path = st.text_input("Ruta local del PDF", value=settings.cv_pdf_path or "", placeholder="/Users/usuario/Documents/CV.pdf")
if st.button("Procesar mi CV", type="primary", disabled=not cv_path.strip()):
    with st.spinner("Leyendo CV, generando embeddings y guardando información..."):
        try:
            result = ingest_cv(cv_path.strip(), client=client, user_id=user["id"])
            st.success("CV procesado y guardado correctamente.")
            st.metric("Fragmentos guardados", result["chunk_count"])
            st.caption(f"Versión: {result['cv_version_id']} · Modelo: {result['embedding_model']}")
            st.caption(f"SHA-256: {result['cv_hash']}")
        except FileNotFoundError:
            st.error("No se encontró el PDF. Revise la ruta local.")
        except Exception as exc:
            st.error(f"No se pudo procesar el CV: {exc}")

st.divider()
st.header("🔎 Búsqueda automática de empleos")
st.write(
    "Radar consulta portales y buscadores laborales, normaliza los avisos, elimina duplicados "
    "y guarda las oportunidades encontradas en su espacio privado. En esta etapa no consume "
    "Gemini para evaluar cada aviso; primero construimos una base limpia de oportunidades."
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
limit_per_query = st.slider("Máximo de resultados por cargo y portal", min_value=5, max_value=30, value=10, step=5)

estimated_queries = len(selected_sources) * len(selected_roles)
st.caption(f"Este barrido ejecutará hasta {estimated_queries} consultas. Cada portal puede devolver menos resultados.")
run_search = st.button(
    "🚀 Ejecutar búsqueda multifuente",
    type="primary",
    disabled=not selected_sources or not selected_roles,
)
if run_search:
    status = st.status("Iniciando rastreo de portales…", expanded=True)
    progress_line = st.empty()
    try:
        def report_progress(message: str):
            progress_line.write(message)
        result = run_discovery(
            client, user_id=user["id"], roles=selected_roles,
            sources=selected_sources, limit_per_query=limit_per_query,
            progress=report_progress,
        )
        status.update(label="Búsqueda finalizada", state="complete", expanded=False)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ofertas encontradas", result["total_found"])
        c2.metric("Nuevas guardadas", result["saved"])
        c3.metric("Duplicadas", result["duplicates"])
        c4.metric("Errores", result["errors"])
        st.subheader("Resultado por portal")
        for source, values in result["by_source"].items():
            label = source_labels.get(source, source)
            st.write(
                f"**{label}:** {values['found']} encontradas · "
                f"{values['saved']} nuevas · {values['duplicates']} duplicadas · "
                f"{values['errors']} errores"
            )
        if result["offers"]:
            st.subheader("Ofertas nuevas capturadas")
            for offer in result["offers"]:
                title = offer.get("title") or "Sin título"
                company = offer.get("company") or "Empresa no informada"
                location = offer.get("location") or "Ubicación no informada"
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.caption(f"{company} · {location} · {source_labels.get(offer.get('source'), offer.get('source'))}")
                    if offer.get("source_url"):
                        st.link_button("Abrir oferta original", offer["source_url"])
        if result["error_details"]:
            with st.expander(f"Ver {len(result['error_details'])} incidencias de los portales"):
                for detail in result["error_details"]:
                    st.write(f"- {detail}")
        st.info(
            "Las ofertas ya están guardadas, pero aún no tienen puntuación de compatibilidad. "
            "La siguiente etapa conectará estos registros con embeddings de ofertas, pgvector y Gemini."
        )
    except Exception as exc:
        status.update(label="La búsqueda no pudo completarse", state="error")
        st.error(f"Error ejecutando la búsqueda: {exc}")


st.divider()
st.header("🧠 Preparación semántica y evaluación")
st.write(
    "Primero procesamos las ofertas en lotes y comparamos sus fragmentos con los del CV. "
    "Gemini no se ejecuta durante esta preparación: solo se activa cuando todas las ofertas "
    "con descripción suficiente ya están vectorizadas."
)
try:
    processing = get_processing_status(client, user_id=user["id"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ofertas nuevas", processing["new_offers"])
    m2.metric("Ofertas preparadas", processing["chunked_offers"])
    m3.metric("Pendientes de preparar", processing["pending_chunking"])
    m4.metric("Sin descripción suficiente", processing["needs_description"])
    chunk_limit = st.slider("Ofertas a preparar en este lote", 25, 200, 100, 25)
    if processing["pending_chunking"] > 0:
        if st.button("🧩 Preparar siguiente lote (sin Gemini)", type="primary"):
            with st.spinner("Fragmentando ofertas y generando embeddings..."):
                result = build_job_chunks(client, user_id=user["id"], limit=chunk_limit)
            st.success(
                f"Lote procesado: {result['offers_chunked']} ofertas y "
                f"{result['chunks_saved']} fragmentos vectorizados."
            )
            st.caption(f"Descripciones insuficientes en este lote: {result['insufficient']}.")
    elif processing["chunked_offers"] > 0:
        st.success("Todas las ofertas con descripción suficiente ya están preparadas.")
    if processing["needs_description"] > 0:
        st.warning(
            f"{processing['needs_description']} ofertas no se evaluarán todavía porque "
            "su descripción es demasiado corta o incompleta."
        )
    top_k = st.slider("Máximo de ofertas que recibirá Gemini", 10, 100, 35, 5)
    can_evaluate = processing["pending_chunking"] == 0 and processing["chunked_offers"] > 0
    if st.button("🎯 Evaluar las mejores ofertas con Gemini", type="primary", disabled=not can_evaluate):
        with st.spinner("Comparando similitud semántica y evaluando solo el top seleccionado..."):
            try:
                eval_stats = evaluate_top_offers(client, user_id=user["id"], top_k=top_k)
                c1, c2, c3 = st.columns(3)
                c1.metric("Preseleccionadas", eval_stats["ranked"])
                c2.metric("Evaluadas con Gemini", eval_stats["evaluated"])
                c3.metric("Filtradas por preferencias", eval_stats["skipped_excluded"])
                if eval_stats["results"]:
                    st.subheader("Mejores oportunidades evaluadas")
                    for item in eval_stats["results"]:
                        with st.container(border=True):
                            st.markdown(f"**{item['title']}**")
                            st.write(
                                f"{item.get('company') or 'Empresa no informada'} · "
                                f"{item['sector_category']} · Afinidad **{item['affinity_score']}%** · "
                                f"Prioridad **{item['priority_score']}/100**"
                            )
                            st.caption(
                                f"Veredicto: {item['verdict']} · "
                                f"Similitud semántica previa: {item.get('semantic_similarity')}"
                            )
                            if item.get("source_url"):
                                st.link_button("Abrir oferta original", item["source_url"])
                if eval_stats["errors"]:
                    with st.expander(f"Incidencias ({len(eval_stats['errors'])})"):
                        for error in eval_stats["errors"]:
                            st.write(f"- {error}")
            except Exception as exc:
                st.error(f"No se pudo completar la evaluación: {type(exc).__name__}: {exc}")
except Exception as exc:
    st.error(f"No se pudo consultar el estado de preparación: {exc}")

st.divider()
st.header("📌 Bandeja priorizada")
st.caption("Solo se muestran oportunidades nuevas. El orden usa prioridad estratégica y afinidad calculadas.")
try:
    inbox = (client.table("job_offers")
             .select("id,title,company,location,source,source_url,lifecycle_status,sector_category,affinity_score,priority_score,raw_metadata")
             .eq("user_id", user["id"]).eq("lifecycle_status", "NUEVA")
             .order("priority_score", desc=True).order("affinity_score", desc=True)
             .limit(100).execute().data or [])
    inbox = [item for item in inbox if not (item.get("raw_metadata") or {}).get("evaluation_filter")]
    inbox.sort(key=lambda item: (item.get("priority_score") is not None, item.get("priority_score") or -1, item.get("affinity_score") or -1), reverse=True)
    if not inbox:
        st.info("Todavía no hay ofertas nuevas en la bandeja.")
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
            except Exception as exc:
                st.error(f"No se pudo completar la evaluación: {exc}")
