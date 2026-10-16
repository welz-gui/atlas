from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.domain import (
    ProtocolEvent,
    ProtocolProcess,
    ProtocolRequirement,
    ProtocolStatus,
    User,
)
from app.schemas.domain import ProtocolRequirementCreate
from app.services.regulatory_engine import RegulatoryEngine

@dataclass
class EventPayload:
    event_type: str
    description: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None

class ProtocolService:
    @staticmethod
    def record_event(
        db: Session,
        process: ProtocolProcess,
        user: User,
        payload: EventPayload,
    ) -> None:
        db.add(
            ProtocolEvent(
                organization_id=process.organization_id,
                process_id=process.id,
                event_type=payload.event_type,
                from_status=payload.from_status,
                to_status=payload.to_status,
                description=payload.description,
                actor_id=user.id,
                actor_name=user.name,
            )
        )

    @staticmethod
    def create_requirement(
        db: Session,
        process: ProtocolProcess,
        user: User,
        payload: ProtocolRequirementCreate,
    ) -> ProtocolRequirement:
        was_predicted = None
        if payload.linked_rule_key:
            run = RegulatoryEngine.latest_run(db, process.project_id)
            if run:
                match = next(
                    (v for v in run.validations if v.rule_id == payload.linked_rule_key),
                    None,
                )
                if match is not None:
                    was_predicted = match.status in ("nao_conforme", "atencao")

        next_sequence = len(process.requirements) + 1
        requirement = ProtocolRequirement(
            organization_id=user.organization_id,
            process_id=process.id,
            sequence=next_sequence,
            description=payload.description,
            origin=payload.origin,
            raised_at=payload.raised_at,
            due_date=payload.due_date,
            linked_rule_key=payload.linked_rule_key,
            was_predicted=was_predicted,
        )
        db.add(requirement)

        ProtocolService.record_event(
            db,
            process,
            user,
            EventPayload(
                event_type="exigencia_registrada",
                description=f"Exigência {next_sequence}: {payload.description[:120]}",
            ),
        )

        # Uma exigência aberta muda a situação do processo — a menos que já esteja
        # em correção ou encerrado.
        if process.status not in ProtocolStatus.TERMINAL | {ProtocolStatus.EM_CORRECAO}:
            process.status = ProtocolStatus.NOTIFICADO

        db.commit()
        db.refresh(requirement)
        return requirement
