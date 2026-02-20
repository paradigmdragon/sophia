import uuid
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from core.engine.schema import Episode, Backbone, Facet, Candidate, Event, MessageQueue
from core.engine.constants import FacetID, FacetValueCertainty, RuleID
from core.engine.conflict_rules import check_conflicts
from core.engine.heart import HeartEngine
from core.engine.epidora import EpidoraValidator
from core.engine.bitmap_validator import InvalidBitmapError, validate_bitmap

class WorkflowEngine:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.heart = HeartEngine(session_factory) # Phase 0 Heart
        self.epidora = EpidoraValidator()

    def _get_session(self):
        return self.session_factory()

    def _append_event(self, session: Session, *, episode_id: str | None, event_type: str, payload: Dict) -> None:
        session.add(
            Event(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                episode_id=episode_id,
                type=event_type,
                payload=payload,
            )
        )

    @staticmethod
    def _payload_as_dict(value) -> Dict:
        if isinstance(value, dict):
            return value
        return {}

    def _find_adopted_backbone_id(self, session: Session, *, episode_id: str, candidate_id: str) -> str | None:
        rows = (
            session.query(Event)
            .filter_by(episode_id=episode_id, type="ADOPT")
            .order_by(Event.at.desc())
            .limit(200)
            .all()
        )
        for row in rows:
            payload = self._payload_as_dict(row.payload)
            if str(payload.get("candidate_id", "")) == candidate_id:
                backbone_id = str(payload.get("backbone_id", "")).strip()
                if backbone_id:
                    return backbone_id
        return None

    def _load_candidate_for_episode(self, session: Session, *, episode_id: str, candidate_id: str) -> Candidate:
        candidate = session.query(Candidate).filter_by(candidate_id=candidate_id).first()
        if candidate is None:
            raise ValueError("Candidate not found")

        candidate_episode_id = str(candidate.episode_id or "").strip()
        requested_episode_id = str(episode_id or "").strip()
        if candidate_episode_id != requested_episode_id:
            raise ValueError(
                f"Candidate episode mismatch: candidate={candidate_episode_id} requested={requested_episode_id}"
            )
        return candidate

    def _record_bitmap_invalid(
        self,
        session: Session,
        *,
        episode_id: str,
        stage: str,
        bits_raw: object,
        reason: str,
        error: str,
        source: str | None = None,
        candidate_id: str | None = None,
        candidate_index: int | None = None,
    ) -> None:
        payload: Dict[str, object] = {
            "stage": stage,
            "bits_raw": bits_raw,
            "reason": reason,
            "error": error,
        }
        if source:
            payload["source"] = source
        if candidate_id:
            payload["candidate_id"] = candidate_id
        if candidate_index is not None:
            payload["candidate_index"] = int(candidate_index)
        self._append_event(session, episode_id=episode_id, event_type="BITMAP_INVALID", payload=payload)

    def ingest(self, log_ref: Dict) -> str:
        """
        Create a new Episode in UNDECIDED state.
        """
        session = self._get_session()
        try:
            ep_id = f"ep_{uuid.uuid4().hex[:8]}"
            episode = Episode(
                episode_id=ep_id,
                log_ref=log_ref,
                status='UNDECIDED'
            )
            
            # Log Event
            event = Event(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                episode_id=ep_id,
                type="INGEST",
                payload=log_ref
            )
            
            session.add(episode)
            session.add(event)
            session.commit()
            return ep_id
        finally:
            session.close()

    def propose(self, episode_id: str, candidates_data: List[Dict], source: str = "encoder") -> List[str]:
        """
        Add Candidates to an Episode.
        candidates_data: list of {backbone_bits: int, facets: [{id, val}, ...], note: str}
        """
        session = self._get_session()
        created_ids = []
        try:
            validated_data: list[tuple[Dict, int]] = []
            for idx, c_data in enumerate(candidates_data):
                bits_raw = c_data.get('backbone_bits')
                try:
                    validated = validate_bitmap(int(bits_raw))
                except (TypeError, ValueError, InvalidBitmapError) as exc:
                    reason = getattr(exc, "reason", "INVALID_BITMAP")
                    self._record_bitmap_invalid(
                        session,
                        episode_id=episode_id,
                        stage="propose",
                        bits_raw=bits_raw,
                        reason=reason,
                        error=str(exc),
                        source=source,
                        candidate_index=idx,
                    )
                    session.commit()
                    raise ValueError(
                        f"invalid backbone_bits for candidate: {bits_raw} [reason={reason}] ({exc})"
                    ) from exc
                validated_data.append((c_data, validated.bits))

            bits_hex: list[str] = []
            for c_data, valid_bits in validated_data:
                c_id = f"cand_{uuid.uuid4().hex[:8]}"
                candidate = Candidate(
                    candidate_id=c_id,
                    episode_id=episode_id,
                    proposed_by=source,
                    backbone_bits=valid_bits,
                    facets_json=c_data.get('facets', []),
                    note_thin=c_data.get('note'),
                    confidence=c_data.get('confidence', 0),
                    status='PENDING'
                )
                session.add(candidate)
                created_ids.append(c_id)
                bits_hex.append(f"0x{valid_bits:04X}")

                # Heart Trigger: Low Confidence
                # If ANY candidate has low confidence (< 50), trigger P3 ASK
                conf = c_data.get('confidence', 0)
                if conf < 50:
                    self.heart.trigger_message(
                        priority="P3",
                        type="ASK",
                        intent="low_confidence",
                        content=f"Candidate {c_id} has low confidence ({conf}%). Please verify context.",
                        episode_id=episode_id,
                        context={"candidate_id": c_id, "confidence": conf}
                    )
            
            # Log Event
            self._append_event(
                session,
                episode_id=episode_id,
                event_type="PROPOSE",
                payload={
                    "count": len(created_ids),
                    "source": source,
                    "bitmap_meta": {
                        "validated_count": len(validated_data),
                        "bits_hex": bits_hex[:10],
                    },
                },
            )
            session.commit()
            return created_ids
        finally:
            session.close()

    def adopt(self, episode_id: str, candidate_id: str) -> str:
        """
        Convert a Candidate to a Backbone.
        - If first backbone: PRIMARY
        - If subsequent: ALTERNATIVE
        - Apply Conflict Rules
        """
        session = self._get_session()
        try:
            candidate = self._load_candidate_for_episode(
                session, episode_id=episode_id, candidate_id=candidate_id
            )
            status = str(candidate.status or "").upper()
            if status == "ADOPTED":
                existing_backbone_id = self._find_adopted_backbone_id(
                    session, episode_id=episode_id, candidate_id=candidate_id
                )
                if existing_backbone_id:
                    return existing_backbone_id
                raise ValueError("Candidate status is ADOPTED")
            if status == "REJECTED":
                raise ValueError("Candidate status is REJECTED")
            if status != 'PENDING':
                raise ValueError(f"Candidate status is {candidate.status}")

            # 1. Determine Role
            existing_backbones = session.query(Backbone).filter_by(episode_id=episode_id, deprecated=False).count()
            role = "PRIMARY" if existing_backbones == 0 else "ALTERNATIVE"

            # 2. Create Backbone
            b_id = f"bb_{uuid.uuid4().hex[:8]}"
            bits = candidate.backbone_bits
            try:
                validated = validate_bitmap(int(bits))
            except (TypeError, ValueError, InvalidBitmapError) as exc:
                reason = getattr(exc, "reason", "INVALID_BITMAP")
                self._record_bitmap_invalid(
                    session,
                    episode_id=episode_id,
                    stage="adopt",
                    bits_raw=bits,
                    reason=reason,
                    error=str(exc),
                    candidate_id=candidate_id,
                )
                session.commit()
                raise ValueError(f"invalid backbone_bits for adopt: {bits} [reason={reason}] ({exc})") from exc

            backbone = Backbone(
                backbone_id=b_id,
                episode_id=episode_id,
                bits_a=validated.bits_a,
                bits_b=validated.bits_b,
                bits_c=validated.bits_c,
                bits_d=validated.bits_d,
                combined_bits=validated.bits,
                role=role,
                origin="ADOPT"
            )
            session.add(backbone)

            # 3. Create or Update Facets from Candidate
            # Logic: If FacetID exists, update it? Or allow multiples?
            # Spec 3.2: "Episode assigned Facet 0~N". 
            # Usually Certainty/Abstraction/Source are singular per episode in Phase 0.
            # Strategy: Upsert for singleton facets (Certainty, Abstraction, Source).
            # Allow multiple for others if needed (e.g. Alignment).
            
            # For Phase 0, let's enforce Singleton for Certainty, Abstraction, Source to avoid confusion.
            singleton_facets = {FacetID.CERTAINTY, FacetID.ABSTRACTION, FacetID.SOURCE}
            
            # Default Certainty = CONFIRMED (0x2)
            has_certainty = False
            
            for f_data in candidate.facets_json:
                f_id = f_data['id']
                if f_id == FacetID.CERTAINTY:
                    has_certainty = True
                    val = FacetValueCertainty.CONFIRMED # Upgrade pending to confirmed
                else:
                    val = f_data['value']
                
                # Check exist
                if f_id in singleton_facets:
                    existing = session.query(Facet).filter_by(episode_id=episode_id, facet_id=f_id).first()
                    if existing:
                        existing.value = val
                        continue

                # Insert new if not existing or not singleton
                facet = Facet(
                    facet_uuid=f"f_{uuid.uuid4().hex[:8]}",
                    episode_id=episode_id,
                    facet_id=f_id,
                    value=val
                )
                session.add(facet)
            
            if not has_certainty:
                # Upsert default confirmed certainty
                existing = session.query(Facet).filter_by(episode_id=episode_id, facet_id=FacetID.CERTAINTY).first()
                if existing:
                    # Don't overwrite if it exists (might be CONFLICT from before? No, Adopt should confirm it?)
                    # Actually, if we adopt a new backbone, does it resolve conflict?
                    # Spec says: "Facet 0x1... CONFLICT... if mechanically contradictory".
                    # We re-check conflict at the end of this function.
                    # So momentarily setting it to CONFIRMED is fine, it will be overwritten by check_conflicts if still conflicting.
                    existing.value = FacetValueCertainty.CONFIRMED
                else:
                    session.add(Facet(
                        facet_uuid=f"f_{uuid.uuid4().hex[:8]}",
                        episode_id=episode_id,
                        facet_id=FacetID.CERTAINTY,
                        value=FacetValueCertainty.CONFIRMED
                    ))

            # 4. Update Candidate Status
            candidate.status = 'ADOPTED' # Custom status, logically handled as resolved
            
            # 5. Update Episode Status
            session.query(Episode).filter_by(episode_id=episode_id).update({"status": "DECIDED"})

            # 6. Log Event
            session.add(Event(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                episode_id=episode_id,
                type="ADOPT",
                payload={"candidate_id": candidate_id, "role": role, "backbone_id": b_id}
            ))

            # Commit first to ensure backbone is visible for conflict check
            session.commit()

            # 7. Check Conflicts
            # Re-query episode to get full backbone list
            ep = session.query(Episode).filter_by(episode_id=episode_id).first()
            conflicts = check_conflicts(ep)
            
            if conflicts:
                # Mark Conflict Facet
                # Find existing Certainty facet and update to CONFLICT (0x3)
                # Or add new if somehow missing
                certainty_facet = session.query(Facet).filter_by(episode_id=episode_id, facet_id=FacetID.CERTAINTY).first()
                if certainty_facet:
                    certainty_facet.value = FacetValueCertainty.CONFLICT
                else:
                    session.add(Facet(
                        facet_uuid=f"f_{uuid.uuid4().hex[:8]}",
                        episode_id=episode_id,
                        facet_id=FacetID.CERTAINTY,
                        value=FacetValueCertainty.CONFLICT
                    ))
                
                # Log Conflict Event
                session.add(Event(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    episode_id=episode_id,
                    type="CONFLICT_MARK",
                    payload={"conflicts": conflicts}
                ))
                session.commit()

                # Heart Trigger: Conflict Detected
                # Trigger P1 NOTICE immediately
                msg_content = f"Conflict detected in Episode {episode_id}: {conflicts[0]['descriptor']}"
                self.heart.trigger_message(
                    priority="P1",
                    type="NOTICE",
                    intent="conflict_check",
                    content=msg_content,
                    episode_id=episode_id,
                    context={"conflict_rules": [c['rule_id'] for c in conflicts]}
                )

            # 8. Epidora Structural Validation (Antigravity Implementation)
            if candidate.note_thin:
                epidora_errors = self.epidora.validate(candidate.note_thin)
                if epidora_errors:
                    for error in epidora_errors:
                        # 8.1 Create Alignment Facet (0x4)
                        # Check if exists (might have multiple errors? Facet table allows unique (ep, facet_id)? 
                        # Constants say FacetID is unique per episode usually.
                        # For now, just take the first error or update.
                        
                        existing_align = session.query(Facet).filter_by(episode_id=episode_id, facet_id=FacetID.ALIGNMENT).first()
                        err_val = error['error_id']
                        
                        if existing_align:
                            existing_align.value = err_val
                        else:
                            session.add(Facet(
                                facet_uuid=f"f_{uuid.uuid4().hex[:8]}",
                                episode_id=episode_id,
                                facet_id=FacetID.ALIGNMENT,
                                value=err_val
                            ))
                        
                        # 8.2 Heart Trigger: Epidora Error
                        # Revealing Question
                        question = self.epidora.get_philosophical_feedback(err_val)
                        
                        self.heart.trigger_message(
                            priority="P2",
                            type="ASK",
                            intent="epidora_reveal",
                            content=f"Structural Insight: {question} (Detected {error['name']})",
                            episode_id=episode_id,
                            context={"epidora_error": error}
                        )
                        
                         # Log Event
                        session.add(Event(
                            event_id=f"evt_{uuid.uuid4().hex[:8]}",
                            episode_id=episode_id,
                            type="EPIDORA_MARK",
                            payload=error
                        ))
                    
                    session.commit()

            return b_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def reject(self, episode_id: str, candidate_id: str, reason: str | None = None) -> bool:
        session = self._get_session()
        try:
            candidate = self._load_candidate_for_episode(
                session, episode_id=episode_id, candidate_id=candidate_id
            )

            status = str(candidate.status or "").upper()
            if status == "ADOPTED":
                raise ValueError("Candidate status is ADOPTED")
            if status == "REJECTED":
                return False
            if status != "PENDING":
                raise ValueError(f"Candidate status is {candidate.status}")

            candidate.status = 'REJECTED'
            reason_text = str(reason or "").strip()
            
            # Log to Event Table
            event_payload = {"candidate_id": candidate_id}
            if reason_text:
                event_payload["reason"] = reason_text
            session.add(Event(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                episode_id=episode_id,
                type="REJECT",
                payload=event_payload,
            ))
            session.commit()
            
            # Log to File (Error Pattern)
            try:
                import json
                import os
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "episode_id": episode_id,
                    "candidate_id": candidate_id,
                    "backbone_bits": candidate.backbone_bits,
                    "facets": candidate.facets_json,
                    "confidence": candidate.confidence,
                    "source": candidate.proposed_by,
                    "note": candidate.note_thin,
                    "reason": reason_text,
                }
                
                os.makedirs("data", exist_ok=True)
                with open("data/error_patterns.jsonl", "a") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception as file_err:
                print(f"Warning: Failed to log error pattern: {file_err}")
            return True

        finally:
            session.close()
