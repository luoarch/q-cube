import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from q3_shared_models.base import Base


# ---------------------------------------------------------------------------
# Fundamentals enums (global, not tenant-scoped)
# ---------------------------------------------------------------------------


class StatementType(str, enum.Enum):
    DRE = "DRE"
    BPA = "BPA"
    BPP = "BPP"
    DFC_MD = "DFC_MD"
    DFC_MI = "DFC_MI"
    DMPL = "DMPL"
    DVA = "DVA"


class PeriodType(str, enum.Enum):
    annual = "annual"
    quarterly = "quarterly"


class FilingType(str, enum.Enum):
    DFP = "DFP"
    ITR = "ITR"
    FCA = "FCA"


class FilingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    superseded = "superseded"


class BatchStatus(str, enum.Enum):
    pending = "pending"
    downloading = "downloading"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ScopeType(str, enum.Enum):
    con = "con"
    ind = "ind"


class SourceProvider(str, enum.Enum):
    cvm = "cvm"
    brapi = "brapi"
    dados_de_mercado = "dados_de_mercado"
    manual = "manual"


# ---------------------------------------------------------------------------
# Existing enums (tenant-scoped)
# ---------------------------------------------------------------------------


class MembershipRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class StrategyType(str, enum.Enum):
    magic_formula_original = "magic_formula_original"
    magic_formula_brazil = "magic_formula_brazil"
    magic_formula_hybrid = "magic_formula_hybrid"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobKind(str, enum.Enum):
    strategy_run = "strategy_run"
    backtest_run = "backtest_run"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MembershipRole] = mapped_column(Enum(MembershipRole, name="membership_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("tenant_id", "ticker", name="uq_assets_tenant_ticker"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str | None] = mapped_column(String)
    sub_sector: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinancialStatement(Base):
    __tablename__ = "financial_statements"
    __table_args__ = (UniqueConstraint("asset_id", "period_date", name="uq_financial_statements_asset_period"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ebit: Mapped[float | None] = mapped_column(Numeric)
    enterprise_value: Mapped[float | None] = mapped_column(Numeric)
    net_working_capital: Mapped[float | None] = mapped_column(Numeric)
    fixed_assets: Mapped[float | None] = mapped_column(Numeric)
    roic: Mapped[float | None] = mapped_column(Numeric)
    net_debt: Mapped[float | None] = mapped_column(Numeric)
    ebitda: Mapped[float | None] = mapped_column(Numeric)
    net_margin: Mapped[float | None] = mapped_column(Numeric)
    gross_margin: Mapped[float | None] = mapped_column(Numeric)
    net_margin_std: Mapped[float | None] = mapped_column(Numeric)
    avg_daily_volume: Mapped[float | None] = mapped_column(Numeric)
    market_cap: Mapped[float | None] = mapped_column(Numeric)
    momentum_12m: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy: Mapped[StrategyType] = mapped_column(Enum(StrategyType, name="strategy_type"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status"), nullable=False)
    as_of_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status", create_type=False), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[JobKind] = mapped_column(Enum(JobKind, name="job_kind"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status", create_type=False), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Fundamentals tables (global, NOT tenant-scoped)
# ---------------------------------------------------------------------------


class RawSourceBatch(Base):
    __tablename__ = "raw_source_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source: Mapped[SourceProvider] = mapped_column(Enum(SourceProvider, name="source_provider"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[FilingType] = mapped_column(Enum(FilingType, name="filing_type"), nullable=False)
    status: Mapped[BatchStatus] = mapped_column(Enum(BatchStatus, name="batch_status"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RawSourceFile(Base):
    __tablename__ = "raw_source_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_source_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Issuer(Base):
    __tablename__ = "issuers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    cvm_code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String)
    cnpj: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    sector: Mapped[str | None] = mapped_column(String)
    subsector: Mapped[str | None] = mapped_column(String)
    segment: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Security(Base):
    __tablename__ = "securities"
    __table_args__ = (
        UniqueConstraint("issuer_id", "ticker", "valid_from", name="uq_securities_issuer_ticker_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    security_class: Mapped[str | None] = mapped_column(String)
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[SourceProvider] = mapped_column(Enum(SourceProvider, name="source_provider", create_type=False), nullable=False)
    filing_type: Mapped[FilingType] = mapped_column(Enum(FilingType, name="filing_type", create_type=False), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_restatement: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    supersedes_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="SET NULL"),
    )
    status: Mapped[FilingStatus] = mapped_column(Enum(FilingStatus, name="filing_status"), nullable=False)
    raw_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_source_files.id", ondelete="SET NULL"),
    )
    validation_result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StatementLine(Base):
    __tablename__ = "statement_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
    )
    statement_type: Mapped[StatementType] = mapped_column(Enum(StatementType, name="statement_type"), nullable=False)
    scope: Mapped[ScopeType] = mapped_column(Enum(ScopeType, name="scope_type"), nullable=False)
    period_type: Mapped[PeriodType] = mapped_column(Enum(PeriodType, name="period_type"), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    canonical_key: Mapped[str | None] = mapped_column(String)
    as_reported_label: Mapped[str] = mapped_column(String, nullable=False)
    as_reported_code: Mapped[str] = mapped_column(String, nullable=False)
    normalized_value: Mapped[float | None] = mapped_column(Numeric)
    currency: Mapped[str] = mapped_column(String, nullable=False, server_default="BRL")
    unit_scale: Mapped[str] = mapped_column(String, nullable=False, server_default="UNIDADE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ComputedMetric(Base):
    __tablename__ = "computed_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="SET NULL"),
    )
    metric_code: Mapped[str] = mapped_column(String, nullable=False)
    period_type: Mapped[PeriodType] = mapped_column(Enum(PeriodType, name="period_type", create_type=False), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric)
    formula_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    inputs_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_filing_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RestatementEvent(Base):
    __tablename__ = "restatement_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    original_filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
    )
    new_filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    affected_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        UniqueConstraint("security_id", "fetched_at", name="uq_market_snapshots_security_fetched"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[SourceProvider] = mapped_column(
        Enum(SourceProvider, name="source_provider", create_type=False), nullable=False
    )
    price: Mapped[float | None] = mapped_column(Numeric)
    market_cap: Mapped[float | None] = mapped_column(Numeric)
    volume: Mapped[float | None] = mapped_column(Numeric)
    currency: Mapped[str] = mapped_column(String, nullable=False, server_default="BRL")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
