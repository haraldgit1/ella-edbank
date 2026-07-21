CREATE SCHEMA IF NOT EXISTS banking;

CREATE TABLE banking.person (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE INDEX ix_person_name_lower
    ON banking.person (lower(name));

CREATE TABLE banking.bank (
    bic         VARCHAR(11) PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE TABLE banking.account (
    id          BIGSERIAL PRIMARY KEY,
    person_id   BIGINT NOT NULL
                REFERENCES banking.person(id),
    bank_bic    VARCHAR(11) NOT NULL
                REFERENCES banking.bank(bic),
    iban        VARCHAR(34) NOT NULL UNIQUE
);
