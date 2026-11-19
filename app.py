"""Interfaz Radar 2.0: Auth, CV local, búsqueda automática y evaluación manual."""
from __future__ import annotations

import streamlit as st

from src.evaluation.service import evaluate_job_offer
from src.config import get_settings
from src.cv.service import ingest_cv
from src.db.client import get_supabase_client
from src.search.ingestion import DEFAULT_SOURCES, DEFAULT_TARGET_ROLES, run_discovery
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
