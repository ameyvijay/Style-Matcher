# Antigravity Engine: Master Architecture & Data Flow (v2.4.0)

This document maps the **End-to-End Flywheel**. It emphasizes **Flow State Optimization**, **Non-Destructive Data Management**, and the **70/30 Cognitive Load Balance**.

---

## 1. Professional Data Flow (The 9-Stage Optimized Engine)

```mermaid
graph TD
    %% Class Definitions
    classDef healthy fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724;
    classDef broken fill:#f8d7da,stroke:#dc3545,stroke-width:2px,color:#721c24;
    classDef compromised fill:#fff3cd,stroke:#ffc107,stroke-width:2px,color:#856404;
    classDef deleted fill:#e2e3e5,stroke:#6c757d,stroke-width:2px,color:#383d41;
    classDef human fill:#cfe2ff,stroke:#0d6efd,color:#084298;

    %% Data Entry & Storage Logic
    subgraph Storage ["Source Directory (Durable)"]
        S_Orig["Original RAWs / JPEGs"]:::healthy
        S_XMP["Auto-Generated XMP Sidecars<br/>(Metadata: 1-5 Stars)"]:::healthy
    end

    %% Pipeline Logic
    subgraph Engine ["Processing Engine (Python Core)"]
        S1["Scan & Glob"]:::healthy
        S2["RAW Preview Extractor"]:::healthy
        S3["Multi-Model Scoring"]:::healthy
        S4["Burst & Visual Dedupe"]:::healthy
        S5["Reconciliation (🚩)"]:::broken
        S6["AI Coach Inference"]:::healthy
        
        %% PSYCHOLOGICAL LOAD BALANCING
        subgraph S7_8_Deep ["Stage 7 & 8: Cognitive Prioritization"]
            P_Port["Portfolio Bin"]:::compromised
            P_Amb["Amber Bin"]:::compromised
            P_Cull["Cull Bin"]:::compromised
            P_Logic["Psychological Load Balancer<br/>(The 70/30 Dopamine Loop)"]:::deleted
        end

        S9["Stage 9: Realization & Master Rendering<br/>(🚩 DELETED)"]:::broken
    end

    %% Output Management
    subgraph Output ["Output Directory"]
        Enhanced["/Enhanced Photos Folder"]:::healthy
    end

    %% Connections
    S_Orig --> S1 --> S2 --> S3 --> S4 --> S5 --> S6
    S6 --> P_Logic
    P_Logic --> P_Port & P_Amb & P_Cull
    P_Port & P_Amb & P_Cull -- "70/30 Interleaved Sync" --> PWA["Mobile Review UI (PWA)"]:::human
    PWA -- "Human Decisions" --> S9
    S9 -- "Render/Copy" --> Enhanced
```

---

## 2. Process Deep Dive

### A. Non-Destructive File Management
*   **Physical Integrity**: Source files are never moved. All decisions are written to **XMP Sidecars**.
*   **Consolidated Realization**: Only user-accepted masters are rendered into the `/Enhanced` folder.

### B. The 70/30 Cognitive Load Model (Stage 8.5)
To prevent "Decision Paralysis" and maintain your **Flow State** during review, the prioritization engine uses a constant-ratio interleaving algorithm:
1.  **Dopamine Ratio**: The review queue is stacked such that you have a **70% probability of an "Accept"** and a **30% probability of a "Reject"**. 
2.  **Decision Anti-Stagnancy**: We introduce minor randomization (stochastic jitter) in the ranking to prevent your brain from "autopiloting" or developing bias.
3.  **Fatigue Prevention**: By keeping the 70/30 ratio constant across the entire subset, the engine reduces cognitive friction, making high-speed culling feel effortless rather than fatiguing.

---

## 3. Engineering Impact Analysis (🚩)
*   **🚩 Stage 8.5 Load Balancer**: Requires a new stochastic interleaving module to manage the 70/30 distribution across the Portfolio, Amber, and Cull bins.
*   **🚩 Stage 9 Realization**: The service listening for these 70/30 decisions and executing the final rendering is currently broken.
