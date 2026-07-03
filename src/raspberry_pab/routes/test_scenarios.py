"""Admin routes for predefined test scenarios."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.models import TestScenarioRunResult, TestScenarioSummary
from raspberry_pab.routes.schedule import get_store, require_admin_pin
from raspberry_pab.test_scenarios import TestScenarioRunner, list_scenarios

router = APIRouter(prefix="/api", tags=["test-scenarios"])


@router.get(
    "/admin/test-scenarios",
    response_model=list[TestScenarioSummary],
    dependencies=[Depends(require_admin_pin)],
)
def get_test_scenarios() -> list[TestScenarioSummary]:
    return list_scenarios()


@router.post(
    "/admin/test-scenarios/{scenario_id}/run",
    response_model=TestScenarioRunResult,
    dependencies=[Depends(require_admin_pin)],
)
def run_test_scenario(request: Request, scenario_id: str) -> TestScenarioRunResult:
    runner = TestScenarioRunner(get_store(request))
    try:
        return runner.run(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    finally:
        runner.close()
