"""Experiment endpoints: create, list, get, start/stop, analyze."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.analytics.bayesian import VariantStats, analyze_experiment
from nexus.api.schemas import (
    CreateExperimentRequest,
    ExperimentListResponse,
    ExperimentResponse,
)
from nexus.core.logging import get_logger
from nexus.db.models import Experiment, ExperimentAssignment
from nexus.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["experiments"])
logger = get_logger(__name__)

_DB_UNAVAILABLE = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Database unavailable",
)


def _build_response(
    exp: Experiment,
    assignments: list[ExperimentAssignment],
) -> ExperimentResponse:
    """Build response with aggregated stats from assignments."""
    control_total = sum(1 for a in assignments if a.variant == "control")
    control_up = sum(1 for a in assignments if a.variant == "control" and a.outcome == "up")
    control_down = sum(1 for a in assignments if a.variant == "control" and a.outcome == "down")

    treatment_total = sum(1 for a in assignments if a.variant == "treatment")
    treatment_up = sum(1 for a in assignments if a.variant == "treatment" and a.outcome == "up")
    treatment_down = sum(1 for a in assignments if a.variant == "treatment" and a.outcome == "down")

    return ExperimentResponse(
        id=exp.id,
        name=exp.name,
        description=exp.description,
        control_model=exp.control_model,
        treatment_model=exp.treatment_model,
        traffic_split=exp.traffic_split,
        strategy=exp.strategy,
        status=exp.status,
        min_samples=exp.min_samples,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
        control_total=control_total,
        control_up=control_up,
        control_down=control_down,
        treatment_total=treatment_total,
        treatment_up=treatment_up,
        treatment_down=treatment_down,
    )


async def _get_experiment_or_404(db: AsyncSession, experiment_id: str) -> Experiment:
    """Fetch experiment or raise 404."""
    stmt = select(Experiment).where(Experiment.id == experiment_id)
    result = await db.execute(stmt)
    exp = result.scalar_one_or_none()
    if exp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    return exp


async def _get_assignments(db: AsyncSession, experiment_id: str) -> list[ExperimentAssignment]:
    """Fetch all assignments for an experiment."""
    stmt = select(ExperimentAssignment).where(ExperimentAssignment.experiment_id == experiment_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    request: CreateExperimentRequest,
    db: AsyncSession | None = Depends(get_db),
) -> ExperimentResponse:
    """Create a new A/B experiment."""
    if db is None:
        raise _DB_UNAVAILABLE

    exp = Experiment(
        name=request.name,
        description=request.description,
        control_model=request.control_model,
        treatment_model=request.treatment_model,
        traffic_split=request.traffic_split,
        strategy=request.strategy.value,
        status="draft",
        min_samples=request.min_samples,
    )
    db.add(exp)
    await db.flush()
    await db.refresh(exp)
    logger.info("Experiment created", id=exp.id, name=exp.name)
    return _build_response(exp, [])


@router.get("/experiments", response_model=ExperimentListResponse)
async def list_experiments(
    db: AsyncSession | None = Depends(get_db),
) -> ExperimentListResponse:
    """List all experiments."""
    if db is None:
        return ExperimentListResponse(experiments=[])

    stmt = select(Experiment).order_by(Experiment.created_at.desc())
    result = await db.execute(stmt)
    experiments = result.scalars().all()

    responses = []
    for exp in experiments:
        assignments = await _get_assignments(db, exp.id)
        responses.append(_build_response(exp, assignments))

    return ExperimentListResponse(experiments=responses)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    db: AsyncSession | None = Depends(get_db),
) -> ExperimentResponse:
    """Get experiment details with stats."""
    if db is None:
        raise _DB_UNAVAILABLE

    exp = await _get_experiment_or_404(db, experiment_id)
    assignments = await _get_assignments(db, experiment_id)
    return _build_response(exp, assignments)


@router.post("/experiments/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
    experiment_id: str,
    db: AsyncSession | None = Depends(get_db),
) -> ExperimentResponse:
    """Start an experiment (transition from draft to running)."""
    if db is None:
        raise _DB_UNAVAILABLE

    exp = await _get_experiment_or_404(db, experiment_id)
    if exp.status not in ("draft", "stopped"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start experiment with status '{exp.status}'",
        )

    exp.status = "running"
    await db.flush()
    await db.refresh(exp)
    logger.info("Experiment started", id=experiment_id)
    return _build_response(exp, [])


@router.post("/experiments/{experiment_id}/stop", response_model=ExperimentResponse)
async def stop_experiment(
    experiment_id: str,
    db: AsyncSession | None = Depends(get_db),
) -> ExperimentResponse:
    """Stop a running experiment."""
    if db is None:
        raise _DB_UNAVAILABLE

    exp = await _get_experiment_or_404(db, experiment_id)
    exp.status = "stopped"
    await db.flush()
    await db.refresh(exp)
    logger.info("Experiment stopped", id=experiment_id)
    return _build_response(exp, [])


@router.get("/experiments/{experiment_id}/analyze")
async def analyze(
    experiment_id: str,
    db: AsyncSession | None = Depends(get_db),
) -> dict:
    """Run Bayesian analysis on experiment results."""
    if db is None:
        raise _DB_UNAVAILABLE

    exp = await _get_experiment_or_404(db, experiment_id)
    assignments = await _get_assignments(db, experiment_id)

    control = VariantStats(
        total=sum(1 for a in assignments if a.variant == "control"),
        successes=sum(1 for a in assignments if a.variant == "control" and a.outcome == "up"),
        failures=sum(1 for a in assignments if a.variant == "control" and a.outcome == "down"),
    )
    treatment = VariantStats(
        total=sum(1 for a in assignments if a.variant == "treatment"),
        successes=sum(1 for a in assignments if a.variant == "treatment" and a.outcome == "up"),
        failures=sum(1 for a in assignments if a.variant == "treatment" and a.outcome == "down"),
    )

    bayes = analyze_experiment(control, treatment, min_samples=exp.min_samples)

    return {
        "experiment_id": experiment_id,
        "experiment_name": exp.name,
        "control": {
            "model": exp.control_model,
            "total": control.total,
            "successes": control.successes,
            "failures": control.failures,
            "rate": control.rate,
            "posterior_mean": bayes.control_posterior_mean,
            "ci_95": [bayes.control_ci_low, bayes.control_ci_high],
        },
        "treatment": {
            "model": exp.treatment_model,
            "total": treatment.total,
            "successes": treatment.successes,
            "failures": treatment.failures,
            "rate": treatment.rate,
            "posterior_mean": bayes.treatment_posterior_mean,
            "ci_95": [bayes.treatment_ci_low, bayes.treatment_ci_high],
        },
        "prob_treatment_better": bayes.prob_treatment_better,
        "expected_loss_control": bayes.expected_loss_control,
        "expected_loss_treatment": bayes.expected_loss_treatment,
        "recommendation": bayes.recommendation,
        "should_stop": bayes.should_stop,
        "reason": bayes.reason,
    }
