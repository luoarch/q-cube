"""Statistical metrics: PSR, DSR, skewness, kurtosis.

References:
- Bailey & Lopez de Prado (2014) — The Deflated Sharpe Ratio
- Lopez de Prado (2018) — Advances in Financial Machine Learning
"""

from __future__ import annotations

import math

from q3_quant_engine.backtest.metrics import _mean, _std


def _skewness(xs: list[float]) -> float:
    """Sample skewness (Fisher's definition)."""
    n = len(xs)
    if n < 3:
        return 0.0
    m = _mean(xs)
    s = _std(xs, ddof=1)
    if s == 0:
        return 0.0
    return (n / ((n - 1) * (n - 2))) * sum(((x - m) / s) ** 3 for x in xs)


def _kurtosis_excess(xs: list[float]) -> float:
    """Sample excess kurtosis (Fisher's, normal = 0)."""
    n = len(xs)
    if n < 4:
        return 0.0
    m = _mean(xs)
    s = _std(xs, ddof=1)
    if s == 0:
        return 0.0
    raw = (n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3)) * sum(((x - m) / s) ** 4 for x in xs)
    correction = (3 * (n - 1) ** 2) / ((n - 2) * (n - 3))
    return raw - correction


def _normal_cdf(x: float) -> float:
    """Cumulative distribution function of the standard normal."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float,
    n_returns: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
) -> float:
    """Probabilistic Sharpe Ratio (PSR).

    Probability that the true Sharpe exceeds benchmark_sharpe,
    accounting for non-normality of returns.

    PSR = Phi( (SR - SR*) / SE(SR) )
    SE(SR) = sqrt( (1 - skew*SR + (kurtosis-1)/4 * SR^2) / (n-1) )
    """
    if n_returns <= 1:
        return 0.0

    sr = observed_sharpe
    sr_star = benchmark_sharpe

    # Standard error of Sharpe ratio under non-normal returns
    se_sq = (1.0 - skew * sr + (excess_kurtosis / 4.0) * sr ** 2) / (n_returns - 1)
    if se_sq <= 0:
        return 1.0 if sr > sr_star else 0.0

    se = math.sqrt(se_sq)
    if se == 0:
        return 1.0 if sr > sr_star else 0.0

    z = (sr - sr_star) / se
    return _normal_cdf(z)


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_returns: int,
    n_trials: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
    variance_of_sharpes: float | None = None,
) -> float:
    """Deflated Sharpe Ratio (DSR).

    Adjusts for multiple testing by computing the expected maximum
    Sharpe under the null and using it as the PSR benchmark.

    E[max(SR)] ~ sqrt(V[SR]) * ((1-gamma)*Phi^{-1}(1-1/N) + gamma*Phi^{-1}(1-1/(N*e)))
    where gamma ~ 0.5772 (Euler-Mascheroni) and N = n_trials.

    Simplified: E[max(SR)] ~ sqrt(V[SR]) * sqrt(2*ln(N))
    """
    if n_trials <= 0 or n_returns <= 1:
        return 0.0

    # Variance of Sharpe ratios across trials
    if variance_of_sharpes is None:
        # Under null (true SR=0), Var(SR) ~ 1/(n-1)
        variance_of_sharpes = 1.0 / (n_returns - 1)

    # Expected maximum Sharpe under null (simplified Bonferroni-like)
    if n_trials <= 1:
        sr_star = 0.0
    else:
        sr_star = math.sqrt(variance_of_sharpes) * math.sqrt(2.0 * math.log(n_trials))

    return probabilistic_sharpe_ratio(
        observed_sharpe=observed_sharpe,
        benchmark_sharpe=sr_star,
        n_returns=n_returns,
        skew=skew,
        excess_kurtosis=excess_kurtosis,
    )


def compute_statistical_metrics(
    returns: list[float],
    sharpe: float,
    n_trials: int = 1,
    benchmark_sharpe: float = 0.0,
) -> dict:
    """Compute PSR, DSR, skewness, and kurtosis from return series."""
    n = len(returns)
    skew = _skewness(returns)
    kurt = _kurtosis_excess(returns)

    psr = probabilistic_sharpe_ratio(
        observed_sharpe=sharpe,
        benchmark_sharpe=benchmark_sharpe,
        n_returns=n,
        skew=skew,
        excess_kurtosis=kurt,
    )

    dsr = deflated_sharpe_ratio(
        observed_sharpe=sharpe,
        n_returns=n,
        n_trials=n_trials,
        skew=skew,
        excess_kurtosis=kurt,
    )

    return {
        "psr": round(psr, 6),
        "dsr": round(dsr, 6),
        "skewness": round(skew, 6),
        "excess_kurtosis": round(kurt, 6),
        "n_returns": n,
        "n_trials": n_trials,
    }
