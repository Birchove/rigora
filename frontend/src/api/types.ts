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

export interface ProjectView {
  project_id: string;
  title: string;
  domain: string;
  version: number;
  phase: Phase;
  is_demo: boolean;
  allowed_commands: CommandType[];
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

export interface ResumeWorkingCommand extends CommandBase {
  type: "resume_working";
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
  | ResumeWorkingCommand
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

export interface ApiErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
  details: Record<string, JsonValue>;
}

export interface ApiErrorEnvelope {
  error: ApiErrorDetail;
}
