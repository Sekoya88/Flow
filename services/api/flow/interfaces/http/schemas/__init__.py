"""HTTP schemas package — central re-export hub for backward compatibility."""

from __future__ import annotations

from flow.interfaces.http.schemas.ab_tests import ABTestCreateIn, ABTestOut, ABTestResultItem
from flow.interfaces.http.schemas.agent_versions import (
    AgentVersionListOut,
    AgentVersionOut,
    SnapshotCreateIn,
    VersionDiffOut,
    VersionRestoreOut,
)
from flow.interfaces.http.schemas.agents import (
    AgentCreateIn,
    AgentCreateOut,
    AgentListOut,
    AgentOut,
    AgentPatchIn,
    AgentPatchOut,
    AgentStatsOut,
    AgentToolsPatchIn,
    ConfidenceTrendItem,
    ExecuteIn,
    ExecuteOut,
    VibeAgentOut,
    VibeIn,
)
from flow.interfaces.http.schemas.analytics import AnalyticsBatchIn, AnalyticsEventIn, AnalyticsEventOut
from flow.interfaces.http.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn, TokenOut
from flow.interfaces.http.schemas.executions import (
    ApproveOut,
    ExecutionDetailOut,
    ExecutionEventOut,
    ExecutionItemOut,
    StreamTokenOut,
    ThreadOut,
)
from flow.interfaces.http.schemas.feedback import FeedbackIn, FeedbackOut
from flow.interfaces.http.schemas.golden_sets import (
    EvaluationResultOut,
    GoldenSetCreateIn,
    GoldenSetEvaluateIn,
    GoldenSetItemCreateIn,
    GoldenSetItemListOut,
    GoldenSetItemOut,
    GoldenSetListOut,
    GoldenSetOut,
)
from flow.interfaces.http.schemas.graph import PositionUpdateIn
from flow.interfaces.http.schemas.kg import (
    KGEdgeOut,
    KGGraphOut,
    KGIngestObsidianIn,
    KGNodeDetailOut,
    KGNodeOut,
    KGQueryIn,
    KGSyncIn,
    SkillNodeDetail,
)
from flow.interfaces.http.schemas.knowledge import (
    ChunkListOut,
    ChunkOut,
    KnowledgeCreateIn,
    KnowledgeCreateOut,
    KnowledgeListOut,
    KnowledgeSourceOut,
    KnowledgeUploadOut,
)
from flow.interfaces.http.schemas.memory import (
    DeletedOut,
    EpisodicMemoryOut,
    MemoryCreateIn,
    MemoryCreateOut,
    SemanticMemoryOut,
    TieredMemoriesOut,
)
from flow.interfaces.http.schemas.personas import (
    PersonaOut,
    PersonaQuestionnaireIn,
    PersonaRegenerateIn,
    PersonaResponseOut,
    PersonaSaveIn,
    QuestionnaireAnswer,
)
from flow.interfaces.http.schemas.preferences import (
    OnboardingAnswerIn,
    OnboardingAnswersIn,
    OnboardingOut,
    PreferenceCreateIn,
    PreferenceCreateOut,
    PreferenceListOut,
    PreferenceOut,
    PreferencePatchIn,
    PreferenceUpsertIn,
)
from flow.interfaces.http.schemas.proposals import ProposalActionIn, ProposalActionOut, ProposalListOut, ProposalOut
from flow.interfaces.http.schemas.schedules import (
    CronJobListOut,
    CronJobOut,
    ScheduleCreateIn,
    ScheduleListOut,
    ScheduleOut,
    ScheduleToggleIn,
)
from flow.interfaces.http.schemas.skills import (
    DeactivateOut,
    SkillActivateOut,
    SkillCatalogItemOut,
    SkillCatalogOut,
    SkillCreateIn,
    SkillCreateOut,
    SkillHistoryOut,
    SkillImproveOut,
    SkillListOut,
    SkillOut,
    SkillTestIn,
    SkillUsageDataPoint,
    SkillUsageOut,
    SkillVersionOut,
    SkillVibeCreateIn,
    SkillVibeModifyIn,
    TrainingConfigIn,
    TrainingEpochOut,
    TrainingRunDetailOut,
    TrainingRunOut,
    TrainingRunsOut,
    TrainingStartOut,
)

__all__ = [
    # auth
    "RegisterIn",
    "LoginIn",
    "TokenOut",
    "ChangePasswordIn",
    # agents
    "AgentCreateIn",
    "AgentToolsPatchIn",
    "AgentPatchIn",
    "VibeIn",
    "ExecuteIn",
    "AgentCreateOut",
    "AgentOut",
    "AgentListOut",
    "AgentPatchOut",
    "VibeAgentOut",
    "ExecuteOut",
    "ConfidenceTrendItem",
    "AgentStatsOut",
    # analytics
    "AnalyticsEventIn",
    "AnalyticsBatchIn",
    "AnalyticsEventOut",
    # executions
    "ExecutionItemOut",
    "ExecutionEventOut",
    "ExecutionDetailOut",
    "ThreadOut",
    "StreamTokenOut",
    "ApproveOut",
    # feedback
    "FeedbackIn",
    "FeedbackOut",
    # knowledge
    "KnowledgeCreateIn",
    "KnowledgeCreateOut",
    "KnowledgeUploadOut",
    "ChunkOut",
    "ChunkListOut",
    "KnowledgeSourceOut",
    "KnowledgeListOut",
    # memory
    "MemoryCreateIn",
    "MemoryCreateOut",
    "EpisodicMemoryOut",
    "SemanticMemoryOut",
    "TieredMemoriesOut",
    "DeletedOut",
    # personas
    "PersonaSaveIn",
    "PersonaRegenerateIn",
    "QuestionnaireAnswer",
    "PersonaQuestionnaireIn",
    "PersonaOut",
    "PersonaResponseOut",
    # preferences
    "PreferenceUpsertIn",
    "PreferenceCreateIn",
    "PreferencePatchIn",
    "OnboardingAnswerIn",
    "OnboardingAnswersIn",
    "PreferenceOut",
    "PreferenceListOut",
    "PreferenceCreateOut",
    "OnboardingOut",
    # proposals
    "ProposalActionIn",
    "ProposalOut",
    "ProposalListOut",
    "ProposalActionOut",
    # skills
    "SkillCreateIn",
    "SkillTestIn",
    "SkillOut",
    "SkillListOut",
    "SkillCreateOut",
    "SkillVersionOut",
    "SkillHistoryOut",
    "SkillActivateOut",
    "SkillImproveOut",
    "SkillUsageDataPoint",
    "SkillUsageOut",
    "SkillCatalogItemOut",
    "SkillCatalogOut",
    "DeactivateOut",
    "SkillVibeCreateIn",
    "SkillVibeModifyIn",
    "TrainingConfigIn",
    "TrainingStartOut",
    "TrainingEpochOut",
    "TrainingRunOut",
    "TrainingRunsOut",
    "TrainingRunDetailOut",
    # ab_tests
    "ABTestCreateIn",
    "ABTestResultItem",
    "ABTestOut",
    # agent_versions
    "SnapshotCreateIn",
    "AgentVersionOut",
    "AgentVersionListOut",
    "VersionDiffOut",
    "VersionRestoreOut",
    # golden_sets
    "GoldenSetCreateIn",
    "GoldenSetItemCreateIn",
    "GoldenSetEvaluateIn",
    "GoldenSetOut",
    "GoldenSetListOut",
    "GoldenSetItemOut",
    "GoldenSetItemListOut",
    "EvaluationResultOut",
    # schedules
    "ScheduleCreateIn",
    "ScheduleToggleIn",
    "ScheduleOut",
    "ScheduleListOut",
    "CronJobOut",
    "CronJobListOut",
    # graph
    "PositionUpdateIn",
    # kg
    "KGNodeOut",
    "KGEdgeOut",
    "KGGraphOut",
    "SkillNodeDetail",
    "KGNodeDetailOut",
    "KGIngestObsidianIn",
    "KGSyncIn",
    "KGQueryIn",
]
