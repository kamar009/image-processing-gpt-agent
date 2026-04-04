create extension if not exists pgcrypto;

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint unique not null,
  username text,
  full_name text,
  role text not null default 'user',
  created_at timestamptz not null default now()
);

create table if not exists public.allowed_users (
  telegram_id bigint primary key,
  comment text,
  created_at timestamptz not null default now()
);

create table if not exists public.generation_presets (
  id uuid primary key default gen_random_uuid(),
  key text unique not null,
  title text not null,
  image_type text not null,
  style text not null default 'neutral',
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.generation_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  preset_key text not null,
  status text not null default 'queued',
  input_file_id text not null,
  output_file_id text,
  error_message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create table if not exists public.usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

insert into public.generation_presets (key, title, image_type, style)
values
  ('promo_flyer', 'Реклама и флаеры', 'banner', 'neutral'),
  ('staff_portrait', 'Проф. фото сотрудников', 'product', 'neutral'),
  ('work_portfolio', 'Проф. фото работ', 'portfolio_interior', 'neutral'),
  ('hair_style_ai', 'ИИ подбор прически', 'category', 'creative'),
  ('catalog_showcase', 'Витрина каталога', 'category', 'neutral'),
  ('hero_slide', 'Слайд главной (герой)', 'banner', 'neutral'),
  ('interior_wide', 'Интерьер широкий кадр', 'portfolio_interior', 'neutral'),
  ('product_white_bg', 'Товар на белом фоне', 'product', 'premium')
on conflict (key) do nothing;
