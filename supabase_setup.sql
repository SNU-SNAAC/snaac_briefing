-- Supabase Dashboard > SQL Editor > New query에서 전체를 실행하세요.

create extension if not exists pgcrypto;

create or replace function public.set_briefing_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.saved_articles_economy (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  article_url text not null,
  title text not null,
  source text not null default '',
  summary text not null default '',
  takeaway text not null default '',
  section text not null default '',
  category text not null default '',
  content_type text not null default '기사',
  image_url text not null default '',
  briefing_date text not null default '',
  note text not null default '',
  fallback_a text not null default '#3D5A6C',
  fallback_b text not null default '#8AA7B7',
  saved_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint saved_articles_economy_user_article_unique unique (user_id, article_url)
);

create index if not exists saved_articles_economy_user_saved_at_idx
  on public.saved_articles_economy (user_id, saved_at desc);

alter table public.saved_articles_economy enable row level security;

revoke all on table public.saved_articles_economy from anon;
grant select, insert, update, delete on table public.saved_articles_economy to authenticated;

drop policy if exists "read own saved articles" on public.saved_articles_economy;
create policy "read own saved articles"
  on public.saved_articles_economy
  for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "insert own saved articles" on public.saved_articles_economy;
create policy "insert own saved articles"
  on public.saved_articles_economy
  for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "update own saved articles" on public.saved_articles_economy;
create policy "update own saved articles"
  on public.saved_articles_economy
  for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "delete own saved articles" on public.saved_articles_economy;
create policy "delete own saved articles"
  on public.saved_articles_economy
  for delete
  to authenticated
  using ((select auth.uid()) = user_id);

drop trigger if exists saved_articles_economy_set_updated_at on public.saved_articles_economy;
create trigger saved_articles_economy_set_updated_at
before update on public.saved_articles_economy
for each row execute function public.set_briefing_updated_at();
