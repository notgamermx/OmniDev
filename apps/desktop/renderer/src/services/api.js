/**
 * OmniDev Desktop - API Service
 * Handles all API communication via Electron IPC
 */

class ApiService {
    constructor() {
        this.basePath = '';
    }

    /**
     * Make an API request to the backend
     * @param {string} path - API endpoint path
     * @param {string} method - HTTP method
     * @param {object|null} body - Request body
     * @returns {Promise<object>} - API response
     */
    async request(path, method = 'GET', body = null) {
        if (!window.electronAPI) {
            throw new Error('Electron API not available');
        }
        return await window.electronAPI.request(path, method, body);
    }

    // Health endpoints
    getHealth() {
        return this.request('/api/v1/health/');
    }

    getSystem() {
        return this.request('/api/v1/system/');
    }

    // Agent endpoints
    listAgents(enabledOnly = true) {
        return this.request(`/api/v1/agents/?enabled_only=${enabledOnly}`);
    }

    getAgent(agentId) {
        return this.request(`/api/v1/agents/${agentId}`);
    }

    createAgent(agentData) {
        return this.request('/api/v1/agents/', 'POST', agentData);
    }

    deleteAgent(agentId) {
        return this.request(`/api/v1/agents/${agentId}`, 'DELETE');
    }

    // Task endpoints
    listTasks(filter = {}) {
        const params = new URLSearchParams(filter).toString();
        return this.request(`/api/v1/tasks/${params ? `?${params}` : ''}`);
    }

    getTask(taskId) {
        return this.request(`/api/v1/tasks/${taskId}`);
    }

    createTask(taskData) {
        return this.request('/api/v1/tasks/', 'POST', taskData);
    }

    executeTask(taskId, projectRoot = '.') {
        return this.request(`/api/v1/tasks/${taskId}/execute`, 'POST', { project_root: projectRoot });
    }

    cancelTask(taskId) {
        return this.request(`/api/v1/tasks/${taskId}/cancel`, 'POST');
    }

    // Memory endpoints
    getSessionMemory(key) {
        return this.request(`/api/v1/memory/session/${key}`);
    }

    setSessionMemory(memoryData) {
        return this.request('/api/v1/memory/session/', 'POST', memoryData);
    }

    listSessionMemories() {
        return this.request('/api/v1/memory/session');
    }

    deleteSessionMemory(key) {
        return this.request(`/api/v1/memory/session/${key}`, 'DELETE');
    }

    listProjectMemories(projectId) {
        return this.request(`/api/v1/memory/project/${projectId}`);
    }

    recallProjectContext(projectId, query, maxItems = 10) {
        return this.request(`/api/v1/memory/project/${projectId}/recall`, 'POST', { query, max_items: maxItems });
    }

    // File operations (via Electron IPC)
    readFile(path) {
        if (!window.electronAPI) {
            throw new Error('Electron API not available');
        }
        return window.electronAPI.read(path);
    }

    writeFile(path, content) {
        if (!window.electronAPI) {
            throw new Error('Electron API not available');
        }
        return window.electronAPI.write(path, content);
    }

    listFiles(dirPath = '.') {
        if (!window.electronAPI) {
            throw new Error('Electron API not available');
        }
        return window.electronAPI.list(dirPath);
    }
}

// Export singleton instance
const api = new ApiService();
export default api;