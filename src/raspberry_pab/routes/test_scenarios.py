"""Admin routes for predefined test scenarios."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.models import (
    TestScenarioDefinition,
    TestScenarioRunResult,
    TestScenarioSummary,
)
from raspberry_pab.routes.schedule import get_store, require_admin_pin
from raspberry_pab.test_scenarios import (
    TestScenarioRunner,
    clear_scenario_data,
    create_scenario,
    delete_scenario,
    list_scenarios,
    load_scenario,
    save_scenario,
)

router = APIRouter(prefix="/api", tags=["test-scenarios"])


@router.get(
    "/admin/test-scenarios",
    response_model=list[TestScenarioSummary],
    dependencies=[Depends(require_admin_pin)],
)
def get_test_scenarios() -> list[TestScenarioSummary]:
    return list_scenarios()


@router.post(
    "/admin/test-scenarios",
    response_model=TestScenarioDefinition,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_pin)],
)
def create_test_scenario(scenario: TestScenarioDefinition) -> TestScenarioDefinition:
    try:
        create_scenario(scenario)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return scenario


@router.get(
    "/admin/test-scenarios/{scenario_id}",
    response_model=TestScenarioDefinition,
    dependencies=[Depends(require_admin_pin)],
)
def get_test_scenario(scenario_id: str) -> TestScenarioDefinition:
    try:
        return load_scenario(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/admin/test-scenarios/{scenario_id}",
    response_model=TestScenarioDefinition,
    dependencies=[Depends(require_admin_pin)],
)
def update_test_scenario(
    scenario_id: str,
    scenario: TestScenarioDefinition,
) -> TestScenarioDefinition:
    if scenario.id != scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario id in body must match URL",
        )
    try:
        save_scenario(scenario)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return scenario


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


@router.delete(
    "/admin/test-scenarios/{scenario_id}",
    dependencies=[Depends(require_admin_pin)],
)
def remove_test_scenario(scenario_id: str) -> dict[str, bool]:
    try:
        delete_scenario(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"deleted": True}


@router.delete(
    "/admin/test-scenarios/{scenario_id}/data",
    dependencies=[Depends(require_admin_pin)],
)
def delete_test_data(request: Request, scenario_id: str) -> dict[str, int]:
    try:
        result = clear_scenario_data(get_store(request), scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return result
