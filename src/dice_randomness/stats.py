"""Small statistical helpers with no SciPy dependency."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import erfc, sqrt
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class ChiSquareSummary:
    statistic: float
    degrees_of_freedom: int
    p_value_upper_approx: float
    p_value_method: str

    def to_jsonable(self):
        return asdict(self)


def chi_square_uniform(observed: Sequence[int], expected_each: float) -> ChiSquareSummary:
    df = len(observed) - 1
    if expected_each <= 0:
        return ChiSquareSummary(
            statistic=0.0,
            degrees_of_freedom=df,
            p_value_upper_approx=1.0,
            p_value_method="wilson_hilferty_normal_approximation",
        )
    statistic = sum(((count - expected_each) ** 2) / expected_each for count in observed)
    return ChiSquareSummary(
        statistic=statistic,
        degrees_of_freedom=df,
        p_value_upper_approx=chi_square_upper_tail_wilson_hilferty(statistic, df),
        p_value_method="wilson_hilferty_normal_approximation",
    )


def chi_square_upper_tail_wilson_hilferty(statistic: float, degrees_of_freedom: int) -> float:
    if degrees_of_freedom <= 0:
        return 1.0
    if statistic <= 0:
        return 1.0
    k = float(degrees_of_freedom)
    z = ((statistic / k) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * k))) / sqrt(2.0 / (9.0 * k))
    return 0.5 * erfc(z / sqrt(2.0))


def z_scores_for_cells(observed: Sequence[int], total: int, probability: float) -> List[float]:
    variance = total * probability * (1.0 - probability)
    if variance <= 0:
        return [0.0 for _ in observed]
    denom = sqrt(variance)
    expected = total * probability
    return [(count - expected) / denom for count in observed]


def max_abs(values: Iterable[float]) -> float:
    return max((abs(value) for value in values), default=0.0)
