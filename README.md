# GridLock 2.0 - Corridor Watch

Corridor Watch is a production-quality, professional decision-support and traffic command dashboard designed for the Bengaluru Traffic Command. The system automates incident triage by assessing the probability of road closure, estimating median clearance times, evaluating corridor vulnerability metrics, and suggesting optimal diversion strategies for traffic controllers.

![Corridor Watch - Dataset & Model at a Glance](ref/10_dataset_stats_card.png)

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
- **Incident Intake Panel (Left Column)**: Collects operational incident parameters (incident category, corridor, police jurisdiction, time parameters, report authentication). Features smart, sequential auto-scrolling to guide operators through input fields. Pins validation warnings at the bottom. Once assessed, the form freezes to show an immutable summary, and presents an "Assess New Risk" action to reset the state.
- **Risk Assessment Panel (Center Column)**: Renders a custom SVG semicircular gauge visualizing closure probability, paired with contextual information tags and structural fragility scores. Contains dynamic scroll indicators (blinking down-arrow) if content overflows.
- **Operational Intelligence Panel (Right Column)**: Displays action items, recommended diversion routes, and an auto-generated summary report. Includes dynamic scroll indicators if content overflows.

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

## 3. Exploratory Data Analysis & Operational Insights

Before modeling, the training dataset of **8,173 traffic incidents** was thoroughly analyzed to identify underlying temporal and spatial patterns.

### Temporal Closure Hazards
Analyses of closure rates by hour revealed that peak road closure risks occur during mid-day (**10:00 - 17:00**), peaking at **40.7%** around noon. Interestingly, the evening rush hour (**19:00 - 22:00**), while having high traffic volume, presents a significantly lower rate of complete road closure (5% to 7%).

![Road Closure Rate by Hour](ref/01_hourly_closure_rate.png)

Cross-referencing the cause of the incident with the hour of the day highlights specific high-risk windows. For example, construction projects and tree falls exhibit elevated closure probabilities during specific intervals, which our model exploits.

![Closure Rate Heatmap by Cause & Hour](ref/05_cause_hour_heatmap.png)

### Corridor Fragility Index
We formulated a dynamic **Corridor Fragility Index (out of 10)** to represent how susceptible a corridor is to gridlock. The index weights event frequency, historical closure rate, and resolution times:

$$\text{Fragility Score} = 0.4 \times \text{Event Count} + 0.4 \times \text{Closure Rate} + 0.2 \times \text{Average Resolution Time}$$

Based on this score, named corridors are classified into High, Medium, and Lower fragility. When an incident occurs on a high-fragility corridor, the dashboard automatically recommends a diversion route using the lowest-fragility corridor within the same traffic zone.

![Corridor Fragility Index Chart](ref/02_corridor_fragility.png)

### Resolution Time (ETA) Estimation
For estimating median clearance times (ETA), a machine learning regressor was trained but ultimately dropped in favor of a historical lookup table. The LightGBM regressor achieved an OOF Mean Absolute Error (MAE) of 28.8 minutes, which did not provide a statistically meaningful lift over the historical lookup baseline of 29.5 minutes. The lookup table was selected for its transparency, simplicity, and low computational overhead.

![Historical Median ETA by Cause](ref/04_eta_by_cause.png)

---

## 4. Machine Learning Pipeline & Model Training

### Feature Selection & Engineering
We evaluated 46 raw features from the traffic logs. To avoid overfitting and optimize performance, we filtered these down to 12 high-signal features across geographical, temporal, and metadata categories.

![Feature Selection Matrix](ref/08_feature_selection_table.png)

Our LightGBM model ensemble relies heavily on geographic coordinates (Latitude and Longitude) and the event cause. Together, these top features drive **58%** of the model's prediction signal.

![LightGBM Feature Importances](ref/03_feature_importance.png)

### Model Evaluation & Cross-Validation
To guarantee generalization across different timeframes and locations in Bengaluru, we utilized a **5-Fold Stratified Cross-Validation** strategy. The ensemble achieves a robust Out-Of-Fold (OOF) Area Under the ROC Curve (AUC) of **0.8057**, indicating highly stable predictions across folds.

![5-Fold CV AUC Chart](ref/06_fold_auc.png)

For deployment testing, a **20-case self-demo matrix** was run to verify in-sample operational accuracy. The system achieved a **95% accuracy rate (19/20 correct)**, with 0 false alarms and only a single missed closure (a vehicle breakdown at midnight, which is historically a lower-hazard hour).

![Self-Demo Confusion Matrix](ref/07_self_demo_matrix.png)

### Data Quality Finding: Priority Column Leakage
A critical finding during data exploration was that the `priority` column represents administrative routing rules (whether the incident occurred on a named corridor) rather than actual hazard severity. Including it as a model target or feature resulted in a near-perfect OOF AUC of **0.9998**, a classic indicator of target leakage. To preserve model integrity, the `priority` feature was dropped.

![Priority Leakage Analysis](ref/09_priority_leakage.png)

---

## 5. Rigour Over Results: Things We Tried and Rejected

We prioritized scientific rigour and operational safety over "inflated" model metrics. Multiple modelling approaches were experimented with and systematically rejected based on validation performance.

![Things We Tried and Rejected Chart](ref/12_what_we_rejected.png)

---

## 6. Reviewer FAQ & Technical Rebuttals

Anticipating tough questions from system reviewers, we have documented our design decisions and justifications below:

![Reviewer Rebuttals Card](ref/11_judge_challenges.png)

---

## 7. Technical Stack

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

## 8. Local Development Setup

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

## 9. Production Deployment

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

## 10. Credits

### Hackathon Team Members
- Anurag Kumar Verma
- Shreyanshu Ghosh
- Abhishek Kumar
