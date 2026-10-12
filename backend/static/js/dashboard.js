/**
 * RepoScore Autonomous Evaluation Dashboard Client
 * Adheres strictly to Phase 12 requirements, typed contracts, and RFC 7807 error handling.
 */

(function () {
  'use strict';

  // State Management
  const state = {
    currentEvaluationId: null,
    pollIntervalId: null,
    activeSubTab: 'dimensions',
    scorecard: null,
    evidenceItems: [],
    runtimeTelemetry: null,
    aiInterpretation: null,
  };

  // DOM Elements
  const elements = {
    // Navigation
    navDashboard: document.getElementById('nav-tab-dashboard'),
    navHistory: document.getElementById('nav-tab-history'),
    submissionSection: document.getElementById('submission-section'),
    trackingSection: document.getElementById('tracking-section'),
    resultsContainer: document.getElementById('results-container'),
    historySection: document.getElementById('history-section'),

    // Submission Form
    submitForm: document.getElementById('evaluation-submit-form'),
    repoUrlInput: document.getElementById('repo-url-input'),
    repoRefInput: document.getElementById('repo-ref-input'),
    aiToggle: document.getElementById('ai-reasoning-toggle'),
    startBtn: document.getElementById('start-evaluation-btn'),
    startBtnLabel: document.getElementById('start-btn-label'),
    quickSamples: document.querySelectorAll('.chip-sample'),

    // Tracker
    trackerEvalId: document.getElementById('tracker-eval-id'),
    trackerRepoName: document.getElementById('tracker-repo-name'),
    trackerElapsedText: document.getElementById('tracker-elapsed-text'),
    cancelBtn: document.getElementById('cancel-evaluation-btn'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    trackerStatusMsg: document.getElementById('tracker-status-message'),
    stepperItems: document.querySelectorAll('.step-item'),

    // Results Hero
    radialScoreNumber: document.getElementById('radial-score-number'),
    radialBar: document.getElementById('radial-bar'),
    compositeGradeBadge: document.getElementById('composite-grade-badge'),
    evalStatusPill: document.getElementById('eval-status-pill'),
    resultRepoHeading: document.getElementById('result-repo-heading'),
    resultCommitSha: document.getElementById('result-commit-sha'),
    resultDuration: document.getElementById('result-duration'),
    statTotalEvidence: document.getElementById('stat-total-evidence'),
    statCriticalCount: document.getElementById('stat-critical-count'),
    statRuntimeStrategy: document.getElementById('stat-runtime-strategy'),
    failureBanner: document.getElementById('failure-diagnostic-banner'),
    failureBannerTitle: document.getElementById('failure-banner-title'),
    failureBannerText: document.getElementById('failure-banner-text'),

    // Subtabs & Panes
    subnavTabs: document.querySelectorAll('.subnav-tab'),
    paneDimensions: document.getElementById('pane-dimensions'),
    paneEvidence: document.getElementById('pane-evidence'),
    paneRuntime: document.getElementById('pane-runtime'),
    paneAi: document.getElementById('pane-ai'),
    dimensionsGrid: document.getElementById('dimensions-grid'),
    evidenceCounter: document.getElementById('evidence-tab-counter'),
    evidenceList: document.getElementById('evidence-list-container'),
    filterSeverity: document.getElementById('filter-evidence-severity'),
    filterCategory: document.getElementById('filter-evidence-category'),
    searchEvidence: document.getElementById('evidence-search-input'),

    // Runtime Pane
    rtStrategy: document.getElementById('rt-strategy'),
    rtBuildStatus: document.getElementById('rt-build-status'),
    rtStartupStatus: document.getElementById('rt-startup-status'),
    rtLatency: document.getElementById('rt-latency'),

    // AI Pane
    aiModelName: document.getElementById('ai-model-name'),
    aiExecSummary: document.getElementById('ai-executive-summary'),
    aiArchAssessment: document.getElementById('ai-architectural-assessment'),
    aiSecurityNarrative: document.getElementById('ai-security-narrative'),
    aiRecsContainer: document.getElementById('ai-recommendations-container'),

    // History
    refreshHistoryBtn: document.getElementById('refresh-history-btn'),
    historyTableBody: document.getElementById('history-table-body'),

    // Receipt Drawer
    receiptDrawerBackdrop: document.getElementById('receipt-drawer-backdrop'),
    closeDrawerBtn: document.getElementById('close-drawer-btn'),
    drawerDimTitle: document.getElementById('drawer-dimension-title'),
    drawerCategoryPill: document.getElementById('drawer-category-pill'),
    drawerScoreValue: document.getElementById('drawer-score-value'),
    drawerWeightValue: document.getElementById('drawer-weight-value'),
    drawerReceiptList: document.getElementById('drawer-receipt-list'),

    // Toast Container
    toastContainer: document.getElementById('toast-container'),
  };

  // Step Progress Mapping
  const STEP_ORDER = [
    'INGESTING',
    'ANALYZING',
    'BUILDING',
    'STARTING',
    'TESTING',
    'SCORING',
    'AI_INTERPRETATION',
  ];

  const STEP_PROGRESS_PERCENT = {
    QUEUED: 5,
    INGESTING: 20,
    ANALYZING: 38,
    BUILDING: 55,
    STARTING: 68,
    TESTING: 78,
    OBSERVING: 85,
    SCORING: 92,
    AI_INTERPRETATION: 96,
    COMPLETED: 100,
    PARTIALLY_COMPLETED: 100,
    BUILD_FAILED: 100,
    STARTUP_FAILED: 100,
    FAILED: 100,
    TIMEOUT: 100,
    CANCELLED: 100,
  };

  /* ==========================================================================
     Toast Notifications
     ========================================================================== */
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 4500);
  }

  /* ==========================================================================
     Tab Navigation
     ========================================================================== */
  function initNavigation() {
    elements.navDashboard.addEventListener('click', () => {
      elements.navDashboard.classList.add('active');
      elements.navHistory.classList.remove('active');
      elements.submissionSection.classList.remove('hidden');
      if (state.scorecard) {
        elements.resultsContainer.classList.remove('hidden');
      }
      elements.historySection.classList.add('hidden');
    });

    elements.navHistory.addEventListener('click', () => {
      elements.navHistory.classList.add('active');
      elements.navDashboard.classList.remove('active');
      elements.submissionSection.classList.add('hidden');
      elements.trackingSection.classList.add('hidden');
      elements.resultsContainer.classList.add('hidden');
      elements.historySection.classList.remove('hidden');
      loadEvaluationHistory();
    });

    // Subtabs within Results
    elements.subnavTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.getAttribute('data-subtab');
        switchSubTab(target);
      });
    });
  }

  function switchSubTab(tabName) {
    state.activeSubTab = tabName;
    elements.subnavTabs.forEach(t => {
      t.classList.toggle('active', t.getAttribute('data-subtab') === tabName);
    });

    elements.paneDimensions.classList.toggle('hidden', tabName !== 'dimensions');
    elements.paneEvidence.classList.toggle('hidden', tabName !== 'evidence');
    elements.paneRuntime.classList.toggle('hidden', tabName !== 'runtime');
    elements.paneAi.classList.toggle('hidden', tabName !== 'ai');
  }

  /* ==========================================================================
     Quick Sample Buttons
     ========================================================================== */
  function initQuickSamples() {
    elements.quickSamples.forEach(chip => {
      chip.addEventListener('click', () => {
        elements.repoUrlInput.value = chip.getAttribute('data-url');
        elements.repoRefInput.value = chip.getAttribute('data-ref') || 'main';
      });
    });
  }

  /* ==========================================================================
     Submission & Evaluation Launch
     ========================================================================== */
  function initSubmission() {
    elements.submitForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const rawUrl = elements.repoUrlInput.value.trim();
      const ref = elements.repoRefInput.value.trim() || 'main';
      const enableAi = elements.aiToggle.checked;

      if (!rawUrl) {
        showToast('Please enter a valid GitHub repository URL', 'error');
        return;
      }

      elements.startBtn.disabled = true;
      elements.startBtnLabel.textContent = 'Enqueuing Evaluation...';

      try {
        // Step 1: Register or fetch repository
        const repoResp = await fetch('/api/v1/repositories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: rawUrl, provider: 'github' }),
        });

        if (!repoResp.ok) {
          const err = await repoResp.json();
          throw new Error(err.detail || 'Failed to register repository');
        }

        const repo = await repoResp.json();

        // Step 2: Enqueue evaluation
        const evalResp = await fetch('/api/v1/evaluations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            repository_id: repo.id,
            ref: ref,
            options: {
              timeout_seconds: 600,
              enable_ai_reasoning: enableAi,
            },
          }),
        });

        if (!evalResp.ok) {
          const err = await evalResp.json();
          throw new Error(err.detail || 'Failed to dispatch evaluation job');
        }

        const accepted = await evalResp.json();
        showToast(`Evaluation ${accepted.evaluation_id.slice(0, 8)} successfully queued`, 'success');

        // Start active tracking
        startTracking(accepted.evaluation_id, `${repo.owner} / ${repo.name}`);
      } catch (err) {
        showToast(err.message || 'Error communicating with RepoScore API', 'error');
      } finally {
        elements.startBtn.disabled = false;
        elements.startBtnLabel.textContent = 'Run Autonomous Evaluation';
      }
    });

    // Cancellation Button
    elements.cancelBtn.addEventListener('click', async () => {
      if (!state.currentEvaluationId) return;
      if (!confirm('Are you sure you want to cancel the active evaluation?')) return;

      try {
        const resp = await fetch(`/api/v1/evaluations/${state.currentEvaluationId}/cancel`, {
          method: 'POST',
        });
        if (resp.ok) {
          showToast('Cancellation signal dispatched', 'info');
        } else {
          const err = await resp.json();
          showToast(err.detail || 'Could not cancel evaluation', 'error');
        }
      } catch (err) {
        showToast('Cancellation request failed', 'error');
      }
    });
  }

  /* ==========================================================================
     Active Evaluation Tracking & Polling
     ========================================================================== */
  function startTracking(evaluationId, repoName) {
    state.currentEvaluationId = evaluationId;
    if (state.pollIntervalId) clearInterval(state.pollIntervalId);

    elements.trackingSection.classList.remove('hidden');
    elements.resultsContainer.classList.add('hidden');
    elements.trackerEvalId.textContent = `EVALUATION #${evaluationId.slice(0, 8)}`;
    elements.trackerRepoName.textContent = repoName;
    elements.trackerElapsedText.textContent = '0s elapsed';
    elements.progressBarFill.style.width = '10%';
    elements.trackerStatusMsg.textContent = 'Initializing isolated sandbox environment...';

    resetStepper();

    // Poll every 1.5 seconds
    state.pollIntervalId = setInterval(async () => {
      try {
        const resp = await fetch(`/api/v1/evaluations/${evaluationId}/status`);
        if (!resp.ok) return;

        const data = await resp.json();
        elements.trackerElapsedText.textContent = `${data.elapsed_seconds}s elapsed`;

        const percent = STEP_PROGRESS_PERCENT[data.status] || 25;
        elements.progressBarFill.style.width = `${percent}%`;
        elements.trackerStatusMsg.textContent = `Current step: ${data.current_step || data.status}`;

        updateStepper(data.status);

        if (data.is_terminal) {
          clearInterval(state.pollIntervalId);
          state.pollIntervalId = null;

          if (data.status === 'CANCELLED') {
            showToast('Evaluation was cancelled.', 'info');
            elements.trackerStatusMsg.textContent = 'Evaluation cancelled by user.';
            return;
          }

          // Terminal completion -> Fetch finalized results
          showToast(`Evaluation finished with status: ${data.status}`, 'success');
          loadFinalizedResults(evaluationId);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 1500);
  }

  function resetStepper() {
    elements.stepperItems.forEach(item => {
      item.classList.remove('active', 'completed');
    });
  }

  function updateStepper(currentStatus) {
    const activeIndex = STEP_ORDER.indexOf(currentStatus);
    elements.stepperItems.forEach((item, idx) => {
      const stepName = item.getAttribute('data-step');
      const stepIndex = STEP_ORDER.indexOf(stepName);

      if (stepName === currentStatus) {
        item.classList.add('active');
        item.classList.remove('completed');
      } else if (stepIndex < activeIndex) {
        item.classList.add('completed');
        item.classList.remove('active');
      } else {
        item.classList.remove('active', 'completed');
      }
    });
  }

  /* ==========================================================================
     Load Finalized Results (Scorecard, Evidence, Runtime, AI)
     ========================================================================== */
  async function loadFinalizedResults(evaluationId) {
    try {
      // 1. Fetch Master Evaluation & Scorecard
      const [evalResp, scoreResp, evResp, rtResp, aiResp] = await Promise.all([
        fetch(`/api/v1/evaluations/${evaluationId}`),
        fetch(`/api/v1/evaluations/${evaluationId}/score`),
        fetch(`/api/v1/evaluations/${evaluationId}/evidence`),
        fetch(`/api/v1/evaluations/${evaluationId}/runtime`),
        fetch(`/api/v1/evaluations/${evaluationId}/ai`),
      ]);

      const evalData = evalResp.ok ? await evalResp.json() : null;
      state.scorecard = scoreResp.ok ? await scoreResp.json() : null;
      state.evidenceItems = evResp.ok ? (await evResp.json()).items : [];
      state.runtimeTelemetry = rtResp.ok ? await rtResp.json() : null;
      state.aiInterpretation = aiResp.ok ? await aiResp.json() : null;

      elements.trackingSection.classList.add('hidden');
      elements.resultsContainer.classList.remove('hidden');

      renderScoreHero(evalData, state.scorecard);
      renderDimensionsGrid(state.scorecard);
      renderEvidenceList(state.evidenceItems);
      renderRuntimeTelemetry(state.runtimeTelemetry);
      renderAiGuidance(state.aiInterpretation);
    } catch (err) {
      console.error('Failed to load results:', err);
      showToast('Could not load all evaluation details', 'error');
    }
  }

  /* ==========================================================================
     Hero & Composite Scorecard Rendering
     ========================================================================== */
  function renderScoreHero(evalRecord, scorecard) {
    if (!scorecard) {
      elements.radialScoreNumber.textContent = '0.0';
      elements.compositeGradeBadge.textContent = 'F';
      elements.compositeGradeBadge.className = 'grade-badge grade-F';
      return;
    }

    const score = parseFloat(scorecard.overall_score) || 0;
    elements.radialScoreNumber.textContent = score.toFixed(1);

    // Radial Bar Stroke Dashoffset (Circumference ~ 440)
    const strokeOffset = Math.max(0, 440 - (440 * (score / 100)));
    elements.radialBar.style.strokeDashoffset = strokeOffset;

    // Grade Badge
    const grade = scorecard.grade || 'F';
    elements.compositeGradeBadge.textContent = grade;
    elements.compositeGradeBadge.className = `grade-badge grade-${grade.replace('+', '-plus')}`;

    // Meta details
    elements.evalStatusPill.textContent = evalRecord ? evalRecord.status : 'COMPLETED';
    if (evalRecord && evalRecord.duration_ms) {
      elements.resultDuration.textContent = `${(evalRecord.duration_ms / 1000).toFixed(1)}s`;
    } else {
      elements.resultDuration.textContent = 'Complete';
    }

    // Quick Stats
    elements.statTotalEvidence.textContent = state.evidenceItems.length;
    const critCount = state.evidenceItems.filter(e => e.severity === 'CRITICAL').length;
    elements.statCriticalCount.textContent = critCount;

    if (state.runtimeTelemetry) {
      elements.statRuntimeStrategy.textContent = state.runtimeTelemetry.evaluator_strategy.toUpperCase();
    }

    // Failure incident handling
    if (evalRecord && (evalRecord.status === 'BUILD_FAILED' || evalRecord.status === 'STARTUP_FAILED')) {
      elements.failureBanner.classList.remove('hidden');
      elements.failureBannerTitle.textContent = `Runtime Failure: ${evalRecord.status}`;
      elements.failureBannerText.textContent = evalRecord.error_summary || 'Compilation or health probes failed.';
    } else {
      elements.failureBanner.classList.add('hidden');
    }
  }

  /* ==========================================================================
     Dimensions & Receipts Rendering
     ========================================================================== */
  function renderDimensionsGrid(scorecard) {
    elements.dimensionsGrid.innerHTML = '';
    if (!scorecard || !scorecard.dimensions) return;

    scorecard.dimensions.forEach(dim => {
      const card = document.createElement('div');
      card.className = 'dimension-card';
      const dimScore = parseFloat(dim.score) || 0;
      const receiptCount = (dim.itemized_receipt || []).length;

      card.innerHTML = `
        <div class="dim-card-top">
          <span class="dim-name">${dim.dimension_name}</span>
          <span class="dim-weight">Weight: ${dim.weight}</span>
        </div>
        <div class="dim-score-row">
          <span class="dim-score-number">${dimScore.toFixed(1)}</span>
          <span class="dim-receipt-count">${receiptCount} receipt item${receiptCount === 1 ? '' : 's'}</span>
        </div>
        <div class="dim-bar-track">
          <div class="dim-bar-fill" style="width: ${dimScore}%;"></div>
        </div>
      `;

      card.addEventListener('click', () => {
        openReceiptDrawer(dim);
      });

      elements.dimensionsGrid.appendChild(card);
    });
  }

  function openReceiptDrawer(dim) {
    elements.drawerDimTitle.textContent = `${dim.dimension_name} Receipt`;
    elements.drawerCategoryPill.textContent = dim.dimension_name;
    elements.drawerScoreValue.textContent = parseFloat(dim.score).toFixed(1);
    elements.drawerWeightValue.textContent = dim.weight;

    elements.drawerReceiptList.innerHTML = '';
    const receipts = dim.itemized_receipt || [];

    if (receipts.length === 0) {
      elements.drawerReceiptList.innerHTML = `
        <div class="empty-state-notice" style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 2rem 0;">
          No deductions or credits applied. Clean baseline of 100.0 retained.
        </div>
      `;
    } else {
      receipts.forEach(r => {
        const item = document.createElement('div');
        item.className = 'receipt-item-box';
        const isDeduction = (r.type || 'DEDUCTION') === 'DEDUCTION';
        const deltaClass = isDeduction ? 'receipt-delta-deduction' : 'receipt-delta-credit';
        const deltaSign = isDeduction ? '-' : '+';

        item.innerHTML = `
          <div class="receipt-item-top">
            <span class="receipt-rule-code">${r.rule_code || 'RULE_EVIDENCE'}</span>
            <span class="receipt-delta-badge ${deltaClass}">${deltaSign}${Math.abs(parseFloat(r.calculated_delta || r.points)).toFixed(1)} pts</span>
          </div>
          <p class="receipt-desc">${r.description || 'Verified evidence deduction'}</p>
          <span class="receipt-evidence-link">Evidence ID: ${r.evidence_id || 'Deterministic Rule'}</span>
        `;
        elements.drawerReceiptList.appendChild(item);
      });
    }

    elements.receiptDrawerBackdrop.classList.remove('hidden');
  }

  function initReceiptDrawer() {
    elements.closeDrawerBtn.addEventListener('click', () => {
      elements.receiptDrawerBackdrop.classList.add('hidden');
    });

    elements.receiptDrawerBackdrop.addEventListener('click', (e) => {
      if (e.target === elements.receiptDrawerBackdrop) {
        elements.receiptDrawerBackdrop.classList.add('hidden');
      }
    });
  }

  /* ==========================================================================
     Evidence Explorer Rendering
     ========================================================================== */
  function renderEvidenceList(items) {
    elements.evidenceCounter.textContent = items.length;
    filterAndRenderEvidence();
  }

  function filterAndRenderEvidence() {
    const sevFilter = elements.filterSeverity.value;
    const catFilter = elements.filterCategory.value;
    const query = elements.searchEvidence.value.toLowerCase().trim();

    const filtered = state.evidenceItems.filter(item => {
      if (sevFilter && item.severity !== sevFilter) return false;
      if (catFilter && item.category !== catFilter) return false;
      if (query) {
        const matchesTitle = (item.title || '').toLowerCase().includes(query);
        const matchesDesc = (item.description || '').toLowerCase().includes(query);
        const matchesFile = item.location && (item.location.file_path || '').toLowerCase().includes(query);
        if (!matchesTitle && !matchesDesc && !matchesFile) return false;
      }
      return true;
    });

    elements.evidenceList.innerHTML = '';
    if (filtered.length === 0) {
      elements.evidenceList.innerHTML = `
        <div style="color: var(--text-muted); font-size: 0.9rem; text-align: center; padding: 2.5rem 0;">
          No verified evidence findings match the active criteria.
        </div>
      `;
      return;
    }

    filtered.forEach(ev => {
      const card = document.createElement('div');
      card.className = 'evidence-item-card';

      let locationHtml = '';
      if (ev.location && ev.location.file_path) {
        const lineInfo = ev.location.start_line ? `:${ev.location.start_line}` : '';
        locationHtml = `<span class="ev-location">${ev.location.file_path}${lineInfo}</span>`;
      }

      card.innerHTML = `
        <div class="ev-header">
          <div class="ev-title-group">
            <span class="ev-severity-badge sev-${ev.severity}">${ev.severity}</span>
            <span class="ev-title">${ev.title}</span>
          </div>
          <span class="ev-category-tag">${ev.category} (${ev.source})</span>
        </div>
        <p class="ev-desc">${ev.description}</p>
        ${locationHtml}
      `;
      elements.evidenceList.appendChild(card);
    });
  }

  function initEvidenceFilters() {
    elements.filterSeverity.addEventListener('change', filterAndRenderEvidence);
    elements.filterCategory.addEventListener('change', filterAndRenderEvidence);
    elements.searchEvidence.addEventListener('input', filterAndRenderEvidence);
  }

  /* ==========================================================================
     Runtime Telemetry Rendering
     ========================================================================== */
  function renderRuntimeTelemetry(telemetry) {
    if (!telemetry) {
      elements.rtStrategy.textContent = 'Generic Container';
      elements.rtBuildStatus.textContent = 'Not Executed';
      elements.rtStartupStatus.textContent = 'Not Executed';
      elements.rtLatency.textContent = 'N/A';
      return;
    }

    elements.rtStrategy.textContent = (telemetry.evaluator_strategy || 'GENERIC').toUpperCase();

    if (telemetry.build_success === true) {
      elements.rtBuildStatus.textContent = `PASS (Exit 0)`;
      elements.rtBuildStatus.style.color = 'var(--accent-emerald)';
    } else if (telemetry.build_success === false) {
      elements.rtBuildStatus.textContent = `FAILED (Exit ${telemetry.build_exit_code ?? 1})`;
      elements.rtBuildStatus.style.color = 'var(--accent-crimson)';
    } else {
      elements.rtBuildStatus.textContent = 'SKIPPED';
    }

    if (telemetry.startup_ready) {
      elements.rtStartupStatus.textContent = `READY (Port ${telemetry.startup_port || 8000})`;
      elements.rtStartupStatus.style.color = 'var(--accent-emerald)';
    } else {
      elements.rtStartupStatus.textContent = telemetry.startup_port ? 'HEALTH CHECK FAILED' : 'NOT STARTED';
    }

    if (telemetry.latency_p95_ms) {
      elements.rtLatency.textContent = `${telemetry.latency_p95_ms.toFixed(1)} ms`;
    } else {
      elements.rtLatency.textContent = 'N/A';
    }
  }

  /* ==========================================================================
     AI Advisory Interpretation Rendering
     ========================================================================== */
  function renderAiGuidance(ai) {
    if (!ai) {
      elements.aiExecSummary.textContent = 'AI advisory reasoning was skipped or unavailable for this evaluation.';
      elements.aiArchAssessment.textContent = 'No qualitative architectural critique generated.';
      elements.aiSecurityNarrative.textContent = 'No qualitative security synthesis generated.';
      elements.aiRecsContainer.innerHTML = '';
      return;
    }

    elements.aiModelName.textContent = `${ai.provider.toUpperCase()} (${ai.model_name})`;
    elements.aiExecSummary.textContent = ai.executive_summary;
    elements.aiArchAssessment.textContent = ai.architectural_assessment;
    elements.aiSecurityNarrative.textContent = ai.security_risk_narrative;

    elements.aiRecsContainer.innerHTML = '';
    const recs = ai.recommendations || [];

    if (recs.length === 0) {
      elements.aiRecsContainer.innerHTML = `
        <div style="color: var(--text-muted); font-size: 0.85rem;">No remediation recommendations returned.</div>
      `;
    } else {
      recs.forEach(rec => {
        const card = document.createElement('div');
        card.className = 'recommendation-card';

        let stepsHtml = '';
        if (rec.actionable_steps && rec.actionable_steps.length > 0) {
          stepsHtml = `<ul class="rec-steps">${rec.actionable_steps.map(s => `<li>${s}</li>`).join('')}</ul>`;
        }

        card.innerHTML = `
          <div class="rec-header">
            <h5 class="rec-title">${rec.title}</h5>
            <span class="rec-priority-badge sev-${rec.priority || 'MEDIUM'}">${rec.priority || 'MEDIUM'}</span>
          </div>
          <p class="rec-explanation">${rec.explanation}</p>
          ${stepsHtml}
        `;
        elements.aiRecsContainer.appendChild(card);
      });
    }
  }

  /* ==========================================================================
     Evaluation History Loading
     ========================================================================== */
  async function loadEvaluationHistory() {
    try {
      elements.historyTableBody.innerHTML = `
        <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading evaluation history...</td></tr>
      `;

      const resp = await fetch('/api/v1/evaluations?limit=25');
      if (!resp.ok) throw new Error('Failed to fetch history');

      const data = await resp.json();
      elements.historyTableBody.innerHTML = '';

      if (data.length === 0) {
        elements.historyTableBody.innerHTML = `
          <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem 0;">No previous evaluations recorded.</td></tr>
        `;
        return;
      }

      data.forEach(item => {
        const row = document.createElement('tr');
        const scoreDisplay = item.overall_score ? parseFloat(item.overall_score).toFixed(1) : '--';
        const gradeDisplay = item.grade || '--';
        const timeDisplay = new Date(item.created_at).toLocaleString();

        row.innerHTML = `
          <td style="font-family: var(--font-mono);">${item.id.slice(0, 8)}...</td>
          <td><span class="pill-tag pill-status">${item.status}</span></td>
          <td style="font-weight: 700;">${scoreDisplay}</td>
          <td><span class="grade-badge" style="font-size: 0.8rem; padding: 0.15rem 0.6rem;">${gradeDisplay}</span></td>
          <td style="color: var(--text-muted); font-size: 0.8rem;">${timeDisplay}</td>
          <td>
            <button class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.7rem;" data-load-id="${item.id}">
              Inspect
            </button>
          </td>
        `;

        row.querySelector('button').addEventListener('click', () => {
          elements.navDashboard.click();
          loadFinalizedResults(item.id);
        });

        elements.historyTableBody.appendChild(row);
      });
    } catch (err) {
      elements.historyTableBody.innerHTML = `
        <tr><td colspan="6" style="text-align: center; color: var(--accent-crimson);">Error loading evaluation history.</td></tr>
      `;
    }
  }

  /* ==========================================================================
     Application Initialization
     ========================================================================== */
  document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initQuickSamples();
    initSubmission();
    initReceiptDrawer();
    initEvidenceFilters();

    if (elements.refreshHistoryBtn) {
      elements.refreshHistoryBtn.addEventListener('click', loadEvaluationHistory);
    }
  });

})();
