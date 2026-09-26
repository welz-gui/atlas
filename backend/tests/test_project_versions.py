from datetime import datetime
import pytest
from sqlalchemy.orm import Session

from app.models.domain import Project, ProjectVersion, ProjectVersionState, User
from app.schemas.domain import ProjectParameters
from app.services.project_versions import (
    VersionConfig,
    create_version,
    derive_next_version,
    set_official_baseline,
    version_content_hash,
)

@pytest.fixture
def project_orm(db_session, project):
    return db_session.get(Project, project["id"])

def test_version_content_hash():
    params1 = ProjectParameters(front_setback=5.0, built_area=150.0)
    params2 = ProjectParameters(front_setback=5.0, built_area=150.0)
    params3 = ProjectParameters(front_setback=5.0, built_area=160.0)

    hash1 = version_content_hash(params1)
    hash2 = version_content_hash(params2)
    hash3 = version_content_hash(params3)

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64  # sha256 hex digest length

def test_create_version_first(db_session: Session, project_orm: Project):
    params = ProjectParameters(front_setback=3.0, built_area=100.0)
    config = VersionConfig(change_reason="Initial", change_origin="test", state=ProjectVersionState.ESTUDO_PRELIMINAR)

    version = create_version(db_session, project_orm, params, config)

    assert version.version_number == 2 # Because `project` fixture already creates version 1
    assert version.front_setback == 3.0
    assert version.built_area == 100.0
    assert version.state == ProjectVersionState.ESTUDO_PRELIMINAR
    assert version.change_reason == "Initial"

def test_create_version_without_config(db_session: Session, project_orm: Project):
    params = ProjectParameters(front_setback=3.0, built_area=100.0)

    version = create_version(db_session, project_orm, params)

    assert version.version_number == 2 # Because `project` fixture already creates version 1
    assert version.front_setback == 3.0
    assert version.built_area == 100.0
    assert version.state == ProjectVersionState.ESTUDO_PRELIMINAR

def test_derive_next_version_inherits_fields(db_session: Session, project_orm: Project, engineer: User):
    params = ProjectParameters(front_setback=3.0, built_area=100.0, floors=2)
    config = VersionConfig(user=engineer)
    v1 = create_version(db_session, project_orm, params, config)

    updates = ProjectParameters(built_area=150.0) # only update built_area
    v2 = derive_next_version(db_session, project_orm, updates, config)

    assert v2.version_number == 3
    assert v2.front_setback == 3.0 # inherited
    assert v2.floors == 2 # inherited
    assert v2.built_area == 150.0 # updated

def test_derive_next_version_without_config(db_session: Session, project_orm: Project):
    updates = ProjectParameters(built_area=150.0) # only update built_area
    v2 = derive_next_version(db_session, project_orm, updates)

    assert v2.version_number == 2
    assert v2.built_area == 150.0 # updated

def test_set_official_baseline(db_session: Session, project_orm: Project):
    params = ProjectParameters(front_setback=3.0, built_area=100.0)
    v1 = create_version(db_session, project_orm, params)
    v2 = create_version(db_session, project_orm, params)

    # Must be approved to set as baseline
    with pytest.raises(ValueError, match="Somente uma versão no estado 'aprovada'"):
        set_official_baseline(db_session, project_orm, v1)

    v1.state = ProjectVersionState.APROVADA
    v2.state = ProjectVersionState.APROVADA
    db_session.commit()

    set_official_baseline(db_session, project_orm, v1)
    assert v1.is_official_baseline is True
    assert v2.is_official_baseline is False

    set_official_baseline(db_session, project_orm, v2)
    db_session.refresh(v1)
    assert v1.is_official_baseline is False
    assert v2.is_official_baseline is True
