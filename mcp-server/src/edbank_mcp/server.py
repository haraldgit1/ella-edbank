import logging
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from edbank_mcp.config import settings
from edbank_mcp.tools.bank_accounts import get_bank_accounts_by_person_name as _get_accounts

logging.basicConfig(
    level=settings.edbank_log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# stateless_http=True: no session state between requests — correct for this PoC.
# host/port are used by mcp.run(); the health route is served on the same port.
mcp = FastMCP(
    "edbank-mcp",
    host="0.0.0.0",
    port=8001,
    stateless_http=True,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool(
    description=(
        "Returns all bank accounts for one person from the local demo database. "
        "Use this tool when the user asks for IBANs, bank accounts, bank names or BICs "
        "belonging to a named person. This is a read-only lookup."
    )
)
async def get_bank_accounts_by_person_name(
    person_name: str = Field(
        description="Full name of the person, for example Hannes Meier",
        min_length=2,
        max_length=200,
    ),
) -> dict:
    result = await _get_accounts(person_name)
    return result.model_dump()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
