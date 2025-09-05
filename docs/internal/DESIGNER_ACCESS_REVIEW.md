# Designer Access Review and Recommendations

This document outlines the trade secrets within the application and proposes strategies to protect them while allowing a UI/UX designer to test the platform.

## 1. Identified Trade Secrets

The primary trade secret is the composition and inner workings of the content generation pipeline. Exposing the specifics of our pipeline could reveal our unique process and competitive advantage. The following elements have been identified as sensitive:

- **Pipeline Stages**: The names and order of the stages in our processing pipeline are proprietary. This includes stages like `Strategy`, `PromptAssembly`, `StyleAdaptation`, `ImageGeneration`, and `Caption`.
- **Real-time Progress Updates**: The detailed, real-time progress updates visible on the `RunResults` page expose the sequence and duration of each pipeline stage.
- **Stage-specific Details**: Any logs, metrics, or parameters associated with individual stages that might be visible in the UI or accessible through the browser's developer tools.
- **Underlying Models and Techniques**: While not always directly visible, any UI text or metadata that hints at the specific AI models or proprietary algorithms used is a trade secret.

These elements are most prominently displayed in the `RunResults` component.

## 2. Recommendations for Protecting Trade Secrets

To allow the designer to evaluate the user experience without exposing our intellectual property, I recommend implementing a **"Presentation Mode"** or **"Guest Mode"**. This mode would be enabled for specific users (like the designer) and would mask the sensitive details of the pipeline.

### Implementation Strategy:

1.  **Environment Variable Configuration**:
    *   Added `PRESENTATION_MODE` environment variable to control the feature.
    *   This is set in the `.env` file and can be easily toggled for different environments.
    *   More developer-friendly than API endpoints for this type of configuration.

2.  **Selective Masking Implementation**:
    *   **Real-time WebSocket Updates**: The WebSocket endpoint in `churns/api/websocket.py` obfuscates stage names and progress updates when `PRESENTATION_MODE=true`. This protects trade secrets during live pipeline execution.
    *   **RunResults Page - Selective Masking**: The detailed run results API endpoint (`/api/v1/runs/{run_id}`) applies masking to pipeline progress (stage names, messages) but preserves stage outputs and error messages for developers.
    *   **Developer-Friendly Balance**: Pipeline progress shows generic "Step X of Y" to hide proprietary stage names, but the "stage outputs (developer)" section remains fully visible with complete debugging data, output_data, and error_messages.

3.  **Multi-Pipeline Support**:
    *   Supports all pipeline types: Generation (7 stages), Refinement (3 stages), and Caption (1 stage).
    *   Automatically detects pipeline type and applies appropriate stage numbering.

4.  **Frontend Compatibility**:
    *   The existing `RunResults` component gracefully handles both masked and unmasked stage names.
    *   Developers see full details in the RunResults page, while the designer only sees obfuscated real-time progress.

## 3. Implementation Status

✅ **Completed**: 
1.  **Backend**: Added environment variable support in `churns/core/user_config.py`
2.  **Backend**: Modified WebSocket logic in `churns/api/websocket.py` to obfuscate stage updates when `PRESENTATION_MODE=true`
3.  **Configuration**: Added `PRESENTATION_MODE` setting to `sample.env` in the Feature Flags section
4.  **Frontend**: Verified compatibility with `RunResults` component

By implementing this "Presentation Mode," we can provide the designer with a fully functional user experience for evaluation while effectively protecting our trade secrets.
