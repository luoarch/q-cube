import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import HALFVEC as HalfVec

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


class CanonicalKey(str, enum.Enum):
    """Canonical financial statement line keys (CVM CD_CONTA mapping)."""

    revenue = "revenue"
    cost_of_goods_sold = "cost_of_goods_sold"
    gross_profit = "gross_profit"
    operating_expenses = "operating_expenses"
    ebit = "ebit"
    financial_result = "financial_result"
    ebt = "ebt"
    income_tax = "income_tax"
    net_income = "net_income"
    total_assets = "total_assets"
    current_assets = "current_assets"
    cash_and_equivalents = "cash_and_equivalents"
    non_current_assets = "non_current_assets"
    fixed_assets = "fixed_assets"
    intangible_assets = "intangible_assets"
    total_liabilities = "total_liabilities"
    current_liabilities = "current_liabilities"
    short_term_debt = "short_term_debt"
    non_current_liabilities = "non_current_liabilities"
    long_term_debt = "long_term_debt"
    equity = "equity"
    cash_from_operations = "cash_from_operations"
    cash_from_investing = "cash_from_investing"
    cash_from_financing = "cash_from_financing"
    shareholder_distributions = "shareholder_distributions"


class MetricCode(str, enum.Enum):
    """Derived metric codes computed by the MetricsEngine."""

    ebitda = "ebitda"
    net_debt = "net_debt"
    roic = "roic"
    roe = "roe"
    earnings_yield = "earnings_yield"
    enterprise_value = "enterprise_value"
    gross_margin = "gross_margin"
    ebit_margin = "ebit_margin"
    net_margin = "net_margin"
    cash_conversion = "cash_conversion"
    debt_to_ebitda = "debt_to_ebitda"
    interest_coverage = "interest_coverage"
    dividend_yield = "dividend_yield"
    net_buyback_yield = "net_buyback_yield"
    net_payout_yield = "net_payout_yield"
    nby_proxy_free = "nby_proxy_free"
    npy_proxy_free = "npy_proxy_free"


class SourceProvider(str, enum.Enum):
    cvm = "cvm"
    brapi = "brapi"
    dados_de_mercado = "dados_de_mercado"
    manual = "manual"
    yahoo = "yahoo"


class ThesisBucket(str, enum.Enum):
    A_DIRECT = "A_DIRECT"
    B_INDIRECT = "B_INDIRECT"
    C_NEUTRAL = "C_NEUTRAL"
    D_FRAGILE = "D_FRAGILE"


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
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    ai_daily_cost_limit_usd: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="10.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    primary_rule_version: Mapped[str | None] = mapped_column(String)
    primary_rule_reason: Mapped[str | None] = mapped_column(String)
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
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    publication_date: Mapped[date | None] = mapped_column(Date)
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


class RefinementResultModel(Base):
    __tablename__ = "refinement_results"
    __table_args__ = (
        UniqueConstraint("strategy_run_id", "issuer_id", name="uq_refinement_results_run_issuer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    strategy_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategy_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    base_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    earnings_quality_score: Mapped[float | None] = mapped_column(Numeric)
    safety_score: Mapped[float | None] = mapped_column(Numeric)
    operating_consistency_score: Mapped[float | None] = mapped_column(Numeric)
    capital_discipline_score: Mapped[float | None] = mapped_column(Numeric)
    refinement_score: Mapped[float | None] = mapped_column(Numeric)
    adjusted_score: Mapped[float | None] = mapped_column(Numeric)
    adjusted_rank: Mapped[int | None] = mapped_column(Integer)
    flags_json: Mapped[dict | None] = mapped_column(JSONB)
    trend_data_json: Mapped[dict | None] = mapped_column(JSONB)
    scoring_details_json: Mapped[dict | None] = mapped_column(JSONB)
    data_completeness_json: Mapped[dict | None] = mapped_column(JSONB)
    score_reliability: Mapped[str | None] = mapped_column(String)
    issuer_classification: Mapped[str | None] = mapped_column(String)
    formula_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    weights_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChatMode(str, enum.Enum):
    free_chat = "free_chat"
    agent_solo = "agent_solo"
    roundtable = "roundtable"
    debate = "debate"
    comparison = "comparison"


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"
    agent = "agent"


class AgentId(str, enum.Enum):
    barsi = "barsi"
    graham = "graham"
    greenblatt = "greenblatt"
    buffett = "buffett"
    moderator = "moderator"


class AgentVerdict(str, enum.Enum):
    buy = "buy"
    watch = "watch"
    avoid = "avoid"
    insufficient_data = "insufficient_data"


class CouncilMode(str, enum.Enum):
    solo = "solo"
    roundtable = "roundtable"
    debate = "debate"
    comparison = "comparison"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

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
    title: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[ChatMode] = mapped_column(
        Enum(ChatMode, name="chat_mode"), nullable=False, server_default="free_chat"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, name="chat_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(20))
    tool_calls_json: Mapped[dict | None] = mapped_column(JSONB)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric)
    provider_used: Mapped[str | None] = mapped_column(String(20))
    model_used: Mapped[str | None] = mapped_column(String(50))
    fallback_level: Mapped[int | None] = mapped_column(Integer)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CouncilSession(Base):
    __tablename__ = "council_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[CouncilMode] = mapped_column(Enum(CouncilMode, name="council_mode"), nullable=False)
    asset_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    agent_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    input_hash: Mapped[str | None] = mapped_column(String(64))
    audit_trail_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CouncilOpinion(Base):
    __tablename__ = "council_opinions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    council_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(20), nullable=False)
    verdict: Mapped[AgentVerdict] = mapped_column(
        Enum(AgentVerdict, name="agent_verdict"), nullable=False
    )
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    opinion_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hard_rejects_json: Mapped[dict | None] = mapped_column(JSONB)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    provider_used: Mapped[str | None] = mapped_column(String(20))
    model_used: Mapped[str | None] = mapped_column(String(50))
    fallback_level: Mapped[int | None] = mapped_column(Integer)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CouncilDebate(Base):
    __tablename__ = "council_debates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    council_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    target_agent_id: Mapped[str | None] = mapped_column(String(20))
    provider_used: Mapped[str | None] = mapped_column(String(20))
    model_used: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CouncilSynthesis(Base):
    __tablename__ = "council_syntheses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    council_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scoreboard_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    conflicts_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synthesis_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserContextProfile(Base):
    __tablename__ = "user_context_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_context_profiles_user_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    preferred_strategy: Mapped[str | None] = mapped_column(String)
    watchlist_json: Mapped[dict | None] = mapped_column(JSONB)
    preferences_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "chunk_index", name="uq_embeddings_entity_chunk"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(HalfVec(1536), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    model_used: Mapped[str] = mapped_column(String, nullable=False, server_default="text-embedding-3-small")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
    shares_outstanding: Mapped[float | None] = mapped_column(Numeric)


# ---------------------------------------------------------------------------
# AI Assistant enums + tables
# ---------------------------------------------------------------------------


class AIModule(str, enum.Enum):
    ranking_explainer = "ranking_explainer"
    backtest_narrator = "backtest_narrator"
    metric_explainer = "metric_explainer"
    rubric_suggester = "rubric_suggester"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ConfidenceLevel(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ExplanationType(str, enum.Enum):
    position = "position"
    sector = "sector"
    outlier = "outlier"
    metric = "metric"


class NoteType(str, enum.Enum):
    summary = "summary"
    concern = "concern"
    highlight = "highlight"
    recommendation = "recommendation"


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "module", "trigger_entity_id", "input_hash", "prompt_version",
            name="uq_ai_suggestions_dedup",
        ),
        Index("idx_ai_suggestions_tenant_module", "tenant_id", "module"),
        Index("idx_ai_suggestions_trigger", "trigger_entity_id"),
        Index("idx_ai_suggestions_review", "review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    module: Mapped[AIModule] = mapped_column(Enum(AIModule, name="ai_module"), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level"), nullable=False
    )
    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens_used: Mapped[int] = mapped_column(nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(nullable=False)
    completion_tokens: Mapped[int] = mapped_column(nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), nullable=False, server_default="pending"
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    explanations: Mapped[list["AIExplanation"]] = relationship(
        back_populates="suggestion", cascade="all, delete-orphan"
    )
    research_notes: Mapped[list["AIResearchNote"]] = relationship(
        back_populates="suggestion", cascade="all, delete-orphan"
    )


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_suggestions.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation_type: Mapped[ExplanationType] = mapped_column(
        Enum(ExplanationType, name="explanation_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    suggestion: Mapped[AISuggestion] = relationship(back_populates="explanations")


class AIResearchNote(Base):
    __tablename__ = "ai_research_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_suggestions.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_type: Mapped[NoteType] = mapped_column(
        Enum(NoteType, name="note_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    suggestion: Mapped[AISuggestion] = relationship(back_populates="research_notes")


# ---------------------------------------------------------------------------
# Plan 2 — Global Thesis Layer
# ---------------------------------------------------------------------------


class Plan2Run(Base):
    __tablename__ = "plan2_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategy_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    # versioning
    thesis_config_version: Mapped[str] = mapped_column(String(20), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # metadata
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_eligible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ineligible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bucket_distribution_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # lifecycle
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Plan2ThesisScore(Base):
    __tablename__ = "plan2_thesis_scores"
    __table_args__ = (
        UniqueConstraint("plan2_run_id", "issuer_id", name="uq_plan2_thesis_scores_run_issuer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan2_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plan2_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id"),
        nullable=False,
    )

    # eligibility
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    eligibility_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # opportunity vector (0-100, NULL if ineligible)
    direct_commodity_exposure_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    indirect_commodity_exposure_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    export_fx_leverage_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    final_commodity_affinity_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    # fragility vector (0-100, NULL if ineligible)
    refinancing_stress_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    usd_debt_exposure_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    usd_import_dependence_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    usd_revenue_offset_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    final_dollar_fragility_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    # ranking (NULL if ineligible)
    bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    thesis_rank_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    thesis_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # provenance
    feature_input_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Plan2RubricScore(Base):
    __tablename__ = "plan2_rubric_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id"),
        nullable=False,
    )
    dimension_key: Mapped[str] = mapped_column(String(60), nullable=False)
    score: Mapped[float] = mapped_column(Numeric, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_version: Mapped[str] = mapped_column(String(60), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, server_default="medium")
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assessed_at: Mapped[date] = mapped_column(Date, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Research panel (3C.2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Strategy Status Governance
# ---------------------------------------------------------------------------


class StrategyStatusRegistry(Base):
    __tablename__ = "strategy_status_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_key: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_type: Mapped[str] = mapped_column(
        Enum("magic_formula_original", "magic_formula_brazil", "magic_formula_hybrid", name="strategy_type", create_type=False),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        Enum("CONTROL", "CANDIDATE", "FRONTRUNNER", name="strategy_role", create_type=False),
        nullable=False,
    )
    promotion_status: Mapped[str] = mapped_column(
        Enum("NOT_EVALUATED", "BLOCKED", "PROMOTED", "REJECTED", name="promotion_status", create_type=False),
        nullable=False,
    )
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    experiment_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_sharpe_avg: Mapped[float | None] = mapped_column(Numeric)
    oos_sharpe_avg: Mapped[float | None] = mapped_column(Numeric)
    promotion_checks: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_by: Mapped[str] = mapped_column(
        Enum("TECH_LEAD_REVIEW", "AUTOMATED_PIPELINE", name="decision_source", create_type=False),
        nullable=False,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Universe Classification (Plan 4)
# ---------------------------------------------------------------------------


class UniverseClassification(Base):
    __tablename__ = "universe_classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    universe_class: Mapped[str] = mapped_column(
        Enum("CORE_ELIGIBLE", "DEDICATED_STRATEGY_ONLY", "PERMANENTLY_EXCLUDED", name="universe_class", create_type=False),
        nullable=False,
    )
    dedicated_strategy_type: Mapped[str | None] = mapped_column(
        Enum("FINANCIAL", "REAL_ESTATE_DEVELOPMENT", "UNCLASSIFIED_HOLDING", name="dedicated_strategy_type", create_type=False),
    )
    permanent_exclusion_reason: Mapped[str | None] = mapped_column(
        Enum("RETAIL_WHOLESALE", "AIRLINE", "TOURISM_HOSPITALITY", "FOREIGN_RETAIL", "NOT_A_COMPANY", name="permanent_exclusion_reason", create_type=False),
    )
    classification_rule_code: Mapped[str] = mapped_column(
        Enum("SECTOR_MAP", "ISSUER_OVERRIDE", name="classification_rule_code", create_type=False),
        nullable=False,
    )
    classification_reason: Mapped[str] = mapped_column(Text, nullable=False)
    matched_sector_key: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NpyResearchPanel(Base):
    __tablename__ = "npy_research_panel"
    __table_args__ = (
        UniqueConstraint("issuer_id", "reference_date", "dataset_version", name="uq_npy_panel_issuer_date_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    primary_security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="SET NULL"),
    )
    dividend_yield: Mapped[float | None] = mapped_column(Numeric)
    net_buyback_yield: Mapped[float | None] = mapped_column(Numeric)
    net_payout_yield: Mapped[float | None] = mapped_column(Numeric)
    dy_source_tier: Mapped[str | None] = mapped_column(String(1))
    nby_source_tier: Mapped[str | None] = mapped_column(String(1))
    market_cap_source_tier: Mapped[str | None] = mapped_column(String(1))
    shares_source_tier: Mapped[str | None] = mapped_column(String(1))
    npy_source_tier: Mapped[str | None] = mapped_column(String(1))
    quality_flag: Mapped[str | None] = mapped_column(String(1))
    formula_version: Mapped[str] = mapped_column(String(60), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dy_metric_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nby_metric_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    npy_metric_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    pit_compliant: Mapped[bool | None] = mapped_column(Boolean)
    knowledge_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NpyDatasetVersion(Base):
    __tablename__ = "npy_dataset_versions"

    dataset_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    knowledge_date: Mapped[date | None] = mapped_column(Date)
    pit_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="relaxed")
    formula_version: Mapped[str] = mapped_column(String(60), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    quality_distribution: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# CVM Share Counts (Plan 5)
# ---------------------------------------------------------------------------


class CVMShareCount(Base):
    """CVM composicao_capital share counts — PIT time series.

    Source: CVM DFP/ITR ZIP → composicao_capital CSV.
    One row per (issuer, reference_date, document_type).
    knowledge_date is NOT stored here — it is a lookup parameter (see Plan 5 §6.2).
    """

    __tablename__ = "cvm_share_counts"
    __table_args__ = (
        UniqueConstraint("issuer_id", "reference_date", "document_type", name="uq_cvm_shares_issuer_date_doctype"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    document_type: Mapped[str] = mapped_column(String(3), nullable=False)  # 'DFP' or 'ITR'
    total_shares: Mapped[float] = mapped_column(Numeric, nullable=False)
    treasury_shares: Mapped[float] = mapped_column(Numeric, nullable=False)
    net_shares: Mapped[float] = mapped_column(Numeric, nullable=False)
    publication_date_estimated: Mapped[date] = mapped_column(Date, nullable=False)
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Pilot Runtime (MF-RUNTIME-01A)
# ---------------------------------------------------------------------------


class RankingSnapshot(Base):
    """Daily snapshot of ranking state for pilot forward return tracking."""

    __tablename__ = "ranking_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "ticker", name="uq_ranking_snapshots_date_ticker"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    model_family: Mapped[str] = mapped_column(String, nullable=False)
    rank_within_model: Mapped[int] = mapped_column(Integer, nullable=False)
    composite_score: Mapped[float | None] = mapped_column(Numeric)
    investability_status: Mapped[str] = mapped_column(String, nullable=False)
    earnings_yield: Mapped[float | None] = mapped_column(Numeric)
    return_on_capital: Mapped[float | None] = mapped_column(Numeric)
    net_payout_yield: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ForwardReturn(Base):
    """Realized forward returns per snapshot/ticker/horizon."""

    __tablename__ = "forward_returns"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "ticker", "horizon", name="uq_forward_returns_date_ticker_horizon"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    horizon: Mapped[str] = mapped_column(String, nullable=False)
    price_t0: Mapped[float | None] = mapped_column(Numeric)
    price_tn: Mapped[float | None] = mapped_column(Numeric)
    return_value: Mapped[float | None] = mapped_column(Numeric)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
