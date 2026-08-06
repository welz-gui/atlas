from app.models.domain import Organization, Project, EAPItem, TaskItem

def test_eap_and_kanban_tasks(db_session):
    org = Organization(name="Org Test Plan")
    db_session.add(org)
    db_session.commit()

    project = Project(
        organization_id=org.id,
        name="Projeto Teste Plan",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        zone="Z2",
        building_type="residencial_unifamiliar"
    )
    db_session.add(project)
    db_session.commit()

    # Create EAP Parent & Child
    eap_parent = EAPItem(project_id=project.id, code="1.0", name="1. Fundações", item_type="etapa", progress_percent=50.0)
    db_session.add(eap_parent)
    db_session.commit()

    eap_child = EAPItem(project_id=project.id, code="1.1", name="Estacas", item_type="subetapa", parent_id=eap_parent.id)
    db_session.add(eap_child)
    db_session.commit()

    # Create Task
    task = TaskItem(
        project_id=project.id,
        eap_item_id=eap_child.id,
        title="Escavação de estacas",
        status="em_andamento",
        priority="alta"
    )
    db_session.add(task)
    db_session.commit()

    fetched_task = db_session.query(TaskItem).filter(TaskItem.id == task.id).first()
    assert fetched_task is not None
    assert fetched_task.status == "em_andamento"
    assert fetched_task.eap_item.code == "1.1"

    # Update Task Status (Kanban Drag & Drop simulation)
    fetched_task.status = "concluido"
    db_session.commit()

    updated_task = db_session.query(TaskItem).filter(TaskItem.id == task.id).first()
    assert updated_task.status == "concluido"
