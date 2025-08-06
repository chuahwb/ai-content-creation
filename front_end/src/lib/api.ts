import axios, { AxiosError } from 'axios';
import {
  PipelineFormData,
  PipelineRunRequest,
  PipelineRunResponse,
  PipelineRunDetail,
  RunListResponse,
  ConfigResponse,
  ApiStatusResponse,
  WebSocketMessage,
  StageProgressUpdate,
  Platform,
  CaptionResponse,
  CaptionRegenerateRequest,
  CaptionModelsResponse,
  CaptionModelOption,
  CaptionRequest,
  CaptionSettings,
  BrandPresetListResponse,
  BrandPresetResponse,
  BrandPresetCreateRequest,
  BrandPresetUpdateRequest,
  SavePresetFromResultRequest,
} from '@/types/api';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
const WS_BASE_URL = (process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000').replace(/\/+$/, '');

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 120000, // 2 minutes for long-running operations
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true', // Bypass ngrok browser warning
  },
});

// Error handling
export class ApiError extends Error {
  constructor(public status: number, message: string, public response?: any) {
    super(message);
    this.name = 'ApiError';
  }
}

// Helper function to handle API errors
const handleApiError = (error: AxiosError): never => {
  if (error.response) {
    const status = error.response.status;
    const responseData = error.response.data as any;
    const message = responseData?.detail || error.message;
    throw new ApiError(status, message, error.response.data);
  } else if (error.request) {
    throw new ApiError(0, 'Network error - unable to reach the server');
  } else {
    throw new ApiError(0, error.message);
  }
};

// Main API class
export class PipelineAPI {


  // Get status of API service
  static async getApiStatus(): Promise<ApiStatusResponse> {
    try {
      const response = await apiClient.get('/status');
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get configuration (platforms, task types)
  static async getConfig(): Promise<ConfigResponse> {
    try {
      const [platformsResponse, taskTypesResponse] = await Promise.all([
        apiClient.get('/config/platforms'),
        apiClient.get('/config/task-types'),
      ]);
      
      return {
        platforms: platformsResponse.data,
        task_types: taskTypesResponse.data,
      };
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Submit new pipeline run
  static async submitRun(formData: PipelineFormData): Promise<PipelineRunResponse> {
    try {
      const requestData = new FormData();

      // Append all simple key-value pairs from formData
      requestData.append('mode', formData.mode);
      requestData.append('platform_name', formData.platform_name);
      requestData.append('creativity_level', formData.creativity_level.toString());
      requestData.append('num_variants', formData.num_variants.toString());
      requestData.append('render_text', formData.render_text.toString());
      requestData.append('apply_branding', formData.apply_branding.toString());

      if (formData.prompt) requestData.append('prompt', formData.prompt);
      if (formData.task_type) requestData.append('task_type', formData.task_type);
      if (formData.task_description) requestData.append('task_description', formData.task_description);
      if (formData.language) requestData.append('language', formData.language);

      // Append marketing goals
      if (formData.marketing_audience) requestData.append('marketing_audience', formData.marketing_audience);
      if (formData.marketing_objective) requestData.append('marketing_objective', formData.marketing_objective);
      if (formData.marketing_voice) requestData.append('marketing_voice', formData.marketing_voice);
      if (formData.marketing_niche) requestData.append('marketing_niche', formData.marketing_niche);

      // Append preset data
      if (formData.preset_id) requestData.append('preset_id', formData.preset_id);
      if (formData.preset_type) requestData.append('preset_type', formData.preset_type);
      if (formData.template_overrides) requestData.append('template_overrides', JSON.stringify(formData.template_overrides));
      if (formData.adaptation_prompt) requestData.append('adaptation_prompt', formData.adaptation_prompt);

      // Append brand_kit as a JSON string
      if (formData.brand_kit) {
        requestData.append('brand_kit', JSON.stringify(formData.brand_kit));
      }

      // Append image file if provided
      if (formData.image_file) {
        requestData.append('image_file', formData.image_file);
        if (formData.image_instruction) {
          requestData.append('image_instruction', formData.image_instruction);
        }
      }

      const response = await apiClient.post('/runs', requestData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get list of runs
  static async getRuns(
    page: number = 1, 
    pageSize: number = 20, 
    status?: string
  ): Promise<RunListResponse> {
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });
      
      if (status) params.append('status', status);

      const response = await apiClient.get(`/runs/?${params}`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get specific run details
  static async getRun(runId: string): Promise<PipelineRunDetail> {
    try {
      const response = await apiClient.get(`/runs/${runId}`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get pipeline results (including generated images)
  static async getResults(runId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/runs/${runId}/results`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Cancel a run
  static async cancelRun(runId: string): Promise<{ message: string }> {
    try {
      const response = await apiClient.post(`/runs/${runId}/cancel`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Download file (for generated images)
  static getFileUrl(runId: string, filename: string): string {
    return `${API_BASE_URL}/api/v1/files/${runId}/${filename}`;
  }

  // Get image as blob URL (works with ngrok by including headers)
  static async getImageBlobUrl(runId: string, filename: string): Promise<string> {
    try {
      const response = await apiClient.get(`/files/${runId}/${filename}`, {
        responseType: 'blob',
      });
      return URL.createObjectURL(response.data);
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Download file as blob
  static async downloadFile(runId: string, filename: string): Promise<Blob> {
    try {
      const response = await apiClient.get(`/files/${runId}/${filename}`, {
        responseType: 'blob',
      });
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get refinements for a run
  static async getRefinements(runId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/runs/${runId}/refinements`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get refinement details for a specific job
  static async getRefinementDetails(jobId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/refinements/${jobId}/details`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Submit refinement request
  static async submitRefinement(runId: string, formData: FormData): Promise<any> {
    try {
      const response = await apiClient.post(`/runs/${runId}/refine`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Caption generation methods
  static async getCaptionModels(): Promise<CaptionModelsResponse> {
    try {
      const response = await apiClient.get('/config/caption-models');
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async generateCaption(
    runId: string, 
    imageId: string, 
    request: CaptionRequest
  ): Promise<CaptionResponse> {
    try {
      const response = await apiClient.post(`/runs/${runId}/images/${imageId}/caption`, request);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async regenerateCaption(
    runId: string, 
    imageId: string, 
    version: number,
    request: CaptionRegenerateRequest
  ): Promise<CaptionResponse> {
    try {
      const response = await apiClient.post(`/runs/${runId}/images/${imageId}/caption/${version}/regenerate`, request);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async getCaptions(runId: string, imageId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/runs/${runId}/images/${imageId}/captions`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Brand Preset API functions
  static async getBrandPresets(presetType?: 'INPUT_TEMPLATE' | 'STYLE_RECIPE'): Promise<BrandPresetListResponse> {
    try {
      const params = presetType ? { preset_type: presetType } : {};
      const response = await apiClient.get('/brand-presets', { params });
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async getBrandPreset(presetId: string): Promise<BrandPresetResponse> {
    try {
      const response = await apiClient.get(`/brand-presets/${presetId}`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async createBrandPreset(data: BrandPresetCreateRequest): Promise<BrandPresetResponse> {
    try {
      const response = await apiClient.post('/brand-presets', data);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async updateBrandPreset(presetId: string, data: BrandPresetUpdateRequest): Promise<BrandPresetResponse> {
    try {
      const response = await apiClient.put(`/brand-presets/${presetId}`, data);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async deleteBrandPreset(presetId: string): Promise<{ message: string }> {
    try {
      const response = await apiClient.delete(`/brand-presets/${presetId}`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  static async savePresetFromResult(runId: string, data: SavePresetFromResultRequest): Promise<BrandPresetResponse> {
    try {
      const response = await apiClient.post(`/runs/${runId}/save-as-preset`, data);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Assess noise for a refinement
  static async assessRefinementNoise(jobId: string): Promise<{ message: string; job_id: string }> {
    try {
      const response = await apiClient.post(`/refinements/${jobId}/assess-noise`);
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }
}

// WebSocket connection manager for real-time updates
export class WebSocketManager {
  private ws: WebSocket | null = null;
  private runId: string;
  private onMessage: (message: WebSocketMessage) => void;
  private onError: (error: Event) => void;
  private onClose: (event: CloseEvent) => void;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private reconnectDelay = 2000;

  constructor(
    runId: string,
    onMessage: (message: WebSocketMessage) => void,
    onError: (error: Event) => void = () => {},
    onClose: (event: CloseEvent) => void = () => {}
  ) {
    this.runId = runId;
    this.onMessage = onMessage;
    this.onError = onError;
    this.onClose = onClose;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = `${WS_BASE_URL}/api/v1/ws/${this.runId}`;
      
      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log(`WebSocket connected for run ${this.runId}`);
          this.reconnectAttempts = 0;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.onMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.onError(error);
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log(`WebSocket connection closed for run ${this.runId}:`, event.code, event.reason);
          this.onClose(event);
          
          // Only attempt reconnection for certain error codes (not for intentional closures)
          const shouldReconnect = event.code !== 1000 && // Normal closure
                                 event.code !== 1001 && // Going away
                                 event.code !== 1005 && // No status code
                                 this.reconnectAttempts < this.maxReconnectAttempts;
          
          if (shouldReconnect) {
            setTimeout(() => {
              this.reconnectAttempts++;
              console.log(`Attempting WebSocket reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts} for run ${this.runId}`);
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
          } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log(`Max reconnection attempts reached for run ${this.runId}`);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  send(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }
}

export default PipelineAPI; 