-- Synthetic empresas fixture: 10 ATIVA empresas across multiple CNAEs in 7 UFs.
--
-- Coverage:
--   - 5 primary matches on cnae_primario='4744001' (Sao Paulo / RJ / MG)
--   - 3 secondary matches: cnaes_secundarios contains 4744001 (different primary)
--   - 2 outliers in unusual UFs (AM, AC) — test UF filter behavior
--
-- data_abertura ranges 1995-2024 to exercise ORDER BY data_abertura ASC.
--
-- Run inside a transaction — rolled back by the db_session fixture.

INSERT INTO empresas (cnpj, razao_social, nome_fantasia,
                      cnae_primario, cnaes_secundarios,
                      situacao_cadastral, data_abertura,
                      porte, capital_social, natureza_juridica,
                      uf, municipio, cep, endereco,
                      ultima_atualizacao_rf) VALUES
-- Primary-match block: cnae_primario = 4744001
('00000001000101','SYN PARAFUSOS 1 LTDA','Parafusos 1','4744001','{}','ATIVA','1995-03-10','EPP',100000,'2062','SP','Sao Paulo','01000000','Rua A, 1','2026-05-12'),
('00000002000101','SYN PARAFUSOS 2 LTDA','Parafusos 2','4744001','{}','ATIVA','2002-07-15','ME',50000,'2062','SP','Campinas','13000000','Rua B, 2','2026-05-12'),
('00000003000101','SYN PARAFUSOS 3 LTDA',NULL,'4744001','{}','ATIVA','2010-01-20','EPP',75000,'2062','RJ','Rio de Janeiro','20000000','Rua C, 3','2026-05-12'),
('00000004000101','SYN PARAFUSOS 4 SA',NULL,'4744001','{}','ATIVA','2018-06-30','DEMAIS',1000000,'2046','SP','Sao Paulo','01000001','Rua D, 4','2026-05-12'),
('00000005000101','SYN PARAFUSOS 5 LTDA','Parafusos 5','4744001','{}','ATIVA','2024-12-01','ME',10000,'2062','MG','Belo Horizonte','30000000','Rua E, 5','2026-05-12');

INSERT INTO empresas (cnpj, razao_social, nome_fantasia,
                      cnae_primario, cnaes_secundarios,
                      situacao_cadastral, data_abertura,
                      porte, capital_social, natureza_juridica,
                      uf, municipio, cep, endereco,
                      ultima_atualizacao_rf) VALUES
-- Secondary-match block: cnaes_secundarios contains 4744001
('00000061000101','SYN FERRAGENS A LTDA','Ferragens A','4673700','{4744001,4674500}','ATIVA','2008-04-12','EPP',200000,'2062','SP','Sao Paulo','01000010','Av X, 100','2026-05-12'),
('00000062000101','SYN ATACADO B LTDA',NULL,'4684201','{4744001}','ATIVA','2015-09-05','DEMAIS',500000,'2062','SP','Santos','11000000','Av Y, 200','2026-05-12'),
('00000063000101','SYN COMPLETO C SA','Completo C','4789099','{4744001,4673700}','ATIVA','1998-11-22','DEMAIS',3000000,'2046','PR','Curitiba','80000000','Av Z, 300','2026-05-12');

INSERT INTO empresas (cnpj, razao_social, nome_fantasia,
                      cnae_primario, cnaes_secundarios,
                      situacao_cadastral, data_abertura,
                      porte, capital_social, natureza_juridica,
                      uf, municipio, cep, endereco,
                      ultima_atualizacao_rf) VALUES
-- Outliers: AM and AC, primary 4744001 (test UF filter excludes them when uf='SP')
('00000091000101','SYN AMAZONAS LTDA',NULL,'4744001','{}','ATIVA','2020-02-14','ME',15000,'2062','AM','Manaus','69000000','Rua AM, 1','2026-05-12'),
('00000092000101','SYN ACRE SA',NULL,'4744001','{}','ATIVA','2019-08-19','ME',25000,'2062','AC','Rio Branco','69900000','Rua AC, 2','2026-05-12');
