from sqlalchemy.ext.asyncio import AsyncSession


async def generate_daily_report(
    session: AsyncSession, user_id: int, date: str
) -> dict[str, object]:
    raise NotImplementedError("Faz 1: günlük rapor üretimi")


async def generate_monthly_report(
    session: AsyncSession, user_id: int, year_month: str
) -> dict[str, object]:
    raise NotImplementedError("Faz 1: aylık rapor üretimi")
