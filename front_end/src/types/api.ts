// API Types matching FastAPI backend schemas

export type RunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type StageStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

export interface Platform {
  name: string;
  details: {
    width: number;
    height: number;
    aspect_ratio: string;
  };
}

export interface ImageReferenceInput {
  filename: string;
  content_type: string;
  size_bytes: number;
  instruction?: string;
}

export interface MarketingGoalsInput {
  target_audience?: string;
  objective?: string;
  voice?: string;
  niche?: string;
}

export interface PipelineRunRequest {
  mode: 'easy_mode' | 'custom_mode' | 'task_specific_mode';
  platform_name: string;
  creativity_level: 1 | 2 | 3;
  prompt?: string;
  task_type?: string;
  task_description?: string;
  branding_elements?: string;
  image_reference?: ImageReferenceInput;
  render_text: boolean;
  apply_branding: boolean;
  marketing_goals?: MarketingGoalsInput;
}

export interface StageProgressUpdate {
  stage_name: string;
  stage_order: number;
  status: StageStatus;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  message: string;
  output_data?: Record<string, any>;
  error_message?: string;
}

export interface PipelineRunResponse {
  id: string;
  status: RunStatus;
  mode: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  total_duration_seconds?: number;
  total_cost_usd?: number;
  error_message?: string;
  output_directory?: string;
  metadata_file_path?: string;
}

export interface PipelineRunDetail extends PipelineRunResponse {
  stages: StageProgressUpdate[];
  
  // Form input data
  platform_name?: string;
  task_type?: string;
  prompt?: string;
  creativity_level: number;
  render_text: boolean;
  apply_branding: boolean;
  has_image_reference: boolean;
  image_filename?: string;
  image_instruction?: string;
  branding_elements?: string;
  task_description?: string;
  marketing_audience?: string;
  marketing_objective?: string;
  marketing_voice?: string;
  marketing_niche?: string;
}

export interface GeneratedImageResult {
  strategy_index: number;
  status: string;
  image_path?: string;
  error_message?: string;
  prompt_used?: string;
}

export interface PipelineResults {
  run_id: string;
  status: RunStatus;
  image_analysis?: Record<string, any>;
  marketing_strategies?: Record<string, any>[];
  style_guidance?: Record<string, any>[];
  visual_concepts?: Record<string, any>[];
  final_prompts?: Record<string, any>[];
  generated_images?: GeneratedImageResult[];
  total_cost_usd?: number;
  total_duration_seconds?: number;
  stage_costs?: Record<string, any>[];
}

export interface RunListItem {
  id: string;
  status: RunStatus;
  mode: string;
  platform_name?: string;
  task_type?: string;
  created_at: string;
  completed_at?: string;
  total_cost_usd?: number;
}

export interface RunListResponse {
  runs: RunListItem[];
  total: number;
  page: number;
  page_size: number;
}

// WebSocket message types
export interface WebSocketMessage {
  type: 'stage_update' | 'run_complete' | 'run_error' | 'ping';
  run_id: string;
  timestamp: string;
  data: Record<string, any>;
}

// Form data types
export interface PipelineFormData {
  mode: 'easy_mode' | 'custom_mode' | 'task_specific_mode';
  platform_name: string;
  creativity_level: 1 | 2 | 3;
  prompt?: string;
  task_type?: string;
  task_description?: string;
  branding_elements?: string;
  image_file?: File;
  image_instruction?: string;
  render_text: boolean;
  apply_branding: boolean;
  marketing_audience?: string;
  marketing_objective?: string;
  marketing_voice?: string;
  marketing_niche?: string;
}

// Configuration types
export interface ConfigResponse {
  platforms?: Platform[];
  task_types?: string[];
}

export interface ApiStatusResponse {
  status: string;
  active_runs: number;
  active_run_ids: string[];
} 