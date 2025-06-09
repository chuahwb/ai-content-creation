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
} from '@/types/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

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
  // Health check
  static async healthCheck(): Promise<{ status: string }> {
    try {
      const response = await apiClient.get('/health');
      return response.data;
    } catch (error) {
      return handleApiError(error as AxiosError);
    }
  }

  // Get API status
  static async getStatus(): Promise<ApiStatusResponse> {
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
      
      // Convert form data to API request format
      const runRequest: Omit<PipelineRunRequest, 'image_reference'> = {
        mode: formData.mode,
        platform_name: formData.platform_name,
        creativity_level: formData.creativity_level,
        num_variants: formData.num_variants,
        render_text: formData.render_text,
        apply_branding: formData.apply_branding,
      };

      // Add optional fields
      if (formData.prompt) runRequest.prompt = formData.prompt;
      if (formData.task_type) runRequest.task_type = formData.task_type;
      if (formData.task_description) runRequest.task_description = formData.task_description;
      if (formData.branding_elements) runRequest.branding_elements = formData.branding_elements;

      // Add marketing goals if provided
      if (formData.marketing_audience || formData.marketing_objective || 
          formData.marketing_voice || formData.marketing_niche) {
        runRequest.marketing_goals = {
          target_audience: formData.marketing_audience,
          objective: formData.marketing_objective,
          voice: formData.marketing_voice,
          niche: formData.marketing_niche,
        };
      }

      // Add individual form fields as expected by the API
      requestData.append('mode', runRequest.mode);
      requestData.append('platform_name', runRequest.platform_name);
      requestData.append('creativity_level', runRequest.creativity_level.toString());
      requestData.append('num_variants', runRequest.num_variants.toString());
      requestData.append('render_text', runRequest.render_text.toString());
      requestData.append('apply_branding', runRequest.apply_branding.toString());

      // Add optional fields
      if (runRequest.prompt) requestData.append('prompt', runRequest.prompt);
      if (runRequest.task_type) requestData.append('task_type', runRequest.task_type);
      if (runRequest.task_description) requestData.append('task_description', runRequest.task_description);
      if (runRequest.branding_elements) requestData.append('branding_elements', runRequest.branding_elements);

      // Add marketing goals as individual fields
      if (runRequest.marketing_goals) {
        if (runRequest.marketing_goals.target_audience) {
          requestData.append('marketing_audience', runRequest.marketing_goals.target_audience);
        }
        if (runRequest.marketing_goals.objective) {
          requestData.append('marketing_objective', runRequest.marketing_goals.objective);
        }
        if (runRequest.marketing_goals.voice) {
          requestData.append('marketing_voice', runRequest.marketing_goals.voice);
        }
        if (runRequest.marketing_goals.niche) {
          requestData.append('marketing_niche', runRequest.marketing_goals.niche);
        }
      }

      // Add image file if provided
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
}

// WebSocket connection manager for real-time updates
export class WebSocketManager {
  private ws: WebSocket | null = null;
  private runId: string;
  private onMessage: (message: WebSocketMessage) => void;
  private onError: (error: Event) => void;
  private onClose: (event: CloseEvent) => void;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

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
          console.log('WebSocket connection closed:', event);
          this.onClose(event);
          
          // Attempt reconnection if not intentionally closed
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
              this.reconnectAttempts++;
              console.log(`Attempting WebSocket reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
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