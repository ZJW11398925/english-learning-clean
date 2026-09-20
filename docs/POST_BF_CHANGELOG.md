# RC2 -> Implementation Baseline V1 Changelog

## Behavioral closure

- Estimator Behavioral Baseline V1.
- Planner Behavioral Baseline V1.
- Gate Behavioral Baseline v1.1.
- Golden Scenario Baseline V1.
- Security / Privacy / Deletion Contract V1.
- Modality Scope Baseline V1.
- Local Runtime Baseline V1.

## Canonical changes

- Target × SkillModality -> Target × EvidenceModality.
- UserTurn/InputEnvelope modality -> interaction_channel.
- Added GoalModality and InteractionChannel.
- Added PlannerExecutionStatus=DEGRADED.
- Added canonical GateExecutionStatus.
- Gate continuation now uses ActiveMoment authorization.
- Local V1 uses app.db + content.db + SecretStore.
- Local V1 uses keyed mutex + runtime_epoch instead of distributed coordinator lease/heartbeat.
- TeachingLock remains durable and unique per conversation.
- Added provenance-aware deletion and minimal provider disclosure.
- Implementation order validates Learning + manual Teaching before full Relationship projection and automatic teaching.
