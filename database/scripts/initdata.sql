DELETE  FROM public.users_user_agent;
DELETE  FROM public.users;
DELETE  FROM public.clients;
DELETE  FROM public.items;


insert into public.users (username, password, status, role) values('sales1', 'password','A', 'U');
insert into public.users (username, password, status, role) values('sales2', 'password123','A', 'U');
insert into public.users (username, password, status, role) values('sales3', 'password','A', 'U');
insert into public.users (username, password, status, role) values('supervisor1', 'password333','A', 'S');
insert into public.users (username, password, status, role) values('admin1', 'password5555','A', 'A');  

insert into public.clients(name, docnum) values('Client1', '123456789');
insert into public.clients(name, docnum) values('Client2', '987654321');    
insert into public.clients(name, docnum) values('Client3', '456789123');
insert into public.clients(name, docnum) values('Client4', '789123456');
insert into public.clients(name, docnum) values('Client5', '321654987');
insert into public.clients(name, docnum) values('Client6', '654987321');
insert into public.clients(name, docnum) values('Client7', '159753456');
insert into public.clients(name, docnum) values('Client8', '753456159');
insert into public.clients(name, docnum) values('Client9', '456123789');
insert into public.clients(name, docnum) values('Client10', '321789654');

insert into public.items(item_name, value) values('Item1', 10.50);
insert into public.items(item_name, value) values('Item2', 20.00);  
insert into public.items(item_name, value) values('Item3', 15.75);
insert into public.items(item_name, value) values('Item4', 5.25);
insert into public.items(item_name, value) values('Item5', 12.00);
insert into public.items(item_name, value) values('Item6', 8.00);
insert into public.items(item_name, value) values('Item7', 18.50);
insert into public.items(item_name, value) values('Item8', 25.00);
insert into public.items(item_name, value) values('Item9', 30.00);
insert into public.items(item_name, value) values('Item10', 22.50);
insert into public.items(item_name, value) values('Item11', 9.99);
insert into public.items(item_name, value) values('Item12', 14.75);

insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'sales1'), 'A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'sales2'), 'A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'sales3'), 'A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'supervisor1'), 'A', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'sales1'), 'I', '10.0.0.4');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'sales2'), 'I', '10.0.0.6');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'sales3'), 'I', '10.0.0.14');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'supervisor1'), 'I', '19.0.0.1');
insert into public.users_user_agent(user_id, type, value) values( (select user_id from public.users where username = 'supervisor1'), 'I', '8.8.8.8');


