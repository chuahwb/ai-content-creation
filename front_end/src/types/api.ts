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

// Brand Kit interface for unified brand management
export interface BrandKitInput {
  colors?: string[];
  brand_voice_description?: string;
  logo_file_base64?: string;
  // Runtime fields - populated during processing
  saved_logo_path_in_run_dir?: string;
  logo_analysis?: Record<string, any>;
}

// Style Recipe interface for structured creative output
export interface StyleRecipeData {
  visual_concept: Record<string, any>;
  strategy: Record<string, any>;
  style_guidance: Record<string, any>;
  final_prompt: string;
  generation_seed?: string;
  model_parameters?: Record<string, any>;
}

// Pipeline Input Snapshot interface
export interface PipelineInputSnapshot {
  mode?: string;
  prompt?: string;
  creativity_level: number;
  platform_name: string;
  num_variants: number;
  task_type?: string;
  task_description?: string;
  image_instruction?: string;
  brand_kit?: BrandKitInput;
  marketing_audience?: string;
  marketing_objective?: string;
  marketing_voice?: string;
  marketing_niche?: string;
  render_text: boolean;
  apply_branding: boolean;
  language: string;
}

export interface PipelineRunRequest {
  mode: 'easy_mode' | 'custom_mode' | 'task_specific_mode';
  platform_name: string;
  creativity_level: 1 | 2 | 3;
  num_variants: number;
  prompt?: string;
  task_type?: string;
  task_description?: string;
  image_reference?: ImageReferenceInput;
  render_text: boolean;
  apply_branding: boolean;
  marketing_goals?: MarketingGoalsInput;
  language?: string;
  preset_id?: string;
  preset_type?: PresetType;
  overrides?: Record<string, any>;
  // Brand kit data (UPDATED: unified brand kit structure)
  brand_kit?: BrandKitInput;
}

export interface StageProgressUpdate {
  stage_name: string;
  stage_order: number;
  status: StageStatus;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  message: string;
  output_data?: Record<string, any> & {
    // NEW: Assessment stage specific output
    image_assessments?: ImageAssessmentData[];
  };
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
  task_description?: string;
  marketing_audience?: string;
  marketing_objective?: string;
  marketing_voice?: string;
  marketing_niche?: string;
  language?: string;
  
  // Brand Kit data (UPDATED: unified brand kit structure)
  brand_kit?: BrandKitInput;
}

// NEW: Assessment data structure
export interface ImageAssessmentData {
  image_index: number;
  image_path: string;
  assessment_scores: {
    concept_adherence: number;
    technical_quality: number;
    subject_preservation?: number;
    text_rendering_quality?: number;
  };
  assessment_justification: {
    concept_adherence: string;
    technical_quality: string;
    subject_preservation?: string;
    text_rendering_quality?: string;
  };
  general_score: number;
  needs_subject_repair: boolean;
  needs_regeneration: boolean;
  needs_text_repair: boolean;
  consistency_metrics?: {
    clip_similarity?: number;
    color_histogram_similarity?: number;
    color_palette_match?: number;
    overall_consistency_score?: number;
    detailed_metrics?: Record<string, any>;
  };
  _meta?: {
    tokens_used: number;
    model: string;
    fallback?: boolean;
  };
}

export interface GeneratedImageResult {
  strategy_index: number;
  status: string;
  image_path?: string;
  error_message?: string;
  prompt_used?: string;
  // NEW: Assessment data
  assessment?: ImageAssessmentData;
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
  // NEW: Image assessments
  image_assessments?: ImageAssessmentData[];
  total_cost_usd?: number;
  total_duration_seconds?: number;
  stage_costs?: Record<string, any>[];
}

// Caption-related interfaces
export interface CaptionSettings {
  tone?: string;
  call_to_action?: string;
  include_emojis?: boolean;
  hashtag_strategy?: string;
  // New fields for mode tracking
  generation_mode?: string;
  processing_mode?: string;
}

export interface CaptionModelOption {
  id: string;
  name: string;
  description: string;
  strengths: string[];
  best_for: string;
  latency: string;
  creativity: string;
}

export interface CaptionModelsResponse {
  models: CaptionModelOption[];
  default_model_id: string;
}

export interface CaptionRequest {
  settings?: CaptionSettings;
  model_id?: string;
}

export interface CaptionRegenerateRequest {
  settings?: CaptionSettings;
  writer_only?: boolean;
  model_id?: string;
}

export interface CaptionUsageComponent {
  tokens: {
    prompt: number;
    completion: number;
    cached: number;
  };
  cost: number;
  latency: number;
}

export interface CaptionUsage {
  total_cost_usd?: number;
  total_latency_seconds?: number;
  model_id?: string;
  analyst?: CaptionUsageComponent;
  writer?: CaptionUsageComponent;
}

export interface CaptionResult {
  version: number;
  text: string;
  settings_used: CaptionSettings;
  brief_used?: Record<string, any>;
  created_at: string;
  model_id?: string;
  usage_summary?: CaptionUsage;
}

export interface CaptionResponse {
  message: string;
  task_id: string;
  status: string;
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
  type: 'stage_update' | 'run_complete' | 'run_error' | 'ping' | 'caption_update' | 'caption_complete' | 'caption_error';
  run_id: string;
  timestamp: string;
  data: Record<string, any>;
}

// Form data types
export interface PipelineFormData {
  mode: 'easy_mode' | 'custom_mode' | 'task_specific_mode';
  platform_name: string;
  creativity_level: 1 | 2 | 3;
  num_variants: number;
  prompt?: string;
  task_type?: string;
  task_description?: string;
  brand_kit?: BrandKitInput;
  image_file?: File;
  image_instruction?: string;
  render_text: boolean;
  apply_branding: boolean;
  marketing_audience?: string;
  marketing_objective?: string;
  marketing_voice?: string;
  marketing_niche?: string;
  language?: string;
  // Brand preset support
  preset_id?: string;
  preset_type?: PresetType; // To distinguish between style recipes and templates
  overrides?: Record<string, any>;
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

// Brand Preset types
export type PresetType = 'INPUT_TEMPLATE' | 'STYLE_RECIPE';

export interface BrandPresetCreateRequest {
  name: string;
  preset_type: PresetType;
  brand_kit?: BrandKitInput;
  input_snapshot?: PipelineInputSnapshot;
  style_recipe?: StyleRecipeData;
  model_id: string;
  pipeline_version: string;
}

export interface BrandPresetUpdateRequest {
  name?: string;
  version: number;
  brand_kit?: BrandKitInput;
}

export interface BrandPresetResponse {
  id: string;
  name: string;
  preset_type: PresetType;
  version: number;
  model_id: string;
  pipeline_version: string;
  usage_count: number;
  created_at: string;
  last_used_at?: string;
  brand_kit?: BrandKitInput;
  input_snapshot?: PipelineInputSnapshot;
  style_recipe?: StyleRecipeData;
}

export interface BrandPresetListResponse {
  presets: BrandPresetResponse[];
  total: number;
}

export interface SavePresetFromResultRequest {
  name: string;
  generation_index: number;
  brand_kit?: BrandKitInput;
}

export interface BrandPreset {
  id: string;
  name: string;
  preset_type: PresetType;
  version: number;
  model_id: string;
  pipeline_version: string;
  usage_count: number;
  created_at: string;
  last_used_at?: string;
  brand_kit?: BrandKitInput;
  input_snapshot?: PipelineInputSnapshot;
  style_recipe?: StyleRecipeData;
} 