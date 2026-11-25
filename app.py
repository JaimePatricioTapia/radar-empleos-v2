"""Interfaz Radar 2.0: Auth, CV seguro, búsqueda automática y evaluación manual."""
from __future__ import annotations

import streamlit as st

from src.evaluation.service import evaluate_job_offer
from src.config import get_settings
from src.cv.service import ingest_cv_upload
from src.db.client import get_supabase_client
from src.db.search_preferences import (load_search_preferences, save_search_portal, set_search_portal_enabled, delete_search_portal, save_search_terms, delete_search_term)
from src.search.ingestion import DEFAULT_SOURCES, DEFAULT_TARGET_ROLES, DEFAULT_TARGET_FUNCTIONS
from src.search.processing import MINIMUM_AFFINITY_SCORE, MANUAL_REVIEW_MINIMUM_SCORE, classify_sector
from src.search.task_runner import start_search_task
from src.search.sources import SOURCE_REGISTRY
from src.search.role_families import derive_role_families
from src.cv.skills_profile import derive_skills_profile

st.set_page_config(page_title="Radar de Empleos 2.0", page_icon="🎯", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

    :root {
        --radar-ink: #17263c;
        --radar-muted: #617086;
        --radar-primary: #2457c5;
        --radar-primary-dark: #1b4399;
        --radar-teal: #087f8c;
        --radar-bg: #f5f7fb;
        --radar-surface: #ffffff;
        --radar-border: #e3e9f2;
        --radar-success: #147d55;
        --radar-warning: #a86408;
        --radar-danger: #b43b45;
    }

    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: 'DM Sans', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--radar-ink);
    }
    [data-testid="stAppViewContainer"] {
        background: var(--radar-bg);
    }
    [data-testid="stHeader"] {
        background: rgba(245, 247, 251, 0.92);
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1440px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    h1, h2, h3, h4 {
        font-family: 'Manrope', 'DM Sans', 'Segoe UI', sans-serif !important;
        color: var(--radar-ink) !important;
        letter-spacing: -0.035em;
        line-height: 1.2;
    }
    h1 { font-size: clamp(1.9rem, 3vw, 2.45rem) !important; font-weight: 800 !important; }
    h2 { font-size: 1.65rem !important; font-weight: 750 !important; }
    h3 { font-size: 1.25rem !important; font-weight: 700 !important; }
    p, li, label, .stMarkdown, .stCaption {
        line-height: 1.58;
    }
    [data-testid="stCaptionContainer"], .stCaption {
        color: var(--radar-muted) !important;
        font-size: 0.84rem;
    }
    [data-testid="stSidebar"] {
        background: #eef3fa;
        border-right: 1px solid var(--radar-border);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #34445c;
    }
    [data-testid="stMetric"] {
        background: var(--radar-surface);
        border: 1px solid var(--radar-border);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        box-shadow: 0 2px 8px rgba(23, 38, 60, 0.035);
    }
    [data-testid="stMetricLabel"] {
        color: var(--radar-muted) !important;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        color: var(--radar-ink) !important;
        font-family: 'Manrope', 'DM Sans', sans-serif;
        font-weight: 800;
    }
    [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] div[data-testid="stAlert"] {
        border-radius: 12px;
        border-width: 1px;
    }
    div.stButton > button, div.stFormSubmitButton > button, [data-testid="stLinkButton"] a {
        border-radius: 10px;
        min-height: 2.65rem;
        font-weight: 650;
        letter-spacing: 0.005em;
        transition: background-color 120ms ease, border-color 120ms ease, transform 120ms ease;
    }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
        background: var(--radar-primary);
        border-color: var(--radar-primary);
        color: #ffffff;
    }
    div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button[kind="primary"]:hover {
        background: var(--radar-primary-dark);
        border-color: var(--radar-primary-dark);
        color: #ffffff;
        transform: translateY(-1px);
    }
    div.stButton > button:not([kind="primary"]):hover, div.stFormSubmitButton > button:not([kind="primary"]):hover {
        border-color: #9aafd2;
        color: var(--radar-primary-dark);
    }
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input, [data-testid="stSelectbox"] div[data-baseweb="select"],
    [data-testid="stMultiSelect"] div[data-baseweb="select"] {
        border-radius: 9px;
    }
    [data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
        border-color: var(--radar-primary);
        box-shadow: 0 0 0 1px var(--radar-primary);
    }
    [data-testid="stExpander"] {
        background: var(--radar-surface);
        border: 1px solid var(--radar-border);
        border-radius: 12px;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        font-weight: 650;
        color: #263852;
    }
    [data-testid="stTabs"] button {
        font-weight: 650;
        color: var(--radar-muted);
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--radar-primary);
    }
    [data-testid="stProgress"] > div > div {
        background: var(--radar-primary);
        border-radius: 99px;
    }
    hr {
        border-color: var(--radar-border);
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
    }
    a {
        color: var(--radar-primary);
        font-weight: 600;
    }
    a:hover {
        color: var(--radar-primary-dark);
    }
    /* Foco visible para navegación por teclado y controles deshabilitados. */
    button:focus-visible, a:focus-visible, input:focus-visible,
    textarea:focus-visible, [role="combobox"]:focus-visible {
        outline: 3px solid rgba(36, 87, 197, 0.38);
        outline-offset: 2px;
    }
    div.stButton > button:disabled,
    div.stFormSubmitButton > button:disabled {
        opacity: 0.58;
        cursor: not-allowed;
    }
    @media (max-width: 768px) {
        [data-testid="stMainBlockContainer"] {
            padding: 1rem 1rem 2rem;
        }
        h1 { font-size: 1.8rem !important; }
        h2 { font-size: 1.4rem !important; }
        [data-testid="stMetric"] { padding: 0.8rem; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
try:
    search_preferences = load_search_preferences(client, user_id=user["id"])
except Exception as exc:
    search_preferences = {"portals": [], "terms": []}
    st.warning(
        f"No se pudieron cargar sus preferencias guardadas: {type(exc).__name__}. "
        "Los valores predeterminados siguen disponibles."
    )
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
active_cv_version = []
derived_skills_profile = {"skills": [], "skill_count": 0, "categories": {}}
try:
    active_cv_version = (
        client.table("cv_versions").select("id")
        .eq("user_id", user["id"]).eq("is_active", True).limit(1).execute().data or []
    )
    if active_cv_version:
        cv_evidence = (
            client.table("cv_chunks").select("chunk_id,section,content")
            .eq("user_id", user["id"])
            .eq("cv_version_id", active_cv_version[0]["id"])
            .limit(500).execute().data or []
        )
        derived_profile = derive_role_families(cv_evidence)
        derived_skills_profile = derive_skills_profile(cv_evidence)
except Exception as exc:
    st.warning(f"No se pudo derivar el perfil de cargos desde el CV: {type(exc).__name__}. Se conservarán los cargos objetivo manuales.")

if derived_skills_profile.get("skills"):
    with st.expander(f"Competencias detectadas con evidencia · {derived_skills_profile['skill_count']}", expanded=False):
        st.caption("Inventario inicial extraído del texto del CV. No presume años ni dominio: los niveles solo aparecen cuando están declarados explícitamente. Revise las evidencias antes de postular.")
        for category, count in derived_skills_profile.get("categories", {}).items():
            st.markdown(f"**{category} · {count} competencias**")
            for skill in [item for item in derived_skills_profile["skills"] if item["category"] == category]:
                level = skill.get("proficiency")
                level_label = level if level != "no_declarado" else "nivel no declarado"
                st.markdown(f"- **{skill['name']}** · {level_label}")
                for evidence in skill.get("evidence", [])[:2]:
                    st.caption(f"{evidence['section']} · {evidence['excerpt']}")
        for limitation in derived_skills_profile.get("limitations", []):
            st.caption(f"Nota: {limitation}")
elif active_cv_version:
    st.info("No se detectaron competencias en el texto extraído. Revise que el CV esté correctamente procesado.")

st.subheader("Mi currículum")
st.write("Cargue su CV en PDF. El archivo se procesa temporalmente en el servidor y se elimina al terminar; solo se guardan el texto extraído, sus fragmentos y embeddings, protegidos por su cuenta.")
uploaded_cv = st.file_uploader("Seleccionar CV (PDF, máximo 15 MB)", type=["pdf"], key="cv_pdf_upload")
st.caption(
    f"Embeddings: {settings.embedding_model} · {settings.embedding_dimensions} dimensiones · "
    f"Tope operativo de prueba: {settings.max_daily_job_chunks} fragmentos y "
    f"{settings.max_daily_evaluations} evaluaciones por 24 h (no son cuotas de Google)."
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

# Portales personalizados persistidos en Supabase y aislados por RLS.
portal_rows = search_preferences.get("portals", [])
custom_sources = [
    {
        "id": f"custom_portal_{row['id']}",
        "name": row["name"],
        "url_template": row["url_template"],
    }
    for row in portal_rows if row.get("enabled", True)
]

with st.expander("＋ Administrar portales personalizados", expanded=False):
    st.caption(
        "Los portales quedan guardados en su cuenta y estarán disponibles en futuras sesiones. "
        "Use una URL pública de resultados; puede insertar {query} donde deba ir el término."
    )
    with st.form("radar_add_custom_portal", clear_on_submit=True):
        custom_portal_name = st.text_input("Nombre del portal", placeholder="Ej.: Portal de empleos de una minera")
        custom_portal_url = st.text_input(
            "URL de búsqueda del portal",
            placeholder="https://sitio.cl/trabajos?buscar={query}",
            help="Use resultados públicos; no se admite una página que requiera iniciar sesión.",
        )
        add_custom_portal = st.form_submit_button("Guardar portal")
    if add_custom_portal:
        try:
            save_search_portal(
                client, user_id=user["id"], name=custom_portal_name,
                url_template=custom_portal_url,
            )
            st.success("Portal guardado en su cuenta.")
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo guardar el portal: {type(exc).__name__}: {exc}")
    if portal_rows:
        for portal in portal_rows:
            cols = st.columns([3, 5, 1, 1])
            cols[0].write(f"**{portal['name']}**")
            cols[1].caption(portal["url_template"])
            action = "Desactivar" if portal.get("enabled", True) else "Activar"
            if cols[2].button(action, key=f"toggle_portal_{portal['id']}"):
                set_search_portal_enabled(
                    client, user_id=user["id"], portal_id=portal["id"],
                    enabled=not portal.get("enabled", True),
                )
                st.rerun()
            if cols[3].button("Eliminar", key=f"delete_portal_{portal['id']}"):
                delete_search_portal(client, user_id=user["id"], portal_id=portal["id"])
                st.rerun()
    else:
        st.caption("Todavía no hay portales personalizados guardados.")

source_labels = {key: label for key, (label, _) in SOURCE_REGISTRY.items()}
source_labels.update({item["id"]: item["name"] for item in custom_sources})
source_options = list(SOURCE_REGISTRY) + [item["id"] for item in custom_sources]
selected_sources = st.multiselect(
    "Portales y buscadores",
    options=source_options,
    default=DEFAULT_SOURCES + [item["id"] for item in custom_sources],
    format_func=lambda value: source_labels[value],
    help="Seleccione los portales donde desea buscar. Puede agregar sitios propios arriba.",
)
saved_terms = [item for item in search_preferences.get("terms", []) if item.get("enabled", True)]
saved_roles = [item["term"] for item in saved_terms if item.get("term_type") == "cargo"]
saved_functions = [item["term"] for item in saved_terms if item.get("term_type") == "funcion"]
generated_roles = derived_profile.get("roles", [])
role_options = list(dict.fromkeys(generated_roles + DEFAULT_TARGET_ROLES + saved_roles))
default_roles = list(dict.fromkeys((generated_roles or DEFAULT_TARGET_ROLES) + saved_roles))
selected_roles = st.multiselect(
    "Cargos objetivo",
    options=role_options,
    default=default_roles,
    accept_new_options=True,
    placeholder="Seleccione o escriba cargos y presione Enter",
    help="Puede combinar cargos sugeridos, detectados en su CV y términos propios guardados.",
)
function_options = list(dict.fromkeys(DEFAULT_TARGET_FUNCTIONS + saved_functions))
default_functions = list(dict.fromkeys(DEFAULT_TARGET_FUNCTIONS + saved_functions))
selected_functions = st.multiselect(
    "Funciones y responsabilidades",
    options=function_options,
    default=default_functions,
    accept_new_options=True,
    placeholder="Ej.: continuidad operacional, control de KPI, levantamiento de requisitos",
    help="Busca por actividades concretas aunque el aviso use un nombre de cargo diferente.",
)
with st.expander("Administrar cargos y funciones guardados", expanded=False):
    if saved_terms:
        for term in saved_terms:
            cols = st.columns([2, 4, 1])
            cols[0].caption("Cargo" if term["term_type"] == "cargo" else "Función")
            cols[1].write(term["term"])
            if cols[2].button("Eliminar", key=f"delete_term_{term['id']}"):
                delete_search_term(client, user_id=user["id"], term_id=term["id"])
                st.rerun()
    else:
        st.caption("Los términos personalizados se guardarán al ejecutar una búsqueda.")
role_context = [
    {
        "family_id": family["id"],
        "family_name": family["name"],
        "priority": family["priority"],
        "titles": family["titles"],
        "domain_terms": family["domain_terms"],
        "evidence": family["evidence"],
    }
    for family in derived_profile.get("families", [])
    if any(title in selected_roles for title in family["titles"])
]
limit_per_query = st.slider(
    "Máximo de resultados por consulta y portal",
    min_value=5,
    max_value=30,
    value=15,
    step=5,
)
search_term_count = len(list(dict.fromkeys([*selected_roles, *selected_functions])))
estimated_queries = sum(
    1 if source == "linkedin" else search_term_count
    for source in selected_sources
)
st.caption(
    f"El barrido ejecutará hasta {estimated_queries} consultas de búsqueda. "
    "LinkedIn agrupa cargos y funciones en una sola consulta para reducir bloqueos por ráfagas."
)
if derived_profile.get("families"):
    with st.expander("Familias funcionales detectadas en su CV", expanded=True):
        st.caption("Análisis local de evidencia ya guardada; no consume Gemini ni vuelve a generar embeddings.")
        for family in derived_profile["families"]:
            st.markdown(
                f"**P{family['priority']} · {family['name']}** — "
                f"{', '.join(family['titles'])}"
            )
            st.caption("Competencias/dominio para ampliar consultas: " + ", ".join(family["domain_terms"]))
            st.caption("Señales encontradas en el CV: " + ", ".join(family["evidence"]))
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
# Recuperar el estado de interfaz si el hilo terminó inesperadamente sin alcanzar
# el bloque finally (por ejemplo, reinicio del worker de Streamlit Cloud).
if active_search_task is not None and not active_search_task.finished:
    worker_thread = getattr(active_search_task, "thread", None)
    if worker_thread is None or not worker_thread.is_alive():
        active_search_task.finished = True
        if active_search_task.result is None and not active_search_task.error:
            active_search_task.error = (
                "El proceso en segundo plano ya no está activo. "
                "Puede iniciar una nueva búsqueda; los datos confirmados permanecen guardados."
            )
search_already_running = active_search_task is not None and not active_search_task.finished
if search_already_running:
    st.info(
        "Hay una ejecución anterior todavía activa. Cambiar el filtro sectorial solo modifica "
        "la bandeja; no inicia otra búsqueda. Puede solicitar la detención segura del proceso "
        "desde el panel de estado."
    )
run_pipeline = st.button(
    "🚀 Buscar y evaluar ofertas automáticamente",
    type="primary",
    disabled=not selected_sources or not (selected_roles or selected_functions) or not active_cv or search_already_running,
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
        custom_sources=custom_sources,
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
        if getattr(task, "cancel_requested", False):
            st.info("Cancelación solicitada. Radar terminará la operación externa en curso y detendrá el pipeline sin descartar lo ya guardado.")
        cancel_cols = st.columns([3, 2])
        if not getattr(task, "cancel_requested", False) and cancel_cols[1].button(
            "⏹ Cancelar proceso completo",
            key="radar_cancel_pipeline",
            type="secondary",
            use_container_width=True,
            help="Detiene el pipeline después de la consulta/API actual; conserva ofertas y fragmentos guardados.",
        ):
            task.request_cancel()
            st.warning("Cancelación solicitada. No se iniciarán nuevas consultas ni evaluaciones; se conservarán los datos confirmados.")
        if task.stop_requested:
            st.info("Detención de búsqueda solicitada. Se terminará el descubrimiento y se procesarán los resultados recopilados.")
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
            if "embedding_budget_remaining" in event:
                st.caption(
                    f"Embeddings utilizados últimas 24 h: {event.get('embedding_chunks_used', 0)} · "
                    f"Presupuesto restante: {event.get('embedding_budget_remaining', 0)} · "
                    f"Ofertas pendientes de preparación: {event.get('preparation_pending', 0)}"
                )
                if event.get("preparation_budget_exhausted"):
                    st.warning(
                        "Se alcanzó el límite preventivo de 250 fragmentos de ofertas en 24 h. "
                        "La evaluación continúa con las ofertas que ya tienen fragmentos guardados; "
                        "las nuevas pendientes se prepararán cuando se renueve el presupuesto."
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
            metric_cols[3].metric("Descartadas por pertinencia", event.get("irrelevant_skipped", 0))
            metric_cols[4].metric("Errores", event.get("errors", 0))
            st.caption(
                f"Duplicadas: {event.get('duplicates', 0)} · "
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
        # Inicializar el resultado antes de evaluar task.error: si el worker falla,
        # la vista de resumen igualmente consulta result/preparation más abajo.
        result = task.result or {}
        discovery = result.get("discovery", {})
        preparation = result.get("preparation", {})
        evaluation = result.get("evaluation", {})
        if task.error:
            st.error(f"No se pudo completar el proceso: {task.error}")
            st.info("Las ofertas y los lotes confirmados permanecen guardados. Puede volver a ejecutar el botón; Radar reutilizará el trabajo ya persistido.")
        else:
            result = task.result or {}
            discovery = result.get("discovery", {})
            preparation = result.get("preparation", {})
            evaluation = result.get("evaluation", {})
            if result.get("cancelled"):
                st.warning("Proceso cancelado a solicitud. Las ofertas, evaluaciones y fragmentos confirmados se conservaron; puede iniciar otra búsqueda.")
            elif result.get("stopped_early"):
                st.warning("Búsqueda detenida a solicitud. Las ofertas recopiladas se procesaron automáticamente.")
            elif result.get("completed"):
                st.success("Búsqueda, preparación y evaluación finalizadas.")
            elif evaluation.get("api_quota_paused"):
                retry_seconds = evaluation.get("retry_after_seconds")
                retry_note = (f" Google indicó esperar {int(retry_seconds):,} segundos antes de reintentar.".replace(",", ".")
                              if retry_seconds else "")
                st.warning(
                    "La evaluación quedó pausada por el límite temporal de Gemini. "
                    "Las evaluaciones ya guardadas se conservaron y las ofertas pendientes "
                    "se pueden retomar con una nueva ejecución." + retry_note
                )
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
                f"Descartadas por pertinencia: {discovery.get('irrelevant_skipped', 0)} · "
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
                    f"{values.get('duplicates', 0)} duplicadas · "
                    f"{values.get('irrelevant_skipped', 0)} descartadas por pertinencia · "
                    f"{values.get('errors', 0)} errores"
                )
            if discovery.get("filtered_examples"):
                with st.expander("Ofertas descartadas por falta de pertinencia"):
                    for item in discovery.get("filtered_examples", []):
                        st.write(f"- **{item.get('title')}** · {item.get('source')} · {item.get('reason')}")
            if discovery.get("error_details") or evaluation.get("errors"):
                with st.expander("Ver incidencias"):
                    for error in discovery.get("error_details", []):
                        st.write(f"- {error}")
                    for error in evaluation.get("errors", []):
                        st.write(f"- {error}")
        if result.get("paused_for_free_quota") or int(preparation.get("pending_remaining", 0)) > 0:
            st.warning(
                "Puede iniciar otra búsqueda para ampliar el descubrimiento, pero el presupuesto "
                "de embeddings está agotado. Las ofertas nuevas quedarán guardadas y pendientes "
                "de preparación hasta que se renueve el límite de 24 horas. No se borrarán "
                "las ofertas ni los fragmentos ya procesados."
            )
        action_cols = st.columns(2)
        if action_cols[0].button(
            "🔁 Nueva búsqueda con esta configuración",
            key="radar_repeat_search",
            type="primary",
            use_container_width=True,
        ):
            # La tarea anterior ya terminó; iniciar otra no puede solaparse con ella.
            st.session_state.radar_search_task = start_search_task(
                client,
                user_id=user["id"],
                roles=selected_roles,
                sources=selected_sources,
                limit_per_query=limit_per_query,
                role_context=role_context,
                custom_sources=custom_sources,
            )
            st.rerun()
        if action_cols[1].button(
            "Cerrar resumen de ejecución",
            key="radar_close_search_summary",
            use_container_width=True,
        ):
            st.session_state.radar_search_task = None
            st.rerun()

if st.session_state.get("radar_search_task") is not None:
    render_search_task()

st.divider()
st.header("📌 Bandeja de oportunidades")
st.caption(
    "La afinidad mide compatibilidad profesional; el atractivo ajusta esa afinidad según la preferencia de renta. "
    "Los rangos son provisionales y no equivalen a una probabilidad de contratación."
)
sector_filter = st.selectbox(
    "Filtro sectorial",
    options=["Todos los sectores", "Solo minería"],
    key="inbox_sector_filter",
)

def render_offer_card(item, evaluation_record=None):
    metadata = item.get("raw_metadata") or {}
    evaluation_meta = metadata.get("evaluation") or {}
    evaluation = (evaluation_record or {}).get("result_json") or {}
    score = item.get("affinity_score")
    attractiveness = evaluation_meta.get("attractiveness_score")
    if attractiveness is None and score is not None:
        attractiveness = score
    salary = evaluation_meta.get("salary_preference") or {}
    with st.container(border=True):
        st.markdown(f"**{item['title']}**")
        st.write(f"{item.get('company') or 'Empresa no informada'} · {item.get('sector_category') or 'POR_CLASIFICAR'}")
        metric_cols = st.columns(2)
        metric_cols[0].metric("Afinidad profesional", f"{score}/100" if score is not None else "Pendiente")
        metric_cols[1].metric("Atractivo ajustado", f"{attractiveness}/100" if attractiveness is not None else "Pendiente")
        salary_text = item.get("salary_text")
        if salary.get("label"):
            st.caption(f"Renta: {salary.get('label')}")
        elif salary_text:
            st.caption(f"Renta publicada: {salary_text} · comparación pendiente")
        else:
            st.caption("Renta no informada · sin penalización")
        search_origin = metadata.get("search_origin") or {}
        origin_families = search_origin.get("families") or []
        if origin_families:
            st.caption("Familia de búsqueda: " + ", ".join(
                family.get("name", family.get("id", "")) for family in origin_families if family
            ))
        publication_status = metadata.get("publication_date_status")
        if publication_status == "unknown":
            st.caption("Fecha de publicación no informada por el portal; antigüedad no verificable.")
        elif publication_status == "verified_recent":
            st.caption("Fecha de publicación verificada: dentro de los últimos 14 días.")
        if evaluation:
            with st.expander("Ver análisis, fortalezas, brechas y evidencia"):
                st.write(f"**Veredicto:** {evaluation.get('verdict', 'No informado')}")
                if evaluation.get("strengths"):
                    st.markdown("**Fortalezas**")
                    for value in evaluation["strengths"]:
                        st.write(f"- {value}")
                if evaluation.get("gaps"):
                    st.markdown("**Brechas**")
                    for value in evaluation["gaps"]:
                        st.write(f"- {value}")
                if evaluation.get("evidence"):
                    st.markdown("**Matriz de requisitos y evidencia**")
                    for evidence in evaluation["evidence"]:
                        st.write(
                            f"- **{evidence.get('requirement', 'Requisito')}** "
                            f"({evidence.get('importance', 'sin clasificar')} · {evidence.get('status', 'no evaluable')}): "
                            f"{evidence.get('cv_evidence', 'Sin evidencia registrada')}"
                        )
                if evaluation.get("hard_constraints"):
                    st.markdown("**Restricciones explícitas**")
                    for value in evaluation["hard_constraints"]:
                        st.write(f"- {value}")
                if evaluation.get("uncertainty_notes"):
                    st.markdown("**Incertidumbres**")
                    for value in evaluation["uncertainty_notes"]:
                        st.write(f"- {value}")
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

try:
    inbox = (
        client.table("job_offers")
        .select("id,title,company,location,source,source_url,description,salary_text,lifecycle_status,sector_category,affinity_score,priority_score,raw_metadata")
        .eq("user_id", user["id"]).eq("lifecycle_status", "NUEVA")
        .order("captured_at", desc=True).limit(1000).execute().data or []
    )
    inbox = [item for item in inbox if not (item.get("raw_metadata") or {}).get("evaluation_filter")]
    for item in inbox:
        item["sector_category"] = classify_sector(item)
    if sector_filter == "Solo minería":
        inbox = [item for item in inbox if item["sector_category"] in ("MINERIA", "PROVEEDOR_MINERO")]
    evaluation_by_offer = {}
    if active_cv:
        evaluation_rows = (
            client.table("evaluations")
            .select("job_offer_id,result_json,cv_version_id")
            .eq("user_id", user["id"]).eq("cv_version_id", active_cv[0]["id"])
            .limit(1000).execute().data or []
        )
        evaluation_by_offer = {row["job_offer_id"]: row for row in evaluation_rows}
    def attractiveness(item):
        value = ((item.get("raw_metadata") or {}).get("evaluation") or {}).get("attractiveness_score")
        return int(value if value is not None else item.get("affinity_score") or -1)
    inbox.sort(key=lambda item: (attractiveness(item), item.get("affinity_score") or -1, item.get("priority_score") or -1), reverse=True)
    recommended = [item for item in inbox if item.get("affinity_score") is not None and int(item["affinity_score"]) >= MINIMUM_AFFINITY_SCORE]
    review = [item for item in inbox if item.get("affinity_score") is not None and MANUAL_REVIEW_MINIMUM_SCORE <= int(item["affinity_score"]) < MINIMUM_AFFINITY_SCORE]
    lower = [item for item in inbox if item.get("affinity_score") is not None and int(item["affinity_score"]) < MANUAL_REVIEW_MINIMUM_SCORE]
    pending = [item for item in inbox if item.get("affinity_score") is None]
    st.subheader(f"Recomendadas · {len(recommended)}")
    st.caption(f"Afinidad igual o superior a {MINIMUM_AFFINITY_SCORE}%. Revisar evidencia antes de postular.")
    for item in recommended:
        render_offer_card(item, evaluation_by_offer.get(item["id"]))
    st.subheader(f"Revisión manual · {len(review)}")
    st.caption(f"Afinidad entre {MANUAL_REVIEW_MINIMUM_SCORE}% y {MINIMUM_AFFINITY_SCORE - 1}%. No se descartan: revise requisitos, brechas y condiciones.")
    for item in review:
        render_offer_card(item, evaluation_by_offer.get(item["id"]))
    with st.expander(f"Otras evaluadas bajo {MANUAL_REVIEW_MINIMUM_SCORE}% · {len(lower)}"):
        st.caption("Se conservan visibles para que un puntaje no calibrado no elimine oportunidades automáticamente.")
        for item in lower:
            render_offer_card(item, evaluation_by_offer.get(item["id"]))
    with st.expander(f"Pendientes de evaluación · {len(pending)}"):
        for item in pending:
            render_offer_card(item)
    if not inbox:
        st.info("Todavía no hay ofertas nuevas en esta bandeja. Ejecute una búsqueda o evalúe una oferta manualmente.")
except Exception as exc:
    st.error(f"No se pudo cargar la bandeja: {exc}")

st.divider()
st.subheader("Evaluar una oferta manualmente")
st.write("Función complementaria: puede pegar un aviso que encontró por su cuenta. No reemplaza la búsqueda automática.")
with st.form("evaluate_offer_form"):
    offer_title = st.text_input("Cargo", placeholder="Business Analyst Senior")
    offer_company = st.text_input("Empresa (opcional)")
    offer_location = st.text_input("Ubicación (opcional)")
    offer_salary = st.text_input("Renta informada (opcional)", placeholder="$1.200.000 líquidos, renta bruta o a convenir")
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
            "salary_text": offer_salary or None,
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
