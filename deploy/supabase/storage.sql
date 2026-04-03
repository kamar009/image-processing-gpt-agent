insert into storage.buckets (id, name, public)
values ('internal-inputs', 'internal-inputs', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('internal-outputs', 'internal-outputs', false)
on conflict (id) do nothing;

create policy if not exists "allow_read_own_output"
on storage.objects
for select
using (
  bucket_id = 'internal-outputs'
);

create policy if not exists "allow_insert_inputs"
on storage.objects
for insert
with check (
  bucket_id = 'internal-inputs'
);
