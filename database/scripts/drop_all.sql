-- Drop all foreign key constraints first
ALTER TABLE public.orders DROP CONSTRAINT IF EXISTS client_orders_fk;
ALTER TABLE public.orders_items DROP CONSTRAINT IF EXISTS items_orders_items_fk;
ALTER TABLE public.orders DROP CONSTRAINT IF EXISTS users_orders_fk;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS public.orders_items;
DROP TABLE IF EXISTS public.orders;
DROP TABLE IF EXISTS public.audiT_logs;
DROP TABLE IF EXISTS public.users_user_agent;
DROP TABLE IF EXISTS public.users;
DROP TABLE IF EXISTS public.clients;
DROP TABLE IF EXISTS public.items;

-- Drop sequences
DROP SEQUENCE IF EXISTS public.clients_client_id_seq_1;
DROP SEQUENCE IF EXISTS public.items_item_id_seq;
DROP SEQUENCE IF EXISTS public.users_user_id_seq;
DROP SEQUENCE IF EXISTS public.audiT_logs_log_id_seq;
DROP SEQUENCE IF EXISTS public.orders_order_id_seq;