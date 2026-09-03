export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type Phase =
  | "awaiting_idea"
  | "awaiting_idea_refinement"
  | "planning"
  | "checking_key_insight"
  | "awaiting_plan_decision"
  | "awaiting_working_context"
  | "working"
  | "awaiting_result_record"
  | "completing"
  | "awaiting_validation_selection"
  | "awaiting_plan_revision_decision"
  | "completed"
  | "rejected"
  | "check_loop_exhausted";

export type CommandType = Command["type"];

export type ActiveRunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "timed_out"
  | "cancelled";

export interface ActiveRun {
  run_id: string;
  agent_name: string;
  status: ActiveRunStatus;
  public_message?: string | null;
}

export interface ValidationCandidate {
  candidate_id: string;
  rank: number;
  priority: "critical" | "high" | "medium" | "low";
  rationale: string;
  addresses_claims: string[];
  task: ValidationTask;
}

export interface VisibleEvidenceItem {
  title: string;
  source_type: string;
  url?: string | null;
  summary?: string | null;
  support?: string | null;
  selected: boolean;
}

export interface StageProgress {
  headline: string;
  detail?: string | null;
  check_round: number;
  max_check_rounds: number;
  candidate_count: number;
  idea_type?: string | null;
  idea_action?: string | null;
  idea_reason?: string | null;
  normalized_idea?: string | null;
  plan_question?: string | null;
  key_insight_title?: string | null;
  last_check_score?: number | null;
  last_check_passed?: boolean | null;
}

export interface PublicActivityItem {
  sequence: number;
  type: string;
  summary: string;
}

export interface UploadedDocumentView {
  document_id: string;
  original_name: string;
  media_type?: string;
  size_bytes: number;
  status: string;
  error_message?: string | null;
}

export interface PlanCandidateView {
  candidate_id: string;
  disposition: string;
  focus_hint?: string;
  check_round?: number;
  research_question?: string | null;
  key_insight_title?: string | null;
  key_insight_content?: string | null;
}

export interface CurrentTaskView {
  task_id: string;
  task_kind: "main" | "validation" | string;
  origin: string;
  status: string;
  current_experiment?: string | null;
  expected_result?: string | null;
  validation_task?: ValidationTask | null;
}

export interface WorkingTurnView {
  question?: string;
  action: string;
  reply: string;
  reason?: string | null;
  occurred_at?: string | null;
}

export interface PendingWorkingClarification {
  original_question: string;
  clarify_reply: string;
  clarify_reason?: string | null;
}

export interface WritingGuidance {
  suggested_structure: string[];
  key_results_to_report: string[];
  key_discussion_points: string[];
  limitations: string[];
}

export interface ProjectView {
  project_id: string;
  title: string;
  domain: string;
  version: number;
  phase: Phase;
  is_demo: boolean;
  allowed_commands: CommandType[];
  last_event_sequence?: number;
  active_run?: ActiveRun | null;
  validation_candidates?: ValidationCandidate[];
  visible_evidence?: VisibleEvidenceItem[];
  stage_progress?: StageProgress | null;
  recent_activity?: PublicActivityItem[];
  plan_candidates?: PlanCandidateView[];
  current_task?: CurrentTaskView | null;
  writing_guidance?: WritingGuidance | null;
  revision_reason?: string | null;
  working_turns?: WorkingTurnView[];
  pending_clarification?: PendingWorkingClarification | null;
}

export interface InitialInput {
  original_idea: string;
  domain: string;
  time_limit?: string | null;
  available_resources?: string[];
  unavailable_resources?: string[];
  other_constraints?: string[];
}

export interface KeyInsight {
  title: string;
  content: string;
  rationale: string;
  evidence?: JsonValue[];
}

export interface ExperimentResult {
  execution_status: "completed" | "failed" | "cancelled";
  impact: "supports" | "neutral" | "contradicts" | "invalidates";
  failure_reason?: string | null;
  actual_result: string;
  conclusion: string;
  evidence_files?: string[];
}

export interface MainExperimentResult extends ExperimentResult {
  objective: string;
  method: string;
  expected_result?: string | null;
}

export interface ValidationTask {
  paradigm: string;
  validation_type: string;
  name: string;
  purpose: string;
  method: string;
  expected_result?: string | null;
}

export interface ValidationResult extends ExperimentResult {
  task: ValidationTask;
  is_success: boolean;
}

export interface ValidationSelection {
  selected_candidate_ids: string[];
  skipped_candidate_ids: string[];
  finish_without_more_validation: boolean;
  user_reason?: string | null;
}

interface CommandBase {
  command_id: string;
  expected_version: number;
}

export interface SubmitIdeaCommand extends CommandBase {
  type: "submit_idea";
  idea: InitialInput;
}

export interface SubmitRefinementCommand extends CommandBase {
  type: "submit_refinement";
  refinement: string;
}

export interface RunPlanCommand extends CommandBase {
  type: "run_plan";
  mode?: "low" | "mid" | "high";
}

export interface RunCheckCommand extends CommandBase {
  type: "run_check";
  candidate_id?: string | null;
}

export type PlanDecision =
  | {
      decision: "accept" | "request_revision";
      user_reason?: string | null;
      overridden_key_insight?: null;
    }
  | {
      decision: "override";
      user_reason?: string | null;
      overridden_key_insight: KeyInsight;
    }
  | { decision: "continue_imperfect"; user_reason: string };

export interface DecidePlanCommand extends CommandBase {
  type: "decide_plan";
  decision: PlanDecision;
  candidate_id?: string | null;
}

export interface SendWorkingMessageCommand extends CommandBase {
  type: "send_working_message";
  question: string;
}

export interface SubmitWorkingClarificationCommand extends CommandBase {
  type: "submit_working_clarification";
  clarification: string;
}

export interface ResumeWorkingCommand extends CommandBase {
  type: "resume_working";
}

export interface FinishWorkingCommand extends CommandBase {
  type: "finish_working";
}

export interface RecordMainResultCommand extends CommandBase {
  type: "record_main_result";
  result: MainExperimentResult;
}

export interface RecordValidationResultCommand extends CommandBase {
  type: "record_validation_result";
  result: ValidationResult;
}

export interface RunCompleteCommand extends CommandBase {
  type: "run_complete";
  completion_status?: boolean;
}

export interface SelectValidationsCommand extends CommandBase {
  type: "select_validations";
  selection: ValidationSelection;
}

export interface DecidePlanRevisionCommand extends CommandBase {
  type: "decide_plan_revision";
  decision: "revise" | "continue_with_warning" | "end_project";
  user_reason?: string | null;
}

export interface CancelRunCommand extends CommandBase {
  type: "cancel_run";
  run_id?: string | null;
}

export interface RestartResearchCommand extends CommandBase {
  type: "restart_research";
  confirm_restart: true;
  idea: InitialInput;
}

export interface ArchiveProjectCommand extends CommandBase {
  type: "archive_project";
}

export type Command =
  | SubmitIdeaCommand
  | SubmitRefinementCommand
  | RunPlanCommand
  | RunCheckCommand
  | DecidePlanCommand
  | SendWorkingMessageCommand
  | SubmitWorkingClarificationCommand
  | ResumeWorkingCommand
  | FinishWorkingCommand
  | RecordMainResultCommand
  | RecordValidationResultCommand
  | RunCompleteCommand
  | SelectValidationsCommand
  | DecidePlanRevisionCommand
  | CancelRunCommand
  | RestartResearchCommand
  | ArchiveProjectCommand;

export interface AgentCommandReceipt {
  command_id: string;
  run_id: string;
}

export type CommandResponse = AgentCommandReceipt | ProjectView;

export interface ResearchJournalProject {
  project_id: string;
  title: string;
  domain: string;
}

export interface ResearchJournal {
  project: ResearchJournalProject;
  generated_at?: string;
  initial_input?: {
    original_idea?: string;
    domain?: string;
    time_limit?: string | null;
    available_resources?: string[];
    other_constraints?: string[];
  } | null;
  idea_review?: {
    normalized_idea?: string;
    reason?: string;
    action?: string;
    idea_type?: string;
  } | null;
  literature?: Array<{
    title?: string;
    summary?: string;
    url?: string | null;
    year?: number | null;
    provider?: string | null;
  }>;
  plans?: Array<{
    response_to_user?: string;
    plan?: {
      research_question?: string;
      key_insight?: { title?: string; content?: string };
    };
  }>;
  experiment_tasks?: Array<{
    task_kind?: string;
    experiment_info?: { current_experiment?: string | null };
  }>;
  main_result?: {
    objective?: string;
    method?: string;
    expected_result?: string | null;
    actual_result?: string;
    conclusion?: string;
    impact?: string;
  } | null;
  validation_results?: Array<{
    actual_result?: string;
    conclusion?: string;
    is_success?: boolean;
    task?: { name?: string };
  }>;
  writing_guidance?: WritingGuidance | null;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
  details: Record<string, JsonValue>;
}

export interface ApiErrorEnvelope {
  error: ApiErrorDetail;
}
