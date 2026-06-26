# ClaimWise

A production-grade, streamlined claims-intelligence platform combining document intake, OCR, machine learning, and reactive streaming pipelines to accelerate insurance claim handling.

---

## System Architecture

ClaimWise integrates a React client, a FastAPI gateway, scikit-learn machine learning models, and a **Pathway** reactive streaming dataflow to parse, score, and route claims in real time.

```mermaid
flowchart TD
    subgraph Client ["Client (React UI, http://localhost:8080)"]
        UI_Rules["Rules Editor (attribute, operator, amount, forward_to)"]
        UI_Dashboard["Dashboard (Claims List, Queues, AI Chat)"]
    end

    subgraph Backend ["FastAPI Backend (http://localhost:8000)"]
        API["FastAPI Web Server"]
        OCR["OCR Service (PyMuPDF)"]
        ClaimStore["Claim Store (Claims / Queue State)"]
        ML_Service["ML Service (Inference Orchestrator)"]
        Routing_Service["Routing Service (Rule Normalization & Fallbacks)"]
        Pathway_Pipeline["Pathway Engine (Reactive Rerouting Pipeline)"]
    end

    subgraph MLCore ["ML Core (ml/)"]
        ML_Config["ML Config"]
        ML_Pipeline_Py["ML Pipeline (Regex Parsers & Feature Building)"]
        ML_Models["Scikit-Learn Models (Random Forests)"]
    end

    %% Ingestion Flow
    UI_Dashboard -->|1. Upload Claim PDFs| API
    API -->|2. Extract Text| OCR
    OCR -->|3. Raw Text| ML_Service
    ML_Service -->|4. Parse Fields & Features| ML_Pipeline_Py
    ML_Pipeline_Py -->|5. Predict Scores| ML_Models
    ML_Models -->|6. Scores (Fraud, Severity, Complexity)| ML_Service
    ML_Service -->|7. Return ML Scores| API

    %% Routing Flow
    API -->|8. Apply Rules| Routing_Service
    Routing_Service -->|Option A: Standard Evaluation| ClaimStore
    API -->|9. Ingest Claim & Rules| Pathway_Pipeline
    Pathway_Pipeline -->|Option B: Reactive Streaming Reroute| ClaimStore

    %% Rule Synchronization
    UI_Rules -->|Post /routing/rules| API
    API -->|Save Rules| Routing_Service
    Routing_Service -->|Trigger Sync| Pathway_Pipeline
    
    %% Output
    ClaimStore -->|Sync Claims & Queues| UI_Dashboard
```

### Component Details

1.  **Ingestion & Parsing**: Custom PDF parsing (`PyMuPDF`) extracts structured metadata from raw text (e.g. loss amounts, incident dates, injuries, vehicle registration) based on document type (ACORD, Police Report, Hospital Bill).
2.  **ML Feature Engineering**: Combines document fields to compute discrepancy checks (e.g. loss amount difference, date mismatch, litigation risk indicators).
3.  **ML Scoring**: Runs scikit-learn Random Forest models to evaluate:
    *   *Fraud Probability*: Classifier predicting the likelihood of fraud.
    *   *Severity level*: Classifier predicting Low/Medium/High severity.
    *   *Complexity Score*: Regressor predicting claims processing difficulty (1.0 to 5.0).
4.  **Business Routing Rules**: Custom routing rules defined by adjusters in the UI (e.g., *Forward claims with complexity >= 3.5 to Senior Team*). Rules are normalized to and from the frontend/backend formats and processed sequentially by priority.
5.  **Pathway Reactive Rerouting**: When rules are updated, the Pathway streaming engine immediately evaluates all active claims against the new rules snapshot in-memory and automatically reassigns queues without manual reprocessing.

---

## Project Layout

```
ClaimWise/
├── backend/                  # FastAPI Application
│   ├── main.py               # Gateway entrypoint
│   ├── routers/              # API endpoints (upload, routing, claims, pathway, chat)
│   ├── schemas/              # Pydantic schemas (RuleCreate, RuleUpdate, etc.)
│   ├── services/             # Ingestion, OCR, ML, Routing, and Pathway services
│   ├── tests/                # Pytest unit and integration tests
│   └── routing_rules.json    # Persistent JSON storage for rules
├── frontend/                 # Vite + React Client SPA
│   ├── client/               # React components, pages, hooks, and API client
│   ├── tailwind.config.ts    # Styling configurations
│   └── package.json          # Node scripts and dependencies
├── ml/                       # Machine Learning Codebase
│   ├── config.py             # Central configuration (paths, weights, parameters)
│   ├── pipeline.py           # Preprocessing, text parsing, and feature extraction
│   ├── train.py              # Scikit-Learn training pipelines for Random Forests
│   └── models/               # Serialized .pkl models and metrics.json
└── docker-compose.yml        # Unified multi-container orchestration
```

---

## Deployment & Setup

Choose one of the following methods to deploy the complete ClaimWise application.

### Method A: Unified Docker Compose (Recommended)
Docker isolates all system packages, installing `tesseract-ocr` and **Pathway** (which requires Linux/macOS) in a containerized Linux environment.

1.  **Configure Environment**:
    Create a `.env` file at the project root based on `.env.example`:
    ```bash
    VITE_API_BASE_URL=http://localhost:8000
    GEMINI_API_KEY=your_google_gemini_api_key
    ```
2.  **Launch the Application**:
    Build and start both the backend and frontend services altogether:
    ```bash
    docker-compose up --build -d
    ```
3.  **Access the Ports**:
    *   **Frontend Interface**: [http://localhost:8080](http://localhost:8080)
    *   **Backend REST API**: [http://localhost:8000](http://localhost:8000)
    *   **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Method B: Local Development Setup
To run the components natively on your machine:

#### Prerequisites
*   Python 3.10+ (and virtualenv)
*   Node.js 18+ and `pnpm`
*   Tesseract OCR (installed on host OS for image-to-text extraction)

#### 1. Backend Setup
1.  Navigate to the `backend/` directory:
    ```bash
    cd backend
    ```
2.  Create and activate a virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    pip install pathway   # (Linux and macOS only)
    ```
4.  Start the FastAPI server:
    ```bash
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload
    ```

#### 2. Frontend Setup
1.  Navigate to the `frontend/` directory:
    ```bash
    cd ../frontend
    ```
2.  Install dependencies:
    ```bash
    pnpm install
    ```
3.  Start the Vite development server:
    ```bash
    pnpm run dev
    ```
    Open your browser to [http://localhost:8080](http://localhost:8080).

---

## Verification & Testing

### Python Backend Unit Tests
We maintain an automated pytest suite validating rule matching boundaries, normalization logic, and Pathway pipeline state:
```bash
# From workspace root
./.venv/bin/python -m pytest backend/tests/test_routing.py
```

### TypeScript Verification
Ensure zero frontend compile errors:
```bash
# From frontend/ directory
pnpm typecheck
```

---

## Chat Assistant (Gemini)
To enable the conversational claims chat assistant:
1.  Create a Google Gemini API Key.
2.  Set it in your host environment or `.env` file:
    ```bash
    export GEMINI_API_KEY=<your_api_key>
    ```
3.  Open any Claim detail panel in the dashboard to converse with the chat assistant about the parsed claims documents.

---

## License

This project is licensed under the MIT License © 2026 kanak227. See the `LICENSE` file for details.