/**
 * Free AI Selector - JavaScript
 * Логика взаимодействия с API
 */

// ============================================
// Конфигурация
// ============================================
const API_BASE = '';

// ============================================
// Утилиты
// ============================================

async function apiCall(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || `Ошибка API: ${response.status}`);
    }

    return data;
}

function show(element) {
    element.classList.remove('hidden');
}

function hide(element) {
    element.classList.add('hidden');
}

function formatTime(seconds) {
    if (seconds === null || seconds === undefined) return '—';
    return `${seconds.toFixed(2)}с`;
}

function formatPercent(value) {
    if (value === null || value === undefined) return '—';
    return `${(value * 100).toFixed(1)}%`;
}

function getMedal(rank) {
    switch (rank) {
        case 1: return '🥇';
        case 2: return '🥈';
        case 3: return '🥉';
        default: return '';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Вкладки
// ============================================

function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const panes = document.querySelectorAll('.tab-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.tab;

            // Убрать active со всех
            tabs.forEach(t => t.classList.remove('active'));
            panes.forEach(p => {
                p.classList.remove('active');
                p.classList.add('hidden');
            });

            // Активировать выбранную
            tab.classList.add('active');
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add('active');
                targetPane.classList.remove('hidden');
            }

            // Загрузить данные при переключении на Рейтинг
            if (targetId === 'stats') {
                loadStats();
            }
        });
    });
}

// ============================================
// Чат с AI
// ============================================

async function sendPrompt() {
    const input = document.getElementById('prompt-input');
    const sendBtn = document.getElementById('send-btn');
    const sendBtnText = document.getElementById('send-btn-text');
    const sendBtnLoader = document.getElementById('send-btn-loader');
    const responseBox = document.getElementById('chat-response');
    const errorBox = document.getElementById('chat-error');

    const prompt = input.value.trim();

    if (!prompt) {
        showError(errorBox, 'Введите текст запроса');
        return;
    }

    // Показать загрузку
    sendBtn.disabled = true;
    hide(sendBtnText);
    show(sendBtnLoader);
    hide(responseBox);
    hide(errorBox);

    try {
        const data = await apiCall('/api/v1/prompts/process', {
            method: 'POST',
            body: JSON.stringify({ prompt })
        });

        // Показать результат
        document.getElementById('response-model').textContent = data.selected_model || 'Неизвестно';
        document.getElementById('response-provider').textContent = data.provider || 'Неизвестно';
        document.getElementById('response-time').textContent = formatTime(data.response_time_seconds);
        document.getElementById('response-text').textContent = data.response || 'Нет ответа';

        show(responseBox);
    } catch (error) {
        showError(errorBox, error.message);
    } finally {
        sendBtn.disabled = false;
        show(sendBtnText);
        hide(sendBtnLoader);
    }
}

// ============================================
// Статистика моделей
// ============================================

async function loadStats() {
    const tbody = document.getElementById('stats-tbody');
    const loader = document.getElementById('stats-loader');
    const tableContainer = document.getElementById('stats-table-container');
    const errorBox = document.getElementById('stats-error');
    const refreshBtn = document.getElementById('refresh-stats-btn');

    // Показать загрузку
    show(loader);
    hide(tableContainer);
    hide(errorBox);
    if (refreshBtn) refreshBtn.style.animation = 'spin 0.8s linear infinite';

    try {
        const data = await apiCall('/api/v1/models/stats');

        tbody.innerHTML = '';

        const models = (data.models || []).sort((a, b) =>
            (b.reliability_score || 0) - (a.reliability_score || 0)
        );

        models.forEach((model, index) => {
            const rank = index + 1;
            const row = document.createElement('tr');

            row.innerHTML = `
                <td class="rank-cell">
                    <span class="medal">${getMedal(rank)}</span>
                    ${rank > 3 ? rank : ''}
                </td>
                <td>${escapeHtml(model.name || '—')}</td>
                <td>${escapeHtml(model.provider || '—')}</td>
                <td class="score-cell">${model.reliability_score?.toFixed(2) || '—'}</td>
                <td>${formatPercent(model.success_rate)}</td>
            `;

            tbody.appendChild(row);
        });

        if (models.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #666;">Нет данных</td></tr>';
        }

        show(tableContainer);
    } catch (error) {
        showError(errorBox, error.message);
    } finally {
        hide(loader);
        if (refreshBtn) refreshBtn.style.animation = '';
    }
}

// ============================================
// Тестирование провайдеров
// ============================================

async function testProviders() {
    const testBtn = document.getElementById('test-providers-btn');
    const testBtnText = document.getElementById('test-btn-text');
    const testBtnLoader = document.getElementById('test-btn-loader');
    const resultsContainer = document.getElementById('providers-results');
    const summaryDiv = document.getElementById('providers-summary');
    const listDiv = document.getElementById('providers-list');
    const errorBox = document.getElementById('providers-error');

    // Показать загрузку
    testBtn.disabled = true;
    hide(testBtnText);
    show(testBtnLoader);
    hide(resultsContainer);
    hide(errorBox);

    try {
        const data = await apiCall('/api/v1/providers/test', {
            method: 'POST'
        });

        summaryDiv.innerHTML = `
            <span style="color: var(--success);">✓ ${data.successful || 0}</span> /
            <span style="color: var(--error);">✗ ${data.failed || 0}</span>
            из ${data.total_providers || 0} провайдеров
        `;

        listDiv.innerHTML = '';

        const results = data.results || [];
        results.forEach(result => {
            const isSuccess = result.status === 'success';
            const item = document.createElement('div');
            item.className = `provider-item ${isSuccess ? 'success' : 'error'}`;

            item.innerHTML = `
                <div class="provider-info">
                    <span class="provider-name">${escapeHtml(result.provider || '—')}</span>
                    <span class="provider-model">${escapeHtml(result.model || '—')}</span>
                </div>
                <div class="provider-status">
                    ${isSuccess
                        ? `<span style="color: var(--success);">✓</span>
                           <span class="provider-time">${formatTime(result.response_time)}</span>`
                        : `<span style="color: var(--error);">✗</span>
                           <span class="provider-error" title="${escapeHtml(result.error || '')}">${escapeHtml(result.error || 'Ошибка')}</span>`
                    }
                </div>
            `;

            listDiv.appendChild(item);
        });

        show(resultsContainer);
    } catch (error) {
        showError(errorBox, error.message);
    } finally {
        testBtn.disabled = false;
        show(testBtnText);
        hide(testBtnLoader);
    }
}

// ============================================
// Проверка здоровья
// ============================================

async function checkHealth() {
    const statusIcon = document.getElementById('status-icon');
    const statusText = document.getElementById('status-text');

    try {
        const data = await apiCall('/health');

        if (data.status === 'healthy') {
            statusIcon.className = 'status-dot online';
            statusText.textContent = 'Онлайн';
        } else {
            statusIcon.className = 'status-dot offline';
            statusText.textContent = 'Проблемы';
        }
    } catch (error) {
        statusIcon.className = 'status-dot offline';
        statusText.textContent = 'Оффлайн';
    }
}

// ============================================
// Обработка ошибок
// ============================================

function showError(errorBox, message) {
    errorBox.textContent = message;
    show(errorBox);
}

// ============================================
// Инициализация
// ============================================

function init() {
    initTabs();
    checkHealth();
    setInterval(checkHealth, 30000);
}

// Обработчики
document.addEventListener('DOMContentLoaded', init);

// Enter для отправки
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('prompt-input');
    if (input) {
        input.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                sendPrompt();
            }
        });
    }
});
