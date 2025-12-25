/**
 * JavaScript для веб-интерфейса Free AI Selector
 * Обеспечивает взаимодействие с API endpoints
 */

// ============================================
// Конфигурация
// ============================================

// Базовый URL — пустая строка для same-origin запросов
const API_BASE = '';

// ============================================
// Утилиты
// ============================================

/**
 * Универсальная функция для API вызовов
 * @param {string} endpoint - URL эндпоинта
 * @param {Object} options - Опции fetch
 * @returns {Promise<Object>} - JSON ответ
 */
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

/**
 * Показать элемент
 * @param {HTMLElement} element - DOM элемент
 */
function show(element) {
    element.classList.remove('hidden');
}

/**
 * Скрыть элемент
 * @param {HTMLElement} element - DOM элемент
 */
function hide(element) {
    element.classList.add('hidden');
}

/**
 * Форматировать время в секундах
 * @param {number} seconds - Время в секундах
 * @returns {string} - Отформатированное время
 */
function formatTime(seconds) {
    if (seconds === null || seconds === undefined) return '—';
    return `${seconds.toFixed(2)}с`;
}

/**
 * Форматировать процент
 * @param {number} value - Значение от 0 до 1
 * @returns {string} - Процент
 */
function formatPercent(value) {
    if (value === null || value === undefined) return '—';
    return `${(value * 100).toFixed(1)}%`;
}

/**
 * Получить медаль для места в рейтинге
 * @param {number} rank - Место (1, 2, 3)
 * @returns {string} - Эмодзи медали или пустая строка
 */
function getMedal(rank) {
    switch (rank) {
        case 1: return '🥇';
        case 2: return '🥈';
        case 3: return '🥉';
        default: return '';
    }
}

// ============================================
// Чат с AI
// ============================================

/**
 * Отправить промпт к AI
 */
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
        // Скрыть загрузку
        sendBtn.disabled = false;
        show(sendBtnText);
        hide(sendBtnLoader);
    }
}

// ============================================
// Статистика моделей
// ============================================

/**
 * Загрузить статистику моделей
 */
async function loadStats() {
    const tbody = document.getElementById('stats-tbody');
    const loader = document.getElementById('stats-loader');
    const tableContainer = document.getElementById('stats-table-container');
    const errorBox = document.getElementById('stats-error');
    const refreshIcon = document.getElementById('refresh-icon');

    // Показать загрузку
    show(loader);
    hide(tableContainer);
    hide(errorBox);
    refreshIcon.style.animation = 'spin 0.8s linear infinite';

    try {
        const data = await apiCall('/api/v1/models/stats');

        // Очистить таблицу
        tbody.innerHTML = '';

        // Отсортировать по reliability_score (убывание)
        const models = (data.models || []).sort((a, b) =>
            (b.reliability_score || 0) - (a.reliability_score || 0)
        );

        // Заполнить таблицу
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
                <td class="${model.is_active ? 'status-active' : 'status-inactive'}">
                    ${model.is_active ? 'Активна' : 'Неактивна'}
                </td>
            `;

            tbody.appendChild(row);
        });

        if (models.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #666;">Нет данных</td></tr>';
        }

        show(tableContainer);
    } catch (error) {
        showError(errorBox, error.message);
    } finally {
        hide(loader);
        refreshIcon.style.animation = '';
    }
}

/**
 * Экранирование HTML
 * @param {string} text - Текст для экранирования
 * @returns {string} - Экранированный текст
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Тестирование провайдеров
// ============================================

/**
 * Тестировать все провайдеры
 */
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

        // Показать сводку
        summaryDiv.innerHTML = `
            <span style="color: var(--success-color);">✓ ${data.successful || 0}</span> /
            <span style="color: var(--error-color);">✗ ${data.failed || 0}</span>
            из ${data.total_providers || 0} провайдеров
        `;

        // Показать список результатов
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
                        ? `<span style="color: var(--success-color);">✓</span>
                           <span class="provider-time">${formatTime(result.response_time)}</span>`
                        : `<span style="color: var(--error-color);">✗</span>
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
        // Скрыть загрузку
        testBtn.disabled = false;
        show(testBtnText);
        hide(testBtnLoader);
    }
}

// ============================================
// Проверка здоровья системы
// ============================================

/**
 * Проверить статус системы
 */
async function checkHealth() {
    const statusIcon = document.getElementById('status-icon');
    const statusText = document.getElementById('status-text');

    try {
        const data = await apiCall('/health');

        if (data.status === 'healthy') {
            statusIcon.className = 'status-icon online';
            statusText.textContent = 'Онлайн';
        } else {
            statusIcon.className = 'status-icon offline';
            statusText.textContent = 'Проблемы';
        }
    } catch (error) {
        statusIcon.className = 'status-icon offline';
        statusText.textContent = 'Оффлайн';
    }
}

// ============================================
// Обработка ошибок
// ============================================

/**
 * Показать сообщение об ошибке
 * @param {HTMLElement} errorBox - Контейнер для ошибки
 * @param {string} message - Текст ошибки
 */
function showError(errorBox, message) {
    errorBox.textContent = message;
    show(errorBox);
}

// ============================================
// Обработчики событий
// ============================================

// Отправка по Enter (Ctrl+Enter или Cmd+Enter)
document.getElementById('prompt-input').addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        sendPrompt();
    }
});

// ============================================
// Инициализация
// ============================================

/**
 * Инициализация страницы
 */
function init() {
    // Загрузить статистику при загрузке страницы
    loadStats();

    // Проверить статус системы
    checkHealth();

    // Периодическая проверка статуса (каждые 30 секунд)
    setInterval(checkHealth, 30000);
}

// Запуск при загрузке DOM
document.addEventListener('DOMContentLoaded', init);
