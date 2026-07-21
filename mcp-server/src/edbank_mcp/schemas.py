from pydantic import BaseModel


class AccountResult(BaseModel):
    iban: str
    bank_name: str
    bic: str


class BankAccountsResponse(BaseModel):
    person_name: str
    match_count: int
    accounts: list[AccountResult]
