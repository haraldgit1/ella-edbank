INSERT INTO banking.person (id, name)
VALUES (1, 'Hannes Meier')
ON CONFLICT (id) DO NOTHING;

-- Reset sequence to avoid collisions
SELECT setval('banking.person_id_seq', (SELECT MAX(id) FROM banking.person));

INSERT INTO banking.bank (bic, name)
VALUES
    ('BAWAATWW', 'Musterbank Wien'),
    ('RLNWATWW', 'Regionalbank Süd')
ON CONFLICT (bic) DO NOTHING;

INSERT INTO banking.account (person_id, bank_bic, iban)
VALUES
    (1, 'BAWAATWW', 'AT611904300234573201'),
    (1, 'RLNWATWW', 'AT483200000012345864')
ON CONFLICT (iban) DO NOTHING;
