import pytest
from fastapi import HTTPException
from app.api.deps import get_scoped_or_404
from app.models.domain import TaskItem


def test_get_scoped_or_404_success(db_session, engineer, project):
    # Setup test data
    task = TaskItem(
        organization_id=engineer.organization_id,
        project_id=project["id"],
        title="Test Task",
    )
    db_session.add(task)
    db_session.commit()

    # Execute
    result = get_scoped_or_404(db_session, TaskItem, task.id, engineer, "Tarefa")

    # Assert
    assert result.id == task.id
    assert result.title == "Test Task"


def test_get_scoped_or_404_not_found(db_session, engineer):
    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, TaskItem, "non-existent-id", engineer, "Tarefa")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Tarefa não encontrado."


def test_get_scoped_or_404_wrong_organization(db_session, engineer, project):
    from tests.conftest import make_org, make_user
    from app.models.domain import UserRole

    # Create an item in engineer's organization
    task = TaskItem(
        organization_id=engineer.organization_id,
        project_id=project["id"],
        title="Test Task",
    )
    db_session.add(task)
    db_session.commit()

    # Create user in another organization
    outra_org = make_org(db_session, "Outra Org")
    outro_user = make_user(
        db_session, outra_org, UserRole.ENGINEER, "outro@atlas-qa.com"
    )

    # Execute as outro_user, attempting to access engineer's task
    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, TaskItem, task.id, outro_user, "Tarefa")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Tarefa não encontrado."


def test_get_scoped_or_404_default_label(db_session, engineer):
    with pytest.raises(HTTPException) as exc_info:
        get_scoped_or_404(db_session, TaskItem, "non-existent-id", engineer)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Recurso não encontrado."
