"""Interfaz inicial de Radar 2.0: autenticación e ingesta local del CV."""
from __future__ import annotations

import streamlit as st

from src.evaluation.service import evaluate_job_offer

from src.config import get_settings
from src.cv.service import ingest_cv
from src.db.client import get_supabase_client

st.set_page_config(page_title="Radar de Empleos 2.0", page_icon="🎯", layout="wide")
st.title("Radar de Empleos 2.0")
st.caption("Entorno independiente de desarrollo · Supabase Auth + Gemini")

settings = get_settings()

try:
    client = get_supabase_client()
except Exception as exc:
    st.error(f"No se pudo configurar Supabase: {exc}")
    st.info("Revise SUPABASE_URL y SUPABASE_KEY en su archivo .env. Use la clave publicable del proyecto Radar Empleos 2.0.")
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
st.subheader("Estado de la siguiente etapa")
st.divider()
st.subheader("Evaluar una oferta laboral")
st.write("Pegue una oferta. Radar buscará evidencia pertinente en su CV y enviará esos fragmentos a Gemini para una evaluación estructurada.")
with st.form("evaluate_offer_form"):
    offer_title = st.text_input("Cargo", placeholder="Business Analyst Senior")
    offer_company = st.text_input("Empresa (opcional)")
    offer_location = st.text_input("Ubicación (opcional)")
    offer_url = st.text_input("URL del aviso (opcional)")
    offer_description = st.text_area("Descripción y requisitos", height=240, placeholder="Pegue aquí el contenido completo del aviso...")
    evaluate_submitted = st.form_submit_button("Evaluar compatibilidad", type="primary")

if evaluate_submitted:
    if not offer_title.strip() or not offer_description.strip():
        st.warning("Debe ingresar el cargo y la descripción de la oferta.")
    else:
        payload = {
            "title": offer_title,
            "company": offer_company or None,
            "location": offer_location or None,
            "source_url": offer_url or None,
            "source": "manual",
            "description": offer_description,
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
