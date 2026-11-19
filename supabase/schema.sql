-- Radar de Empleos 2.0 — esquema inicial de desarrollo.
-- Aplicar SOLO en el proyecto Supabase independiente de Radar 2.0.
-- No ejecutar en la base productiva.
-- Requiere Supabase Auth: cada fila pertenece a auth.uid().

create extension if not exists vector with schema extensions;

create table if not exists public.cv_versions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    cv_hash text not null,
    source_filename text,
    page_count integer,
    char_count integer,
    chunker_version text not null,
    embedding_model text not null,
    embedding_dimensions integer not null default 3072 check (embedding_dimensions = 3072),
    is_active boolean not null default false,
    created_at timestamptz not null default now(),
    unique (user_id, cv_hash),
    unique (id, user_id)
);
create unique index if not exists cv_versions_one_active_per_user
    on public.cv_versions(user_id) where is_active;

create table if not exists public.cv_chunks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    cv_version_id uuid not null,
    chunk_id text not null,
    chunk_index integer not null,
    section text not null default 'general',
    content text not null,
    char_count integer not null,
    embedding_model text not null,
    embedding extensions.vector(3072) not null,
    created_at timestamptz not null default now(),
    foreign key (cv_version_id, user_id)
        references public.cv_versions(id, user_id) on delete cascade,
    unique (cv_version_id, chunk_id),
    unique (cv_version_id, chunk_index)
);

create table if not exists public.job_offers (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    source text,
    source_url text,
    external_id text,
    title text not null,
    company text,
    location text,
    employment_type text,
    salary_text text,
    description text not null,
    job_hash text not null,
    published_at timestamptz,
    captured_at timestamptz not null default now(),
    raw_metadata jsonb not null default '{}'::jsonb,
    unique (user_id, job_hash),
    unique (id, user_id)
);

create table if not exists public.job_chunks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_offer_id uuid not null,
    chunk_index integer not null,
    content text not null,
    embedding_model text not null,
    embedding extensions.vector(3072) not null,
    created_at timestamptz not null default now(),
    foreign key (job_offer_id, user_id)
        references public.job_offers(id, user_id) on delete cascade,
    unique (job_offer_id, chunk_index)
);

create table if not exists public.evaluations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_offer_id uuid not null,
    cv_version_id uuid not null,
    score_match integer not null check (score_match between 0 and 100),
    verdict text not null check (verdict in ('POSTULAR', 'POSTULAR CON RESERVAS', 'DESCARTAR')),
    model text not null,
    prompt_version text not null,
    result_json jsonb not null,
    evidence_chunk_ids text[] not null default '{}',
    evaluated_at timestamptz not null default now(),
    foreign key (job_offer_id, user_id)
        references public.job_offers(id, user_id) on delete cascade,
    foreign key (cv_version_id, user_id)
        references public.cv_versions(id, user_id) on delete restrict
);

create table if not exists public.applications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_offer_id uuid not null,
    status text not null default 'por_evaluar'
        check (status in ('por_evaluar', 'interesado', 'postulado', 'entrevista', 'rechazado', 'contratado', 'descartado')),
    applied_at timestamptz,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (job_offer_id, user_id)
        references public.job_offers(id, user_id) on delete cascade,
    unique (user_id, job_offer_id)
);

create index if not exists cv_chunks_user_version_idx
    on public.cv_chunks(user_id, cv_version_id);
create index if not exists job_offers_user_captured_idx
    on public.job_offers(user_id, captured_at desc);
create index if not exists evaluations_user_date_idx
    on public.evaluations(user_id, evaluated_at desc);
create index if not exists applications_user_status_idx
    on public.applications(user_id, status);

-- HNSW index on half precision supports 3,072 dimensions (pgvector limit: 4,000).
-- Stored vectors remain full precision; the index is an expression index.
create index if not exists cv_chunks_embedding_hnsw
    on public.cv_chunks using hnsw
    ((embedding::extensions.halfvec(3072)) extensions.halfvec_cosine_ops);
create index if not exists job_chunks_embedding_hnsw
    on public.job_chunks using hnsw
    ((embedding::extensions.halfvec(3072)) extensions.halfvec_cosine_ops);

-- RLS: ninguna tabla queda expuesta a otros usuarios.
alter table public.cv_versions enable row level security;
alter table public.cv_chunks enable row level security;
alter table public.job_offers enable row level security;
alter table public.job_chunks enable row level security;
alter table public.evaluations enable row level security;
alter table public.applications enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array['cv_versions','cv_chunks','job_offers','job_chunks','evaluations','applications']
    loop
        execute format('drop policy if exists %I on public.%I', t || '_owner_all', t);
        execute format(
            'create policy %I on public.%I for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))',
            t || '_owner_all', t
        );
    end loop;
end $$;

-- En proyectos nuevos, Supabase ya no expone automáticamente las tablas
-- public a Data API. Los GRANT habilitan el rol autenticado a nivel SQL;
-- la exposición del esquema debe confirmarse en la configuración Data API.
grant usage on schema public, extensions to authenticated;
grant select, insert, update, delete on
    public.cv_versions, public.cv_chunks, public.job_offers,
    public.job_chunks, public.evaluations, public.applications
    to authenticated;

create or replace function public.match_cv_chunks(
    query_embedding extensions.vector(3072),
    match_count integer default 8,
    filter_cv_version_id uuid default null,
    filter_section text default null
)
returns table (
    chunk_id text,
    section text,
    content text,
    cv_version_id uuid,
    similarity double precision
)
language sql
stable
security invoker
set search_path = public, extensions
as $$
    select
        c.chunk_id,
        c.section,
        c.content,
        c.cv_version_id,
        1 - (
            c.embedding::extensions.halfvec(3072)
            <=> query_embedding::extensions.halfvec(3072)
        ) as similarity
    from public.cv_chunks c
    join public.cv_versions v
      on v.id = c.cv_version_id and v.user_id = c.user_id
    where c.user_id = (select auth.uid())
      and v.is_active
      and (filter_cv_version_id is null or c.cv_version_id = filter_cv_version_id)
      and (filter_section is null or c.section = filter_section)
    order by
        c.embedding::extensions.halfvec(3072)
        <=> query_embedding::extensions.halfvec(3072)
    limit least(greatest(match_count, 1), 50);
$$;

revoke all on function public.match_cv_chunks(extensions.vector, integer, uuid, text) from public;
grant execute on function public.match_cv_chunks(extensions.vector, integer, uuid, text) to authenticated;

comment on table public.cv_versions is 'Versiones del CV del usuario; el PDF original permanece local.';
comment on table public.cv_chunks is 'Fragmentos de texto del CV y embeddings Gemini 3072d.';
comment on table public.job_offers is 'Ofertas laborales capturadas por el usuario.';
comment on table public.evaluations is 'Evaluaciones reproducibles con modelo, prompt y evidencia.';
