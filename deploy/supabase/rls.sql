alter table public.users enable row level security;
alter table public.allowed_users enable row level security;
alter table public.generation_presets enable row level security;
alter table public.generation_jobs enable row level security;
alter table public.usage_events enable row level security;

create or replace function public.current_telegram_id()
returns bigint
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.telegram_id', true), '')::bigint
$$;

create policy if not exists users_select_own
on public.users for select
using (telegram_id = public.current_telegram_id());

create policy if not exists users_update_own
on public.users for update
using (telegram_id = public.current_telegram_id());

create policy if not exists jobs_select_own
on public.generation_jobs for select
using (
  user_id in (
    select id from public.users where telegram_id = public.current_telegram_id()
  )
);

create policy if not exists jobs_insert_own
on public.generation_jobs for insert
with check (
  user_id in (
    select id from public.users where telegram_id = public.current_telegram_id()
  )
);

create policy if not exists presets_select_enabled
on public.generation_presets for select
using (enabled = true);

create policy if not exists usage_select_own
on public.usage_events for select
using (
  user_id in (
    select id from public.users where telegram_id = public.current_telegram_id()
  )
);
