import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from edbank_mcp.db import AsyncSessionLocal
from edbank_mcp.schemas import BankAccountsResponse, AccountResult

logger = logging.getLogger(__name__)

_SQL = text("""
SELECT
    p.name  AS person_name,
    a.iban,
    b.name  AS bank_name,
    b.bic
FROM banking.person p
JOIN banking.account a ON a.person_id = p.id
JOIN banking.bank    b ON b.bic = a.bank_bic
WHERE lower(p.name) = lower(:person_name)
ORDER BY b.name, a.iban
""")


async def get_bank_accounts_by_person_name(
    person_name: str,
    session: AsyncSession | None = None,
) -> BankAccountsResponse:
    """
    Look up bank accounts by person name.
    An external session can be injected for testing; otherwise a new one is created.
    """
    logger.info("tool=get_bank_accounts_by_person_name person_name_length=%d", len(person_name))

    async def _query(s: AsyncSession) -> list:
        result = await s.execute(_SQL, {"person_name": person_name})
        return result.fetchall()

    if session is not None:
        rows = await _query(session)
    else:
        async with AsyncSessionLocal() as s:
            rows = await _query(s)

    accounts = [
        AccountResult(iban=row.iban, bank_name=row.bank_name, bic=row.bic)
        for row in rows
    ]
    return BankAccountsResponse(
        person_name=person_name,
        match_count=len(accounts),
        accounts=accounts,
    )
