(function () {
    const API_BASE_KEY = 'energyai.apiBase';

    function normalizeApiBase(value) {
        if (!value || typeof value !== 'string') return null;

        let base = value.trim();
        if (!base) return null;

        if (!/^https?:\/\//i.test(base)) {
            base = `http://${base}`;
        }

        base = base.replace(/\/+$/, '');

        try {
            const parsed = new URL(base);
            return `${parsed.protocol}//${parsed.host}`;
        } catch (_) {
            return null;
        }
    }

    function defaultApiBase() {
        const host = window.location.hostname || 'localhost';
        return `http://${host}:8000`;
    }

    function getApiBase() {
        try {
            const saved = normalizeApiBase(localStorage.getItem(API_BASE_KEY));
            if (saved) return saved;
        } catch (_) {
            // Ignore localStorage issues and use default
        }
        return defaultApiBase();
    }

    function setApiBase(value) {
        const normalized = normalizeApiBase(value);
        if (!normalized) {
            throw new Error('Invalid API endpoint URL');
        }

        localStorage.setItem(API_BASE_KEY, normalized);
        return normalized;
    }

    function apiUrl(path) {
        const cleanedPath = path.startsWith('/') ? path : `/${path}`;
        return `${getApiBase()}${cleanedPath}`;
    }

    window.EnergyAIConfig = {
        apiBaseKey: API_BASE_KEY,
        getApiBase,
        setApiBase,
        apiUrl,
        normalizeApiBase,
        defaultApiBase,
    };
})();
