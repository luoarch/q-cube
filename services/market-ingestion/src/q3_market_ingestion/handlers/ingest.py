"""Ingestion endpoints — orchestrates data from all three layers.

Layer hierarchy (controlled by .env feature flags):
  1. CVM raw  → source of truth, audit trail (ENABLE_CVM=true)
  2. Dados de Mercado → primary for canonical fundamentals (ENABLE_DADOS_MERCADO=true)
  3. brapi.dev → secondary for market data / enrichment (ENABLE_BRAPI=true)

Default: CVM only. Other vendors activated via .env when tokens are configured.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from q3_market_ingestion.clients import brapi, cvm
from q3_market_ingestion.config import ENABLE_BRAPI, ENABLE_CVM
from q3_market_ingestion.db.session import SessionLocal
from q3_shared_models.entities import Asset, FinancialStatement

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingestion"])


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# CVM-based ingestion (source of truth)
# ---------------------------------------------------------------------------

@router.post("/cvm/fundamentals/{year}")
async def ingest_cvm_fundamentals(
    year: int,
    tenant_id: uuid.UUID = Query(...),
) -> dict[str, Any]:
    """Download DFP from CVM, parse financial statements, and upsert into DB.

    This is the CVM-only pipeline:
    1. Download DFP (annual) ZIP for the year
    2. Download FCA to get CD_CVM → ticker mapping
    3. Parse DRE/BPA/BPP and extract key accounts
    4. Upsert companies into `assets` and fundamentals into `financial_statements`

    Companies without tickers in CVM's FCA are skipped (e.g. deregistered companies).
    """
    if not ENABLE_CVM:
        raise HTTPException(status_code=400, detail="CVM ingestion is disabled (ENABLE_CVM=false)")

    # 1. Download DFP
    logger.info("downloading DFP year=%d", year)
    dfp_csvs = await cvm.download_dfp(year)

    # 2. Download FCA for ticker mapping
    logger.info("downloading FCA year=%d for ticker mapping", year)
    try:
        fca_csvs = await cvm.download_fca(year)
        ticker_mapping = cvm.extract_ticker_mapping(fca_csvs)
        logger.info("ticker mapping: %d companies with tickers", len(ticker_mapping))
    except Exception:
        logger.warning("FCA download failed for year=%d, trying year-1", year, exc_info=True)
        try:
            fca_csvs = await cvm.download_fca(year - 1)
            ticker_mapping = cvm.extract_ticker_mapping(fca_csvs)
            logger.info("ticker mapping (year-1): %d companies", len(ticker_mapping))
        except Exception:
            logger.warning("FCA fallback also failed, proceeding without tickers", exc_info=True)
            ticker_mapping = {}

    # 3. Parse DRE/BPA/BPP (consolidated only, ÚLTIMO period)
    dre_rows = cvm.parse_statements(dfp_csvs, statement_type="DRE", consolidated=True)
    bpa_rows = cvm.parse_statements(dfp_csvs, statement_type="BPA", consolidated=True)
    bpp_rows = cvm.parse_statements(dfp_csvs, statement_type="BPP", consolidated=True)

    logger.info("parsed DRE=%d BPA=%d BPP=%d rows", len(dre_rows), len(bpa_rows), len(bpp_rows))

    # 4. Build fundamentals
    fundamentals = cvm.build_fundamentals(
        dre_rows, bpa_rows, bpp_rows,
        ticker_mapping=ticker_mapping,
        period_order="ÚLTIMO",
    )
    logger.info("built %d company fundamentals", len(fundamentals))

    # 5. Upsert into DB
    upserted_assets = 0
    upserted_statements = 0
    skipped_no_ticker = 0

    with SessionLocal() as session:
        for fund in fundamentals:
            if not fund.tickers:
                skipped_no_ticker += 1
                continue

            for ticker in fund.tickers:
                # Upsert asset
                asset_id = uuid.uuid4()
                asset_stmt = pg_insert(Asset).values(
                    id=asset_id,
                    tenant_id=tenant_id,
                    ticker=ticker,
                    name=fund.company_name,
                    is_active=True,
                ).on_conflict_do_update(
                    constraint="uq_assets_tenant_ticker",
                    set_={
                        "name": fund.company_name,
                        "is_active": True,
                        "updated_at": datetime.now(UTC),
                    },
                )
                session.execute(asset_stmt)
                upserted_assets += 1

                # Get the actual asset id (might be existing)
                actual_asset = session.execute(
                    select(Asset).where(
                        Asset.tenant_id == tenant_id,
                        Asset.ticker == ticker,
                    )
                ).scalar_one()

                # Parse reference_date to datetime
                try:
                    period_date = datetime.strptime(fund.reference_date, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    logger.warning("invalid reference_date %s for %s", fund.reference_date, ticker)
                    continue

                # Upsert financial statement
                now = datetime.now(UTC)
                fs_stmt = pg_insert(FinancialStatement).values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    asset_id=actual_asset.id,
                    period_date=period_date,
                    ebit=fund.ebit,
                    net_working_capital=fund.net_working_capital,
                    fixed_assets=fund.fixed_assets,
                    roic=fund.roic,
                    gross_margin=fund.gross_margin,
                    net_margin=fund.ebit_margin,
                ).on_conflict_do_update(
                    constraint="uq_financial_statements_asset_period",
                    set_={
                        "ebit": fund.ebit,
                        "net_working_capital": fund.net_working_capital,
                        "fixed_assets": fund.fixed_assets,
                        "roic": fund.roic,
                        "gross_margin": fund.gross_margin,
                        "net_margin": fund.ebit_margin,
                        "updated_at": now,
                    },
                )
                session.execute(fs_stmt)
                upserted_statements += 1

        session.commit()

    # Also save raw CSVs for audit trail
    output_dir = Path("data/cvm")
    cvm.save_raw(dfp_csvs, output_dir / f"dfp_{year}")

    return {
        "year": year,
        "source": "cvm",
        "fundamentals_built": len(fundamentals),
        "upserted_assets": upserted_assets,
        "upserted_statements": upserted_statements,
        "skipped_no_ticker": skipped_no_ticker,
        "ticker_mapping_size": len(ticker_mapping),
    }


@router.post("/cvm/raw/{year}")
async def ingest_cvm_raw(year: int) -> dict[str, Any]:
    """Download DFP/ITR from CVM and save raw CSVs for audit trail."""
    if not ENABLE_CVM:
        raise HTTPException(status_code=400, detail="CVM ingestion is disabled (ENABLE_CVM=false)")

    output_dir = Path("data/cvm")

    dfp_csvs = await cvm.download_dfp(year)
    dfp_saved = cvm.save_raw(dfp_csvs, output_dir / f"dfp_{year}")

    itr_csvs = await cvm.download_itr(year)
    itr_saved = cvm.save_raw(itr_csvs, output_dir / f"itr_{year}")

    return {
        "year": year,
        "dfp_files": len(dfp_saved),
        "itr_files": len(itr_saved),
        "output_dir": str(output_dir),
    }


# ---------------------------------------------------------------------------
# brapi-based ingestion (secondary, requires ENABLE_BRAPI=true)
# ---------------------------------------------------------------------------

@router.post("/assets")
async def ingest_assets(
    tenant_id: uuid.UUID = Query(...),
) -> dict[str, Any]:
    """List B3 stocks from brapi and upsert into assets table.

    Uses brapi quote/list (available on all plans including free).
    Requires ENABLE_BRAPI=true.
    """
    if not ENABLE_BRAPI:
        raise HTTPException(
            status_code=400,
            detail="brapi ingestion is disabled (ENABLE_BRAPI=false). Use CVM endpoints instead.",
        )

    stocks = await brapi.list_stocks()
    if not stocks:
        raise HTTPException(status_code=502, detail="No stocks returned from brapi")

    upserted = 0
    with SessionLocal() as session:
        for stock in stocks:
            ticker = stock.get("stock", "")
            name = stock.get("name") or stock.get("close", ticker)
            sector = stock.get("sector")
            sub_sector = stock.get("type")

            if not ticker:
                continue

            stmt = pg_insert(Asset).values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                ticker=ticker,
                name=str(name),
                sector=sector,
                sub_sector=sub_sector,
                is_active=True,
            ).on_conflict_do_update(
                constraint="uq_assets_tenant_ticker",
                set_={
                    "name": str(name),
                    "sector": sector,
                    "sub_sector": sub_sector,
                    "is_active": True,
                    "updated_at": datetime.now(UTC),
                },
            )
            session.execute(stmt)
            upserted += 1

        session.commit()

    return {"upserted": upserted, "source": "brapi"}


@router.post("/fundamentals")
async def ingest_fundamentals(
    tenant_id: uuid.UUID = Query(...),
    year: int | None = Query(None, description="Year for CVM data (default: current year)"),
) -> dict[str, Any]:
    """Fetch fundamentals for all active assets.

    Routes to the active data source based on feature flags:
    - ENABLE_CVM=true → uses CVM DFP data
    - ENABLE_BRAPI=true → uses brapi modules/quote
    - Both disabled → returns error
    """
    if ENABLE_CVM:
        target_year = year or datetime.now(UTC).year
        return await ingest_cvm_fundamentals(target_year, tenant_id)

    if not ENABLE_BRAPI:
        raise HTTPException(
            status_code=400,
            detail="No data source enabled. Set ENABLE_CVM=true or ENABLE_BRAPI=true in .env",
        )

    # brapi fallback
    return await _ingest_fundamentals_brapi(tenant_id)


async def _ingest_fundamentals_brapi(tenant_id: uuid.UUID) -> dict[str, Any]:
    """Fetch fundamentals via brapi (secondary source)."""
    import asyncio

    with SessionLocal() as session:
        assets = session.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.is_active.is_(True),
            )
        ).scalars().all()

    processed = 0
    skipped = 0
    errors: list[str] = []

    for asset in assets:
        try:
            ingested = await _ingest_asset_fundamentals(asset, tenant_id)
            if ingested:
                processed += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{asset.ticker}: {exc}")
            logger.warning("failed to ingest %s: %s", asset.ticker, exc)

        await asyncio.sleep(0.5)

    return {"processed": processed, "skipped": skipped, "errors": errors, "source": "brapi"}


@router.post("/fundamentals/{ticker}")
async def ingest_single_fundamental(
    ticker: str,
    tenant_id: uuid.UUID = Query(...),
) -> dict[str, Any]:
    """Ingest fundamentals for a single ticker. Requires ENABLE_BRAPI=true."""
    if not ENABLE_BRAPI:
        raise HTTPException(
            status_code=400,
            detail="Single-ticker ingestion requires ENABLE_BRAPI=true. Use /ingest/cvm/fundamentals/{year} for CVM bulk.",
        )

    with SessionLocal() as session:
        asset = session.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.ticker == ticker,
            )
        ).scalar_one_or_none()

    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset {ticker} not found")

    ingested = await _ingest_asset_fundamentals(asset, tenant_id)
    return {"ticker": ticker, "status": "ok" if ingested else "skipped_no_data"}


@router.post("/market-data")
async def ingest_market_data(
    tenant_id: uuid.UUID = Query(...),
) -> dict[str, Any]:
    """Enrich financial_statements with quote data from brapi.

    Requires ENABLE_BRAPI=true.
    Available on all plans (free included).
    """
    if not ENABLE_BRAPI:
        raise HTTPException(
            status_code=400,
            detail="Market data enrichment requires ENABLE_BRAPI=true.",
        )

    import asyncio

    with SessionLocal() as session:
        assets = session.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.is_active.is_(True),
            )
        ).scalars().all()

    enriched = 0
    for asset in assets:
        try:
            await _enrich_market_data(asset, tenant_id)
            enriched += 1
        except Exception:  # noqa: BLE001
            logger.warning("failed to enrich %s", asset.ticker, exc_info=True)

        await asyncio.sleep(0.5)

    return {"enriched": enriched}


# ---------------------------------------------------------------------------
# brapi helper functions (used when ENABLE_BRAPI=true)
# ---------------------------------------------------------------------------

async def _ingest_asset_fundamentals(
    asset: Asset,
    tenant_id: uuid.UUID,
) -> bool:
    """Fetch fundamentals from brapi and upsert into financial_statements."""
    data = await brapi.get_fundamentals(
        asset.ticker,
        modules="defaultKeyStatistics,financialData,summaryProfile,balanceSheetHistory,incomeStatementHistory",
    )

    if data is not None:
        return await _upsert_from_modules(asset, tenant_id, data)

    quote = await brapi.get_quote(asset.ticker)
    if quote is not None:
        return await _upsert_from_quote(asset, tenant_id, quote)

    return False


async def _upsert_from_modules(
    asset: Asset,
    tenant_id: uuid.UUID,
    data: dict[str, Any],
) -> bool:
    """Upsert from brapi modules response (Startup+ plan)."""
    key_stats = data.get("defaultKeyStatistics") or {}
    fin_data = data.get("financialData") or {}
    profile = data.get("summaryProfile") or {}
    balance_sheets = data.get("balanceSheetHistory") or []
    if isinstance(balance_sheets, dict):
        balance_sheets = balance_sheets.get("balanceSheetStatements", [])
    income_stmts = data.get("incomeStatementHistory") or []
    if isinstance(income_stmts, dict):
        income_stmts = income_stmts.get("incomeStatementHistory", [])

    enterprise_value = _decimal(key_stats.get("enterpriseValue"))
    ebitda = _decimal(fin_data.get("ebitda"))
    total_debt = _decimal(fin_data.get("totalDebt"))
    net_margin = _decimal(fin_data.get("profitMargins"))
    gross_margin = _decimal(fin_data.get("grossMargins"))
    market_cap_val = _decimal(data.get("marketCap"))
    avg_volume = _decimal(data.get("averageDailyVolume3Month") or data.get("regularMarketVolume"))

    ebit: Decimal | None = None
    if income_stmts:
        ebit = _decimal(income_stmts[0].get("ebit"))

    nwc: Decimal | None = None
    fixed_assets: Decimal | None = None
    if balance_sheets:
        bs = balance_sheets[0]
        current_assets = _decimal(bs.get("totalCurrentAssets"))
        current_liabilities = _decimal(
            bs.get("totalCurrentLiabilities") or bs.get("currentLiabilities")
        )
        if current_assets is not None and current_liabilities is not None:
            nwc = current_assets - current_liabilities
        fixed_assets = _decimal(bs.get("propertyPlantEquipment"))

    roic: Decimal | None = None
    roa = fin_data.get("returnOnAssets")
    roe = fin_data.get("returnOnEquity")
    if roa is not None and roe is not None:
        roic = _decimal((roa + roe) / 2)

    now = datetime.now(UTC)
    period_date = now.replace(day=1)

    with SessionLocal() as session:
        if profile.get("sector"):
            session.execute(
                pg_insert(Asset).values(
                    id=asset.id,
                    tenant_id=tenant_id,
                    ticker=asset.ticker,
                    name=asset.name,
                    sector=profile.get("sector"),
                    sub_sector=profile.get("industry"),
                ).on_conflict_do_update(
                    constraint="uq_assets_tenant_ticker",
                    set_={
                        "sector": profile["sector"],
                        "sub_sector": profile.get("industry"),
                        "updated_at": now,
                    },
                )
            )

        stmt = pg_insert(FinancialStatement).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            asset_id=asset.id,
            period_date=period_date,
            ebit=ebit,
            enterprise_value=enterprise_value,
            net_working_capital=nwc,
            fixed_assets=fixed_assets,
            roic=roic,
            net_debt=total_debt,
            ebitda=ebitda,
            net_margin=net_margin,
            gross_margin=gross_margin,
            avg_daily_volume=avg_volume,
            market_cap=market_cap_val,
        ).on_conflict_do_update(
            constraint="uq_financial_statements_asset_period",
            set_={
                "ebit": ebit,
                "enterprise_value": enterprise_value,
                "net_working_capital": nwc,
                "fixed_assets": fixed_assets,
                "roic": roic,
                "net_debt": total_debt,
                "ebitda": ebitda,
                "net_margin": net_margin,
                "gross_margin": gross_margin,
                "avg_daily_volume": avg_volume,
                "market_cap": market_cap_val,
                "updated_at": now,
            },
        )
        session.execute(stmt)
        session.commit()

    return True


async def _upsert_from_quote(
    asset: Asset,
    tenant_id: uuid.UUID,
    quote: dict[str, Any],
) -> bool:
    """Upsert from brapi quote response (free plan fallback)."""
    market_cap_val = _decimal(quote.get("marketCap"))
    avg_volume = _decimal(quote.get("averageDailyVolume3Month") or quote.get("regularMarketVolume"))

    if market_cap_val is None and avg_volume is None:
        return False

    now = datetime.now(UTC)
    period_date = now.replace(day=1)

    with SessionLocal() as session:
        stmt = pg_insert(FinancialStatement).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            asset_id=asset.id,
            period_date=period_date,
            market_cap=market_cap_val,
            avg_daily_volume=avg_volume,
        ).on_conflict_do_update(
            constraint="uq_financial_statements_asset_period",
            set_={
                "market_cap": market_cap_val,
                "avg_daily_volume": avg_volume,
                "updated_at": now,
            },
        )
        session.execute(stmt)
        session.commit()

    return True


async def _enrich_market_data(
    asset: Asset,
    tenant_id: uuid.UUID,
) -> None:
    """Enrich with quote data from brapi: volume, market cap, momentum."""
    quote = await brapi.get_quote(asset.ticker)
    if quote is None:
        return

    market_cap_val = _decimal(quote.get("marketCap"))
    avg_volume = _decimal(quote.get("averageDailyVolume3Month") or quote.get("regularMarketVolume"))

    momentum: Decimal | None = None
    try:
        history = await brapi.get_historical(asset.ticker)
        if len(history) >= 2:
            first_close = history[0].get("close", 0)
            last_close = history[-1].get("close", 0)
            if first_close and first_close > 0:
                momentum = _decimal((last_close - first_close) / first_close)
    except Exception:  # noqa: BLE001
        logger.debug("failed to compute momentum for %s", asset.ticker)

    now = datetime.now(UTC)
    period_date = now.replace(day=1)

    update_fields: dict[str, Any] = {"updated_at": now}
    if market_cap_val is not None:
        update_fields["market_cap"] = market_cap_val
    if avg_volume is not None:
        update_fields["avg_daily_volume"] = avg_volume
    if momentum is not None:
        update_fields["momentum_12m"] = momentum

    with SessionLocal() as session:
        stmt = pg_insert(FinancialStatement).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            asset_id=asset.id,
            period_date=period_date,
            market_cap=market_cap_val,
            avg_daily_volume=avg_volume,
            momentum_12m=momentum,
        ).on_conflict_do_update(
            constraint="uq_financial_statements_asset_period",
            set_=update_fields,
        )
        session.execute(stmt)
        session.commit()
