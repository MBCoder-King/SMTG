const API = '';

const screens = {
  onboarding: document.getElementById('onboarding-screen'),
  home: document.getElementById('home-screen'),
  insights: document.getElementById('insights-screen'),
  focus: document.getElementById('focus-screen'),
  settings: document.getElementById('settings-screen'),
  subscription: document.getElementById('subscription-screen')
};

const navItems = document.querySelectorAll('.nav-item');
const tabButtons = document.querySelectorAll('[data-tab]');
const ringFg = document.getElementById('ring-fg');
const nudgeSheet = document.getElementById('nudge-sheet');
const bottomNav = document.getElementById('bottom-nav');

let focusInterval;
let remaining = 15 * 60;
let onboardingStep = 1;
let selectedGoal = 120;

function setScreen(tab) {
  Object.entries(screens).forEach(([k, el]) => el.classList.toggle('active', k === tab));
  navItems.forEach((el) => el.classList.toggle('active', el.dataset.tab === tab));
  bottomNav.classList.toggle('hidden', ['onboarding', 'subscription'].includes(tab));
}

function minutesLabel(totalMin) {
  if (totalMin >= 60) {
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    return `${h}h ${m}m`;
  }
  return `${totalMin}m`;
}

function updateRing(used, goal) {
  const ratio = Math.max(0, Math.min(1, used / goal));
  const circumference = 2 * Math.PI * 78;
  ringFg.style.strokeDasharray = `${circumference}`;
  ringFg.style.strokeDashoffset = `${circumference - ratio * circumference}`;
  ringFg.style.stroke = ratio < 0.5 ? '#2ECC71' : '#F4A261';
}

function setTheme(theme) {
  document.body.dataset.theme = theme;
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function apiSend(path, method, body) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.error || `${method} ${path} failed`);
  }
  return res.json();
}

function renderBehavior(behavior) {
  document.getElementById('behavior-risk').textContent = `Risk: ${behavior.risk_level}`;
  document.getElementById('behavior-summary').textContent =
    `Scroll ratio: ${behavior.scroll_ratio_pct}% · Productive ratio: ${behavior.productive_ratio_pct}%`;
  const ul = document.getElementById('behavior-recos');
  ul.innerHTML = '';
  behavior.recommendations.forEach((recommendation) => {
    const li = document.createElement('li');
    li.textContent = recommendation;
    ul.appendChild(li);
  });
}

function renderIntegrations(integrations) {
  const list = document.getElementById('integration-list');
  list.innerHTML = '';
  Object.entries(integrations).forEach(([name, value]) => {
    const row = document.createElement('div');
    row.className = 'integration-row';
    row.innerHTML = `<strong>${name.replace('_', ' ')}</strong><span class="caption">${value.supported}</span>`;

    const detail = document.createElement('p');
    detail.className = 'caption';
    detail.textContent = `${value.method} — ${value.note}`;
    list.appendChild(row);
    list.appendChild(detail);
  });
}

async function loadDashboard() {
  const [{ dashboard }, { insights }, { behavior }] = await Promise.all([
    apiGet('/api/dashboard'),
    apiGet('/api/insights'),
    apiGet('/api/behavior/analyze')
  ]);

  document.getElementById('welcome-name').textContent = dashboard.name;
  document.getElementById('focus-score').textContent = `Focus ${dashboard.focus_score}/100`;
  document.getElementById('used-time').textContent = minutesLabel(dashboard.used_minutes);
  document.getElementById('goal-text').textContent = `of ${dashboard.goal_minutes}m goal`;
  document.getElementById('status-line').textContent = dashboard.used_minutes < dashboard.goal_minutes
    ? "You're doing great today."
    : 'You crossed today\'s goal, recover with a focus session.';
  document.getElementById('ai-home-insight').textContent = insights.ai_sentence;
  document.getElementById('streak-text').textContent = `Focus streak: ${dashboard.streak_days} days`;

  updateRing(dashboard.used_minutes, dashboard.goal_minutes);
  renderBehavior(behavior);

  const bars = document.getElementById('weekly-bars');
  bars.innerHTML = '';
  const max = Math.max(...insights.weekly_minutes, 1);
  insights.weekly_minutes.forEach((m) => {
    const bar = document.createElement('div');
    bar.style.setProperty('--h', `${Math.max(10, (m / max) * 100)}%`);
    bars.appendChild(bar);
  });

  const points = insights.time_saved_weekly;
  const maxP = Math.max(...points, 1);
  const step = 280 / (points.length - 1);
  const path = points.map((p, i) => {
    const x = 10 + i * step;
    const y = 100 - (p / maxP) * 70;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');
  document.getElementById('saved-path').setAttribute('d', path);
  document.getElementById('saved-dot').setAttribute('cx', String(10 + (points.length - 1) * step));
  document.getElementById('saved-dot').setAttribute('cy', String(100 - (points[points.length - 1] / maxP) * 70));
  document.getElementById('accept-rate').textContent = `Nudge accept ${insights.nudge_accept_rate}%`;
}

async function loadSettings() {
  const [{ profile }, { settings }, { subscription }, { integrations }] = await Promise.all([
    apiGet('/api/profile'),
    apiGet('/api/settings'),
    apiGet('/api/subscription'),
    apiGet('/api/integrations')
  ]);

  document.getElementById('profile-name').value = profile.name;
  document.getElementById('profile-goal').value = profile.goal_minutes;
  document.getElementById('study-mode').checked = !!settings.study_mode;
  document.getElementById('work-mode').checked = !!settings.work_mode;
  document.getElementById('sleep-mode').checked = !!settings.sleep_mode;
  document.getElementById('theme-select').value = settings.theme;
  document.getElementById('plan-name').textContent = subscription.plan.toUpperCase();
  document.getElementById('trial-text').textContent = subscription.plan === 'pro'
    ? 'Pro analytics and themes are active.'
    : 'Upgrade to unlock advanced analytics and heatmap.';

  setTheme(settings.theme);
  renderIntegrations(integrations);

  if (!settings.onboarding_done) {
    setScreen('onboarding');
    showOnboardingStep(1);
  } else {
    setScreen('home');
  }
}

function showOnboardingStep(step) {
  onboardingStep = Math.max(1, Math.min(4, step));
  document.querySelectorAll('.onboarding-step').forEach((el) => {
    el.classList.toggle('active', Number(el.dataset.step) === onboardingStep);
  });
  document.getElementById('onboarding-pagination').textContent = `${onboardingStep} / 4`;
}

async function saveSettings() {
  const name = document.getElementById('profile-name').value.trim() || 'User';
  const goal = Number(document.getElementById('profile-goal').value || 120);
  const payload = {
    study_mode: document.getElementById('study-mode').checked ? 1 : 0,
    work_mode: document.getElementById('work-mode').checked ? 1 : 0,
    sleep_mode: document.getElementById('sleep-mode').checked ? 1 : 0,
    nudge_enabled: 1,
    nudge_threshold_min: 18,
    theme: document.getElementById('theme-select').value,
    onboarding_done: 1
  };

  await apiSend('/api/profile', 'PUT', {
    name,
    goal_minutes: goal,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  });
  await apiSend('/api/settings', 'PUT', payload);
  setTheme(payload.theme);
}

function startFocusCountdown() {
  clearInterval(focusInterval);
  remaining = 15 * 60;
  setScreen('focus');
  const timer = document.getElementById('focus-timer');
  timer.textContent = '15:00';

  focusInterval = setInterval(() => {
    remaining -= 1;
    const mm = String(Math.floor(remaining / 60)).padStart(2, '0');
    const ss = String(remaining % 60).padStart(2, '0');
    timer.textContent = `${mm}:${ss}`;
    if (remaining <= 0) {
      clearInterval(focusInterval);
      endFocusSession(true);
    }
  }, 1000);
}

async function endFocusSession(completed) {
  clearInterval(focusInterval);
  await apiSend('/api/focus-sessions', 'POST', {
    planned_min: 15,
    completed_min: completed ? 15 : Math.max(1, 15 - Math.floor(remaining / 60)),
    accepted_from_nudge: 0
  });
  await apiSend('/api/sessions', 'POST', {
    app_name: 'SMTG Focus',
    session_type: 'focus',
    duration_min: 15,
    productive: 1
  });
  document.getElementById('focus-timer').textContent = '15:00';
  setScreen('home');
  await loadDashboard();
}

navItems.forEach((btn) => btn.addEventListener('click', () => setScreen(btn.dataset.tab)));
tabButtons.forEach((btn) => btn.addEventListener('click', () => setScreen(btn.dataset.tab)));
document.getElementById('go-subscription').addEventListener('click', () => setScreen('subscription'));
document.getElementById('onboarding-next').addEventListener('click', () => showOnboardingStep(2));

Array.from(document.querySelectorAll('.goal-card')).forEach((btn) => {
  btn.addEventListener('click', () => {
    Array.from(document.querySelectorAll('.goal-card')).forEach((b) => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedGoal = Number(btn.dataset.goal);
    showOnboardingStep(4);
  });
});

document.getElementById('onboarding-finish').addEventListener('click', async () => {
  try {
    document.getElementById('profile-goal').value = selectedGoal;
    await saveSettings();
    await loadDashboard();
    setScreen('home');
  } catch (e) {
    document.getElementById('onboarding-pagination').textContent = `Setup failed: ${e.message}`;
  }
});

document.getElementById('theme-select').addEventListener('change', (e) => setTheme(e.target.value));
document.getElementById('save-settings').addEventListener('click', async () => {
  const msg = document.getElementById('save-msg');
  try {
    await saveSettings();
    await loadDashboard();
    msg.textContent = 'Saved successfully.';
  } catch (e) {
    msg.textContent = `Failed to save: ${e.message}`;
  }
});

document.getElementById('export-data').addEventListener('click', async () => {
  const data = await apiGet('/api/export');
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'smtg-export.json';
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById('delete-data').addEventListener('click', async () => {
  if (!window.confirm('Delete all activity data?')) return;
  await fetch('/api/data', { method: 'DELETE' });
  await loadDashboard();
});

document.getElementById('upgrade-pro').addEventListener('click', async () => {
  await apiSend('/api/subscription', 'PUT', { plan: 'pro' });
  await loadSettings();
});

document.getElementById('downgrade-free').addEventListener('click', async () => {
  await apiSend('/api/subscription', 'PUT', { plan: 'free' });
  await loadSettings();
});

document.getElementById('start-focus').addEventListener('click', startFocusCountdown);
document.getElementById('end-focus').addEventListener('click', () => endFocusSession(false));

setTimeout(() => nudgeSheet.classList.add('visible'), 1500);

document.getElementById('nudge-start').addEventListener('click', async () => {
  await apiSend('/api/nudges', 'POST', { trigger_reason: 'scroll_threshold', response: 'start_focus' });
  nudgeSheet.classList.remove('visible');
  startFocusCountdown();
});

document.getElementById('nudge-snooze').addEventListener('click', async () => {
  await apiSend('/api/nudges', 'POST', { trigger_reason: 'scroll_threshold', response: 'snooze' });
  nudgeSheet.classList.remove('visible');
});

document.getElementById('nudge-dismiss').addEventListener('click', async () => {
  await apiSend('/api/nudges', 'POST', { trigger_reason: 'scroll_threshold', response: 'dismiss' });
  nudgeSheet.classList.remove('visible');
});

async function boot() {
  try {
    await apiGet('/api/health');
    await loadSettings();
    await loadDashboard();
  } catch (e) {
    setScreen('home');
    document.getElementById('status-line').textContent = `Backend unavailable: ${e.message}`;
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => null);
  }
}

boot();
