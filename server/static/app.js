const state = {
  tasks: [],
  sessionId: null,
  session: null,
  selectedEmailId: null,
  autoPlay: false,
};

const elements = {
  taskSelect: document.getElementById("task-select"),
  newSessionBtn: document.getElementById("new-session-btn"),
  taskTitle: document.getElementById("task-title"),
  taskDescription: document.getElementById("task-description"),
  metricScore: document.getElementById("metric-score"),
  metricSteps: document.getElementById("metric-steps"),
  metricResolved: document.getElementById("metric-resolved"),
  queueCount: document.getElementById("queue-count"),
  emailList: document.getElementById("email-list"),
  focusSubject: document.getElementById("focus-subject"),
  focusPriority: document.getElementById("focus-priority"),
  focusMeta: document.getElementById("focus-meta"),
  focusBody: document.getElementById("focus-body"),
  recommendationText: document.getElementById("recommendation-text"),
  useSuggestionBtn: document.getElementById("use-suggestion-btn"),
  autoPlayBtn: document.getElementById("auto-play-btn"),
  actionForm: document.getElementById("action-form"),
  actionType: document.getElementById("action-type"),
  priority: document.getElementById("priority"),
  responseText: document.getElementById("response-text"),
  delegateTo: document.getElementById("delegate-to"),
  snoozeUntil: document.getElementById("snooze-until"),
  scheduledTime: document.getElementById("scheduled-time"),
  rationale: document.getElementById("rationale"),
  historyList: document.getElementById("history-list"),
  historyState: document.getElementById("history-state"),
};

const priorityColors = {
  urgent: "#c43d22",
  important: "#f05a28",
  low: "#5b6f64",
  spam: "#7a7a7a",
};

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || `Request failed with ${response.status}`);
  }

  return response.json();
}

async function loadTasks() {
  state.tasks = await fetchJSON("/ui/tasks");
  elements.taskSelect.innerHTML = state.tasks
    .map(
      (task) =>
        `<option value="${task.name}">${task.name.toUpperCase()} · ${task.email_count} emails</option>`,
    )
    .join("");
}

async function createSession(taskName) {
  const payload = await fetchJSON("/ui/session", {
    method: "POST",
    body: JSON.stringify({ task_name: taskName }),
  });
  state.sessionId = payload.session_id;
  state.session = payload;
  state.selectedEmailId = payload.current_emails[0]?.id || null;
  render();
}

function render() {
  const session = state.session;
  if (!session) {
    return;
  }

  document.body.classList.toggle("is-complete", Boolean(session.completed));
  elements.taskTitle.textContent = `${session.task_name.toUpperCase()} mode`;
  elements.taskDescription.textContent = session.task_description;
  elements.metricScore.textContent = `${session.progress_percent}%`;
  elements.metricSteps.textContent = `${session.steps_taken} / ${session.max_steps}`;
  elements.metricResolved.textContent = `${session.resolved_count} / ${session.total_emails}`;
  elements.queueCount.textContent = `${session.current_emails.length} open`;
  elements.historyState.textContent = session.completed
    ? "Scenario complete"
    : `${session.remaining_actions} actions remaining`;

  renderEmails(session.current_emails);
  renderFocus(session.current_emails);
  renderRecommendation(session.recommended_action, session.completed);
  renderHistory(session.action_history);
  syncFormToSelection();
  updateConditionalFields();
}

function renderEmails(emails) {
  if (!emails.length) {
    elements.emailList.innerHTML = `<div class="empty-state">Every message has been handled. Start a new scenario or replay the current one.</div>`;
    return;
  }

  if (!emails.find((email) => email.id === state.selectedEmailId)) {
    state.selectedEmailId = emails[0].id;
  }

  elements.emailList.innerHTML = emails
    .map((email, index) => {
      const activeClass = email.id === state.selectedEmailId ? "active" : "";
      const preview = email.body.length > 110 ? `${email.body.slice(0, 110)}...` : email.body;
      return `
        <button
          class="email-item ${activeClass}"
          data-email-id="${email.id}"
          style="animation-delay: ${index * 60}ms; --priority-color: ${priorityColors[email.priority_hint] || "#999"}"
        >
          <div class="email-topline">
            <span>${email.sender}</span>
            <span>${email.timestamp.slice(0, 10)}</span>
          </div>
          <h4>${email.subject}</h4>
          <div class="email-preview">${preview}</div>
        </button>
      `;
    })
    .join("");

  elements.emailList.querySelectorAll(".email-item").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedEmailId = button.dataset.emailId;
      render();
    });
  });
}

function renderFocus(emails) {
  const email = emails.find((item) => item.id === state.selectedEmailId);
  if (!email) {
    elements.focusSubject.textContent = "Inbox clear";
    elements.focusPriority.textContent = "Complete";
    elements.focusPriority.style.background = "rgba(42, 140, 109, 0.12)";
    elements.focusPriority.style.color = "#2a8c6d";
    elements.focusMeta.innerHTML = "";
    elements.focusBody.textContent = "No active email remains in this scenario.";
    return;
  }

  elements.focusSubject.textContent = email.subject;
  elements.focusPriority.textContent = email.priority_hint;
  elements.focusPriority.style.background = `${priorityColors[email.priority_hint] || "#999"}20`;
  elements.focusPriority.style.color = priorityColors[email.priority_hint] || "#444";
  elements.focusMeta.innerHTML = `
    <span>${email.sender}</span>
    <span>${email.timestamp}</span>
    <span>${email.thread_id || "single message"}</span>
  `;
  elements.focusBody.textContent = email.body;
}

function renderRecommendation(action, completed) {
  if (completed) {
    elements.recommendationText.textContent = "This scenario is complete. Start a fresh session or switch difficulty to keep exploring.";
    return;
  }

  if (!action) {
    elements.recommendationText.textContent = "No recommendation is available yet.";
    return;
  }

  const details = [
    action.action_type,
    action.priority || "no priority",
    action.delegate_to || action.scheduled_time || action.snooze_until || "",
  ]
    .filter(Boolean)
    .join(" · ");
  elements.recommendationText.textContent = `${action.email_id} · ${details}`;
}

function renderHistory(history) {
  if (!history.length) {
    elements.historyList.innerHTML = `<div class="empty-state">No actions yet. Use the suggestion engine or compose a move manually.</div>`;
    return;
  }

  elements.historyList.innerHTML = history
    .slice()
    .reverse()
    .map((action, index) => {
      const meta =
        action.delegate_to || action.scheduled_time || action.snooze_until || action.priority || "direct";
      const summary = action.response_text || action.rationale || "No supporting copy added.";
      return `
        <div class="history-item">
          <div class="history-index">${history.length - index}</div>
          <div class="history-copy">
            <strong>${action.action_type.toUpperCase()} · ${action.email_id}</strong>
            <span>${summary}</span>
          </div>
          <div class="history-meta">${meta}</div>
        </div>
      `;
    })
    .join("");
}

function syncFormToSelection() {
  const email = state.session?.current_emails.find((item) => item.id === state.selectedEmailId);
  if (!email) {
    elements.actionForm.reset();
    return;
  }

  if (!elements.priority.value) {
    elements.priority.value = email.priority_hint || "";
  }
}

function fillFormFromAction(action) {
  if (!action) {
    return;
  }

  state.selectedEmailId = action.email_id;
  elements.actionType.value = action.action_type || "classify";
  elements.priority.value = action.priority || "";
  elements.responseText.value = action.response_text || "";
  elements.delegateTo.value = action.delegate_to || "";
  elements.snoozeUntil.value = action.snooze_until || "";
  elements.scheduledTime.value = action.scheduled_time || "";
  elements.rationale.value = action.rationale || "";
  updateConditionalFields();
  render();
}

function updateConditionalFields() {
  const actionType = elements.actionType.value;
  const visibility = {
    response_text: ["respond", "delegate", "schedule", "snooze"].includes(actionType),
    delegate_to: actionType === "delegate",
    snooze_until: actionType === "snooze",
    scheduled_time: actionType === "schedule",
  };

  document.querySelectorAll(".conditional").forEach((node) => {
    const field = node.dataset.field;
    node.classList.toggle("hidden", !visibility[field]);
  });
}

async function submitCurrentAction(event) {
  event.preventDefault();
  if (!state.sessionId || !state.selectedEmailId) {
    return;
  }

  const action = {
    action_type: elements.actionType.value,
    email_id: state.selectedEmailId,
  };

  if (elements.priority.value) {
    action.priority = elements.priority.value;
  }
  if (elements.responseText.value.trim()) {
    action.response_text = elements.responseText.value.trim();
  }
  if (elements.delegateTo.value.trim()) {
    action.delegate_to = elements.delegateTo.value.trim();
  }
  if (elements.snoozeUntil.value.trim()) {
    action.snooze_until = elements.snoozeUntil.value.trim();
  }
  if (elements.scheduledTime.value.trim()) {
    action.scheduled_time = elements.scheduledTime.value.trim();
  }
  if (elements.rationale.value.trim()) {
    action.rationale = elements.rationale.value.trim();
  }

  const payload = await fetchJSON(`/ui/session/${state.sessionId}/action`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
  state.session = payload;
  state.selectedEmailId = payload.current_emails[0]?.id || null;
  elements.actionForm.reset();
  render();
}

async function autoPlayDemo() {
  if (!state.session || state.autoPlay) {
    return;
  }

  state.autoPlay = true;
  elements.autoPlayBtn.textContent = "Playing...";

  try {
    while (
      state.autoPlay &&
      state.session &&
      !state.session.completed &&
      state.session.recommended_action
    ) {
      fillFormFromAction(state.session.recommended_action);
      await submitCurrentAction(new Event("submit"));
      await new Promise((resolve) => setTimeout(resolve, 420));
    }
  } finally {
    state.autoPlay = false;
    elements.autoPlayBtn.textContent = "Auto-Play Demo";
  }
}

function bindEvents() {
  elements.newSessionBtn.addEventListener("click", () => createSession(elements.taskSelect.value));
  elements.taskSelect.addEventListener("change", () => createSession(elements.taskSelect.value));
  elements.useSuggestionBtn.addEventListener("click", () => fillFormFromAction(state.session?.recommended_action));
  elements.autoPlayBtn.addEventListener("click", autoPlayDemo);
  elements.actionType.addEventListener("change", updateConditionalFields);
  elements.actionForm.addEventListener("submit", submitCurrentAction);
}

async function init() {
  await loadTasks();
  bindEvents();
  await createSession(elements.taskSelect.value || "easy");
}

init().catch((error) => {
  console.error(error);
  elements.taskDescription.textContent = error.message;
});
