# GridLock 2.0 - Corridor Watch

Corridor Watch is a production-quality, professional decision-support and traffic command dashboard designed for the Bengaluru Traffic Command. The system automates incident triage by assessing the probability of road closure, estimating median clearance times, evaluating corridor vulnerability metrics, and suggesting optimal diversion strategies for traffic controllers.

---

## 1. System Architecture

The application is structured as a decoupled client-server architecture. The backend service encapsulates the core machine learning inference pipeline and serves pre-computed topological data, while the frontend single-page application displays the real-time operational status.

```mermaid
graph TD
    classDef client fill:#070a0f,stroke:#1f2d40,stroke-width:2px,color:#dde3ee
    classDef server fill:#0d1220,stroke:#d97706,stroke-width:2px,color:#dde3ee
    classDef storage fill:#0a0e18,stroke:#5eead4,stroke-width:2px,color:#dde3ee

    subgraph Client [Client - Vite + React Single Page Application]
        UI[User Interface Dashboard]:::client
        Styles[Vanilla CSS Design System]:::client
        UI --- Styles
    end

    subgraph Server [Server - FastAPI Application]
        API[FastAPI Router main.py]:::server
        ML[Inference Pipeline recommend.py]:::server
        LGBM[LightGBM Model Ensemble]:::server
        
        API -->|1. Parse and Validate| ML
        ML -->|2. Evaluate Ensemble| LGBM
    end

    subgraph Storage [Static Data & Artifacts]
        Meta[Model Metadata meta.json]:::storage
        Centroids[Corridor Centroids CSV]:::storage
        Fragility[Corridor Fragility Index CSV]:::storage
        PoliceMap[Corridor Police Station Mapping CSV]:::storage
        ETALookup[ETA Lookup CSV]:::storage
    end

    UI -->|HTTP GET /api/meta| API
    UI -->|HTTP POST /api/assess| API
    
    API -.->|Load Metadata| Meta
    API -.->|Resolve Coordinates| Centroids
    API -.->|Resolve Police Jurisdictions| PoliceMap
    
    ML -.->|Read Thresholds| Meta
    ML -.->|Evaluate Fragility| Fragility
    ML -.->|Resolve ETA| ETALookup
```

### Components

#### Frontend Single-Page Application (SPA)
The frontend is a lightweight Single-Page Application built with React, TypeScript, and Vite. All styles are declared in vanilla CSS, implementing a dark operations-center theme utilizing amber as the primary command color.
- **Incident Intake Panel (Left Column)**: Collects operational incident parameters, including incident category, targeted traffic corridor, police jurisdiction overrides, incident scheduling, classification, and report authentication tags.
- **Risk Assessment Panel (Center Column)**: Renders a custom SVG semicircular gauge visualizing closure probability, paired with contextual information tags and structural fragility scores.
- **Operational Intelligence Panel (Right Column)**: Displays action items, recommended diversion routes, and an auto-generated summary report.

#### Backend REST API (FastAPI)
The backend is a python-based REST API built with FastAPI. It handles routing, requests verification, coordinates resolution, and delegates tasks to the machine learning inference pipeline.
- **`GET /health`**: Health check endpoint.
- **`GET /api/meta`**: Reads training metadata to generate validated dropdown parameters for the frontend client.
- **`POST /api/assess`**: Receives incident payloads, normalizes inputs, resolves implicit details, evaluates the prediction ensemble, and formats the response.

#### Inference & Analytics Engine
Residing in the backend under the `theme2` module, this component loads pre-trained model ensembles and static lookup files. It performs multi-class category encoding, calculates road closure risk, retrieves median clearance estimates, and dynamically identifies lower-vulnerability corridors in the target traffic zone.

---

## 2. Operational Data Flow

The following flowchart outlines the step-by-step execution lifecycle when an operator logs a new incident:

```mermaid
flowchart TD
    classDef step fill:#070a0f,stroke:#1f2d40,stroke-width:2px,color:#dde3ee
    classDef decision fill:#0d1220,stroke:#d97706,stroke-width:2px,color:#dde3ee

    Start([Incident Intake Form Submitted]):::step --> CheckAuth{Authenticate Report?}:::decision
    
    CheckAuth -->|Yes| SetAuth[Set authenticated_bin = 1]:::step
    CheckAuth -->|No| SetAuthNo[Set authenticated_bin = 0]:::step
    
    SetAuth & SetAuthNo --> CheckOverride{Jurisdiction Override?}:::decision
    
    CheckOverride -->|Manual| ManualPS[Use User Selected Police Station]:::step
    CheckOverride -->|Auto| AutoPS[Resolve Top Jurisdiction via corridor_police_map.csv]:::step
    
    ManualPS & AutoPS --> ResolveCoords[Resolve GPS Coordinates from corridor_centroids.csv]:::step
    ResolveCoords --> ParseTime[Extract Hour, Day of Week, Peak Status, and Weekend Status]:::step
    
    ParseTime --> PredictClosure[Run Inputs Through 5-Fold LightGBM Models]:::step
    PredictClosure --> GetETA[Retrieve Historical Median ETA for Incident Type]:::step
    GetETA --> GetFragility[Fetch Corridor Fragility Score out of 10]:::step
    
    GetFragility --> CalcRiskLabel{Closure Risk Probability}:::decision
    CalcRiskLabel -->|p >= 0.35| HighRisk[Assign HIGH Risk Label]:::step
    CalcRiskLabel -->|0.12 <= p < 0.35| MedRisk[Assign MEDIUM Risk Label]:::step
    CalcRiskLabel -->|p < 0.12| LowRisk[Assign LOW Risk Label]:::step
    
    HighRisk & MedRisk & LowRisk --> SuggestDiversion{Is Named Corridor?}:::decision
    SuggestDiversion -->|Yes| FetchDiversion[Retrieve Lowest Fragility Named Corridor in Same Zone]:::step
    SuggestDiversion -->|No| ClearDiversion[Set Diversion to None]:::step
    
    FetchDiversion & ClearDiversion --> FormatResponse[Generate Operational Summary & Recommendations]:::step
    FormatResponse --> SendClient([Return JSON payload to UI]):::step
```

---

## 3. Technical Stack

- **Frontend**:
  - Framework: React 18 with TypeScript
  - Bundler: Vite 8
  - Styling: Vanilla CSS (Theme: Amber on Jet Black, font families: Inter and JetBrains Mono)
  - Layout: CSS Grid (3-column dashboard topology)

- **Backend**:
  - Runtime: Python 3.11
  - Framework: FastAPI
  - Web Server: Uvicorn
  - Data Processing: Pandas, NumPy
  - Serialization: Joblib
  - Model Framework: LightGBM

---

## 4. Local Development Setup

### Directory Structure

```
/backend
  /theme2                   # Self-contained ML code and artifacts
    /artifacts              # Serialized LightGBM models, mapping and lookup tables
    recommend.py            # Primary recommendation and inference script
    train.py                # Model training routine
  main.py                   # FastAPI application entrypoint
  requirements.txt          # Python dependencies
  render.yaml               # Backend deployment blueprint configuration
/frontend
  /public                   # Public assets (custom street light SVG favicon)
  /src
    /components             # Modular React components (Gauge, metrics display)
    App.tsx                 # Core page layout, form handling, and state management
    index.css               # Design system and CSS variables
    main.tsx                # Client application root mount
  package.json              # Node dependencies and scripts
  tsconfig.json             # TypeScript compiler rules
```

### Prerequisites
- Node.js (version 18 or newer)
- Python (version 3.11)

### Backend Service Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows (Command Prompt)
   venv\Scripts\activate
   # On Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   # On Linux/macOS
   source venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Uvicorn local development server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   The API documentation will be available locally at `http://localhost:8000/docs`.

### Frontend Client Setup
1. Open a new terminal window and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the required Node packages:
   ```bash
   npm install
   ```
3. Launch the Vite local development server:
   ```bash
   npm run dev
   ```
   The client application will run at `http://localhost:5173/`.

---

## 5. Production Deployment

### Backend Deployment (Render)
1. Commit and push the project changes to a GitHub repository.
2. Log into the Render Dashboard and choose **New > Web Service**.
3. Connect the repository.
4. Set the following environment configuration parameters:
   - **Root Directory**: `backend`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under Advanced settings, declare the environment variable:
   - `PYTHON_VERSION`: `3.11.4`

### Frontend Deployment (Vercel)
1. In Vercel, select **New Project** and import the target repository.
2. Select **Vite** as the framework preset.
3. Set the **Root Directory** to `frontend`.
4. Add the following environment variable in the dashboard configurations:
   - `VITE_API_URL`: Set this value to the live HTTPS URL of the deployed Render backend (e.g., `https://gridlock-api.onrender.com`).
5. Click **Deploy**.

---

## 6. Credits

### Hackathon Team Members
- Anurag Kumar Verma
- Shreyanshu Ghosh
- Abhishek Kumar

