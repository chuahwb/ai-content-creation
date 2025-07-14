# EDA Migration Plan: From Monolith to Production-Grade Scalability

## 1. Executive Summary

This document outlines a strategic plan to migrate the application from its current asynchronous monolithic architecture to a robust, scalable, and resilient Event-Driven Architecture (EDA). This transition is critical to support our growth as a consumer-facing application, ensuring a consistently fast user experience, high reliability, and the ability to scale gracefully under load.

The core of this migration involves introducing a message broker (RabbitMQ) and dedicated worker services. This will decouple the API from the heavy lifting of pipeline execution, solving current and future bottlenecks related to performance, reliability, and concurrency. We will also implement a Redis Pub/Sub system to bridge the gap for real-time WebSocket updates, ensuring a seamless user experience. This plan prioritizes developer experience by establishing a comprehensive local development environment using Docker Compose and embedding observability from day one.

**This is not just a technical upgrade; it is a foundational investment in the product's future success.**

## 2. Problem Statement & Business Justification

The current architecture, while efficient for a single-process application, presents fundamental risks to a consumer-facing product:

1.  **Poor User Experience Under Load:** When multiple users run pipelines simultaneously, the shared resources on the API server will become saturated, leading to a slow, unresponsive UI for *all* users.
2.  **Lack of Reliability:** A server crash or deployment will terminate any in-progress pipeline runs, leading to lost user work, frustration, and potential churn.
3.  **Noisy Neighbor Problem:** A single, resource-intensive job from one user can degrade the performance and experience for every other user on the platform.
4.  **Inability to Scale Efficiently:** We can only scale the entire monolith. We cannot independently scale the API and the pipeline processing, leading to inefficient and costly resource allocation.

EDA directly solves these problems by creating a system that is scalable, resilient, and guarantees a responsive experience regardless of the background workload.

## 3. Proposed Event-Driven Architecture

The new architecture will be composed of several distinct, decoupled services communicating through events.

```mermaid
graph TD
    subgraph "User's Browser"
        Frontend
    end

    subgraph "API Layer (Handles HTTP & WebSockets)"
        API_Server
    end

    subgraph "Event & Communication Layer"
        Broker[RabbitMQ <br/><i>(Job Queue)</i>]
        Cache[Redis <br/><i>(Pub/Sub for UI Updates)</i>]
    end

    subgraph "Processing Layer (Scalable & Independent)"
        W1(Pipeline Worker 1)
        W2(Pipeline Worker 2)
        W3(Pipeline Worker ...)
    end
    
    subgraph "Data Layer"
        Database[(Database)]
    end

    Frontend -- HTTP Request --> API_Server
    API_Server -- Publishes Job --> Broker
    
    Broker -- Distributes Job --> W1
    Broker -- Distributes Job --> W2
    Broker -- Distributes Job --> W3

    W1 -- Reads/Writes --> Database
    W2 -- Reads/Writes --> Database
    W3 -- Reads/Writes --> Database

    %% Real-time Update Path
    Frontend -- WebSocket --> API_Server
    W1 -- Publishes Progress --> Cache
    W2 -- Publishes Progress --> Cache
    W3 -- Publishes Progress --> Cache
    
    API_Server -- Subscribes to Progress --> Cache
    API_Server -- Forwards Update --> Frontend
```

### Key Component Roles:

*   **API Server (`main.py`):** Its role is simplified. It handles user authentication, request validation, and WebSocket connections. For pipeline runs, it publishes a job to RabbitMQ and immediately returns a response to the user. It also listens to Redis for progress updates to forward to the client.
*   **Message Broker (RabbitMQ):** Acts as a durable, persistent queue for pipeline jobs. It ensures that jobs are not lost and distributes them to available workers.
*   **Pipeline Workers (`worker.py`):** These are separate, dedicated services that do the heavy lifting. They listen for jobs from RabbitMQ, execute the pipeline logic (moved from `background_tasks.py`), write to the database, and publish progress updates to Redis. They can be scaled independently.
*   **Redis Pub/Sub:** A lightweight, high-speed channel for workers to broadcast real-time progress updates without needing to know about the API server or WebSockets.

## 4. Detailed Implementation Plan

This migration will be executed in five deliberate phases to ensure a smooth transition.

### Phase 1: Infrastructure Setup & Configuration

**Goal:** Add the new services to our environment.

1.  **Update `requirements.txt`:** Add libraries for RabbitMQ and Redis.
    ```
    # requirements.txt
    ...
    aio-pika  # Async library for RabbitMQ
    aioredis  # For Redis Pub/Sub
    ```
2.  **Update `docker-compose.yml`:** Define the new services.
    ```yaml
    # docker-compose.yml
    services:
      api:
        # ... existing config
        depends_on:
          - db
          - redis
          - rabbitmq # API needs to connect to the broker
      
      db: # ... existing postgres/sqlite config
      
      redis:
        image: redis:7-alpine
        ports:
          - "6379:6379"

      rabbitmq:
        image: rabbitmq:3.11-management
        ports:
          - "5672:5672"  # AMQP protocol port
          - "15672:15672" # Management UI port
        environment:
          - RABBITMQ_DEFAULT_USER=user
          - RABBITMQ_DEFAULT_PASS=password

      worker:
        build:
          context: .
          dockerfile: Dockerfile.api # Can reuse the same image for now
        command: python -m churns.worker # New entrypoint
        depends_on:
          - db
          - redis
          - rabbitmq
        environment:
          # All secrets/API keys needed for pipeline execution
          - OPENAI_API_KEY=${OPENAI_API_KEY} 
          - DATABASE_URL=${DATABASE_URL}
          # ... etc
    ```
3.  **Environment Variables:** Add `RABBITMQ_URL` and `REDIS_URL` to your `.env` file.

### Phase 2: Create the Pipeline Worker Service

**Goal:** Isolate the pipeline execution logic into a new, standalone service.

1.  **Create `churns/worker.py`:** This will be the main entrypoint for the worker service.
    ```python
    # churns/worker.py
    import asyncio
    import json
    from churns.api.database import async_session_factory
    from churns.api.background_tasks import _execute_pipeline, _execute_refinement # etc.
    from churns.utils.mq_client import get_rabbitmq_connection # New utility
    from churns.utils.redis_client import get_redis_client # New utility

    async def main():
        connection = await get_rabbitmq_connection()
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue('pipeline_jobs', durable=True)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        payload = json.loads(message.body)
                        job_type = payload.get("type")
                        
                        # Use existing, now-isolated, logic
                        if job_type == "generation":
                            await _execute_pipeline(payload["run_id"], payload["data"])
                        elif job_type == "refinement":
                            await _execute_refinement(payload["job_id"], payload["data"])
                        # ... add other job types

    if __name__ == "__main__":
        asyncio.run(main())
    ```
2.  **Refactor `churns/api/background_tasks.py`:**
    *   The functions (`_execute_pipeline`, etc.) will be slightly modified to accept all necessary data from the job payload instead of relying on in-process memory.
    *   The dependency on the `WebSocketManager` must be removed. This will be replaced by the Redis publisher.

### Phase 3: Adapt the API to Publish Jobs

**Goal:** Change the API endpoints to be lightweight publishers.

1.  **Refactor `churns/api/routers.py`:**
    ```python
    # churns/api/routers.py
    from churns.utils.mq_client import get_rabbitmq_channel # New utility

    @runs_router.post("", status_code=202) # 202 Accepted is more semantic
    async def create_pipeline_run(
        request: PipelineRunRequest,
        channel: aio_pika.Channel = Depends(get_rabbitmq_channel),
        # ... other dependencies
    ):
        # ... (Create the initial PipelineRun in the DB as before)
        run = PipelineRun(...)
        session.add(run)
        await session.commit()
        await session.refresh(run)

        # Instead of asyncio.create_task, publish to RabbitMQ
        job_payload = {
            "type": "generation",
            "run_id": run.id,
            "data": request.model_dump()
        }
        
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(job_payload).encode()),
            routing_key='pipeline_jobs'
        )

        return run # Return immediately
    ```
2.  Apply the same pattern to `create_refinement` and `generate_caption` endpoints.

### Phase 4: Implement Real-Time Updates via Redis Pub/Sub

**Goal:** Re-establish the real-time progress updates for the frontend.

1.  **Modify the Worker's Progress Callback:**
    *   In `churns/api/background_tasks.py`, the `progress_callback` function will be modified. Instead of calling the WebSocket manager, it will publish to Redis.
    ```python
    # churns/api/background_tasks.py (now running in the worker)

    async def redis_progress_callback(run_id: str, message: dict):
        redis = await get_redis_client()
        channel_name = f"run_updates:{run_id}"
        await redis.publish(channel_name, json.dumps(message))

    # The _execute_pipeline function will now be passed this redis_progress_callback
    ```
2.  **Create a Redis Subscriber in the API Server:**
    *   In `churns/api/websocket.py`, the `WebSocketManager` will spawn a listener task for each connected run.
    ```python
    # churns/api/websocket.py

    class WebSocketManager:
        # ... existing connect/disconnect logic

        async def connect(self, websocket: WebSocket, run_id: str):
            await websocket.accept()
            self.active_connections[run_id] = websocket
            # Spawn a task to listen for updates for this specific run
            asyncio.create_task(self.redis_listener(run_id, websocket))

        async def redis_listener(self, run_id: str, websocket: WebSocket):
            redis = await get_redis_client()
            pubsub = redis.pubsub()
            await pubsub.subscribe(f"run_updates:{run_id}")
            try:
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
                    if message and 'data' in message:
                        # Forward the data received from Redis to the client
                        await websocket.send_text(message['data'].decode())
            except WebSocketDisconnect:
                # Handle cleanup if client disconnects
                self.disconnect(run_id)
            finally:
                await pubsub.unsubscribe(f"run_updates:{run_id}")
    ```

## 5. Developer Experience & Debugging Strategy

**Goal:** To build a developer-friendly environment that mitigates the complexity of a distributed system, enabling rapid development and effective debugging.

### 5.1 The Principle: Dev/Prod Parity

We will **not** maintain separate architectures for development and production. Doing so leads to critical bugs being discovered only in production. Our strategy is to make the production architecture easy to run and debug locally.

### 5.2 One-Command Local Environment

A developer must be able to launch the entire, multi-service application stack with a single command.

*   **Action:** We will build a comprehensive `docker-compose.dev.yml` that defines and configures the `api`, `worker`, `rabbitmq`, `redis`, and `db` services.
*   **Goal:** A developer clones the repo, sets up their `.env` file, and runs `docker-compose up`. The entire application starts, with **hot-reloading enabled** for both the API and worker services, allowing for immediate feedback on code changes.

### 5.3 Deep Observability: The Distributed Debugger

Since we cannot attach a single debugger to all services, we will rely on deep observability tools to understand the system's behavior.

1.  **Distributed Tracing (Essential):**
    *   **Tool:** Integrate **OpenTelemetry**.
    *   **Implementation:**
        *   The API service will generate a `trace_id` for every incoming request.
        *   This `trace_id` will be automatically propagated in the headers of the RabbitMQ message.
        *   The worker will extract the `trace_id` and continue the trace.
    *   **Benefit:** This provides a visual, end-to-end flame graph of a request as it flows through the API, into the queue, and through the worker's execution stages. It is the single most powerful tool for pinpointing latency and errors in a distributed system.

2.  **Structured Logging:**
    *   **Tool:** Integrate a library like `structlog`.
    *   **Implementation:** All log output from all services will be in JSON format and **must** contain the `trace_id`.
    *   **Benefit:** Allows developers to instantly filter and view the complete, ordered log history of a single user action across all services, e.g., "show me all logs for `trace_id=xyz`".

3.  **Broker & Cache UIs:**
    *   **Action:** Document and promote the use of the **RabbitMQ Management UI** (`localhost:15672`).
    *   **Benefit:** Gives developers a real-time window into the system's state. They can inspect message contents, monitor queue lengths, and manually purge or re-queue messages for debugging.

### 5.4 Pragmatic Hybrid Execution Mode

To balance development speed with architectural purity, we will use a single environment variable for two purposes.

*   **`EXECUTION_MODE` Environment Variable:**
    *   `EDA` (default for production and CI): The full distributed architecture is used.
    *   `MONOLITH` (local development convenience): The API bypasses RabbitMQ and calls the pipeline logic directly via `asyncio.create_task`, as it does today.
*   **Workflow:** A developer can use `MONOLITH` mode for the initial, rapid development of a feature within a single service. However, before submitting a pull request, they **must** switch to `EDA` mode and test the full, end-to-end flow using the one-command local environment. The CI/CD pipeline will *only* run tests in `EDA` mode.

## 6. Testing Strategy

1.  **Unit Tests:** Test the message publishing logic in the API and the message consumption logic in the worker in isolation, using mocked broker connections.
2.  **Integration Tests:** Create a separate `docker-compose.test.yml`. The test suite (running in `EDA` mode) will use a real (but temporary) RabbitMQ and Redis instance to test the full end-to-end flow:
    *   Call the API endpoint.
    *   Assert that a message appears in the correct RabbitMQ queue.
    *   Assert that a worker consumes the message.
    *   Assert that the database is updated correctly.
    *   Assert that progress messages are published to Redis and received by a test WebSocket client.
3.  **Load Tests:** Use a tool like Locust to simulate high traffic against the API, ensuring the queue handles the load gracefully and API response times remain low.

## 7. Deployment & Rollback Strategy

The `EXECUTION_MODE` flag provides a safe, zero-downtime rollout mechanism.

1.  **Deployment:** Deploy the new `api` and `worker` code to production with `EXECUTION_MODE` set to `MONOLITH`. The worker service will be running but will not receive any jobs.
2.  **Staged Rollout:**
    *   Enable `EDA` mode for internal users first.
    *   Gradually enable it for a small percentage of real users (e.g., 1%, 10%, 50%).
    *   Monitor performance and error rates closely.
3.  **Rollback Plan:** If any critical issues arise, simply set `EXECUTION_MODE` back to `MONOLITH`. This instantly reverts the system to its previous behavior without requiring a code redeployment.

## 8. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| **Increased Complexity** | Invest heavily in developer tooling, documentation, and observability as detailed in the Developer Experience strategy (Section 5). |
| **Message Broker Downtime** | Use a highly available, managed RabbitMQ service in production. Implement connection retry logic with exponential backoff in the API and workers. |
| **Poison Pill Messages** | A malformed message could crash a worker repeatedly. Implement a Dead-Letter Queue (DLQ) in RabbitMQ. After N failed processing attempts, the message is moved to the DLQ for manual inspection. |
| **Observability Gaps** | Strict adherence to the tools and practices in Section 5. Make distributed tracing and structured logging mandatory for new features. |

This plan provides a comprehensive, phased approach to evolving our architecture. By migrating to EDA, we are not just fixing performance issues; we are building a foundation that can support a successful, scalable, and reliable consumer product for years to come. 