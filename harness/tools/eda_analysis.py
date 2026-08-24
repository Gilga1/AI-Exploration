from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool
from harness.analytics.lib import cohort_analysis, detect_anomalies, trend_forecast


class CohortAnalysisInput(BaseModel):
    records: list[dict[str, Any]]
    cohort_field: str
    measure_field: str
    agg: Literal["sum", "avg", "count", "min", "max"] = "sum"


class CohortAnalysisOutput(BaseModel):
    cohorts: list[dict[str, Any]]


@register_tool
class CohortAnalysisTool:
    spec = ToolSpec(
        name="cohort_analysis",
        description="Group records into cohorts and aggregate a measure field.",
        capability_tags=["analytics", "eda", "cohort"],
        input_schema=CohortAnalysisInput,
        output_schema=CohortAnalysisOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: CohortAnalysisInput, *, context: RunContext) -> CohortAnalysisOutput:
        cohorts = cohort_analysis(
            args.records,
            cohort_field=args.cohort_field,
            measure_field=args.measure_field,
            agg=args.agg,
        )
        return CohortAnalysisOutput(cohorts=cohorts)


class DetectAnomaliesInput(BaseModel):
    records: list[dict[str, Any]]
    value_field: str
    z_threshold: float = Field(default=2.0, ge=0.5, le=5.0)


class DetectAnomaliesOutput(BaseModel):
    anomalies: list[dict[str, Any]]
    anomaly_count: int


@register_tool
class DetectAnomaliesTool:
    spec = ToolSpec(
        name="detect_anomalies",
        description="Detect statistical anomalies in a numeric field using z-score thresholding.",
        capability_tags=["analytics", "eda", "anomaly"],
        input_schema=DetectAnomaliesInput,
        output_schema=DetectAnomaliesOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: DetectAnomaliesInput, *, context: RunContext) -> DetectAnomaliesOutput:
        anomalies = detect_anomalies(
            args.records,
            value_field=args.value_field,
            z_threshold=args.z_threshold,
        )
        return DetectAnomaliesOutput(anomalies=anomalies, anomaly_count=len(anomalies))


class TrendForecastInput(BaseModel):
    records: list[dict[str, Any]]
    date_field: str
    value_field: str
    periods_ahead: int = Field(default=3, ge=1, le=12)


class TrendForecastOutput(BaseModel):
    history: list[dict[str, Any]]
    forecast: list[dict[str, Any]]
    slope: float


@register_tool
class TrendForecastTool:
    spec = ToolSpec(
        name="trend_forecast",
        description="Simple linear trend forecast over time-series records.",
        capability_tags=["analytics", "eda", "forecast"],
        input_schema=TrendForecastInput,
        output_schema=TrendForecastOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: TrendForecastInput, *, context: RunContext) -> TrendForecastOutput:
        result = trend_forecast(
            args.records,
            date_field=args.date_field,
            value_field=args.value_field,
            periods_ahead=args.periods_ahead,
        )
        return TrendForecastOutput(
            history=result["history"],
            forecast=result["forecast"],
            slope=float(result["slope"]),
        )
