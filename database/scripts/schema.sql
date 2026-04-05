
CREATE SEQUENCE public.clients_client_id_seq;

CREATE TABLE public.clients (
                client_id NUMERIC NOT NULL DEFAULT nextval('public.clients_client_id_seq'),
                name VARCHAR(256) NOT NULL,
                docnum VARCHAR NOT NULL,
                CONSTRAINT clients_pk PRIMARY KEY (client_id)
);


ALTER SEQUENCE public.clients_client_id_seq OWNED BY public.clients.client_id;

CREATE SEQUENCE public.items_item_id_seq;

CREATE TABLE public.items (
                item_id NUMERIC NOT NULL DEFAULT nextval('public.items_item_id_seq'),
                item_name VARCHAR(256) NOT NULL,
                value NUMERIC NOT NULL,
                CONSTRAINT items_pk PRIMARY KEY (item_id)
);


ALTER SEQUENCE public.items_item_id_seq OWNED BY public.items.item_id;

CREATE SEQUENCE public.users_user_id_seq;

CREATE TABLE public.users (
                user_id NUMERIC NOT NULL DEFAULT nextval('public.users_user_id_seq'),
                username VARCHAR(32) NOT NULL,
                password VARCHAR(256) NOT NULL,
                status CHAR(1) NOT NULL,
                role VARCHAR NOT NULL,
                CONSTRAINT user_pk PRIMARY KEY (user_id)
);
COMMENT ON COLUMN public.users.role IS 'admin, supervisor or user';


ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;

CREATE TABLE public.users_user_agent (
                user_id NUMERIC NOT NULL,
                type CHAR(1) NOT NULL,
                value VARCHAR(256) NOT NULL
);


CREATE SEQUENCE public.audit_logs_log_id_seq;

CREATE TABLE public.audit_logs (
                log_id NUMERIC NOT NULL DEFAULT nextval('public.audit_logs_log_id_seq'),
                user_id NUMERIC,
                method VARCHAR NOT NULL,
                endpoint VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                user_agent VARCHAR(512) NOT NULL,
                ip VARCHAR(64) NOT NULL,
                pod VARCHAR(256),
                CONSTRAINT audit_logs_pk PRIMARY KEY (log_id)
);


ALTER SEQUENCE public.audit_logs_log_id_seq OWNED BY public.audit_logs.log_id;

CREATE SEQUENCE public.orders_order_id_seq;

CREATE TABLE public.orders (
                order_id NUMERIC NOT NULL DEFAULT nextval('public.orders_order_id_seq'),
                user_id NUMERIC NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                client_id NUMERIC NOT NULL,
                CONSTRAINT orders_pk PRIMARY KEY (order_id)
);


ALTER SEQUENCE public.orders_order_id_seq OWNED BY public.orders.order_id;

CREATE TABLE public.orders_items (
                order_id NUMERIC NOT NULL,
                item_id NUMERIC NOT NULL,
                quantity INTEGER NOT NULL,
                unit_value NUMERIC NOT NULL,
                CONSTRAINT orders_items_pk PRIMARY KEY (order_id, item_id)
);


ALTER TABLE public.orders ADD CONSTRAINT client_orders_fk
FOREIGN KEY (client_id)
REFERENCES public.clients (client_id)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

ALTER TABLE public.orders_items ADD CONSTRAINT items_orders_items_fk
FOREIGN KEY (item_id)
REFERENCES public.items (item_id)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

ALTER TABLE public.orders ADD CONSTRAINT users_orders_fk
FOREIGN KEY (user_id)
REFERENCES public.users (user_id)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

ALTER TABLE public.audit_logs ADD CONSTRAINT users_audit_logs_fk
FOREIGN KEY (user_id)
REFERENCES public.users (user_id)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

ALTER TABLE public.users_user_agent ADD CONSTRAINT users_users_user_agent_fk
FOREIGN KEY (user_id)
REFERENCES public.users (user_id)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

ALTER TABLE public.orders_items ADD CONSTRAINT orders_orders_items_fk
FOREIGN KEY (order_id)
REFERENCES public.orders (order_id)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;