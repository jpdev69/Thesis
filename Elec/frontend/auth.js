// Authentication guard for protected EnergyAI pages

const AUTH_KEYS = {
    users: 'users',
    currentUser: 'currentUser',
    returnTo: 'returnTo',
    adminActive: 'energyai_admin_active',
};

const ALLOWED_RETURN_PAGES = new Set([
    'dashboard.html',
    'analytics.html',
    'reports.html',
    'settings.html',
    'models.html',
]);

function safeReadJson(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        if (!raw) return fallback;
        return JSON.parse(raw);
    } catch (_) {
        return fallback;
    }
}

function safeWriteJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
}

function normalizeUser(user) {
    if (!user || typeof user !== 'object') return null;

    const email = String(user.email || '').trim().toLowerCase();
    if (!email) return null;

    const status = String(user.status || 'pending').trim().toLowerCase();
    const role = String(user.role || (email === 'admin@energy.ai' ? 'admin' : 'user')).trim().toLowerCase();

    return {
        id: user.id || '',
        name: String(user.name || 'User').trim() || 'User',
        email,
        password: user.password || '',
        status,
        role,
        created: user.created || new Date().toISOString(),
        lastLogin: user.lastLogin || null,
    };
}

function loadUsers() {
    const users = safeReadJson(AUTH_KEYS.users, []);
    if (!Array.isArray(users)) return [];
    const normalized = users.map(normalizeUser).filter(Boolean);
    if (normalized.length !== users.length) {
        safeWriteJson(AUTH_KEYS.users, normalized);
    }
    return normalized;
}

function saveUsers(users) {
    safeWriteJson(AUTH_KEYS.users, users.map(normalizeUser).filter(Boolean));
}

function getCurrentUser() {
    const current = safeReadJson(AUTH_KEYS.currentUser, null);
    if (!current || typeof current !== 'object') return null;
    const email = String(current.email || '').trim().toLowerCase();
    if (!email) return null;
    return {
        id: current.id || '',
        name: String(current.name || 'User').trim() || 'User',
        email,
        status: String(current.status || '').trim().toLowerCase(),
        role: String(current.role || 'user').trim().toLowerCase(),
    };
}

function setCurrentUser(user) {
    const normalized = normalizeUser(user);
    if (!normalized) return;
    safeWriteJson(AUTH_KEYS.currentUser, {
        id: normalized.id,
        name: normalized.name,
        email: normalized.email,
        status: normalized.status,
        role: normalized.role,
    });
}

function currentPageName() {
    return window.location.pathname.split('/').pop() || 'dashboard.html';
}

function redirectToLogin() {
    const page = currentPageName();
    if (page !== 'login.html' && page !== 'admin.html') {
        if (ALLOWED_RETURN_PAGES.has(page)) {
            localStorage.setItem(AUTH_KEYS.returnTo, page);
        }
        window.location.href = 'login.html';
    }
}

function checkSimpleAuth() {
    const current = getCurrentUser();
    if (!current) {
        redirectToLogin();
        return;
    }

    const users = loadUsers();
    const liveUser = users.find(u => u.email === current.email);

    if (!liveUser || liveUser.status !== 'approved') {
        alert('Your access permissions have been modified or revoked by the Administrator.');
        localStorage.removeItem(AUTH_KEYS.currentUser);
        redirectToLogin();
        return;
    }

    setCurrentUser(liveUser);

    const userName = document.querySelector('.user-name');
    const avatar = document.querySelector('.avatar');

    if (userName) {
        userName.textContent = liveUser.name;
    }

    if (avatar) {
        const initials = liveUser.name
            .split(' ')
            .map(n => n[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);
        avatar.textContent = initials || 'US';
    }

    window.EnergyAIAuth = {
        user: {
            id: liveUser.id,
            name: liveUser.name,
            email: liveUser.email,
            role: liveUser.role,
            status: liveUser.status,
        },
        isAdmin: liveUser.role === 'admin',
    };

    const page = currentPageName();
    if (page === 'models.html' && liveUser.role !== 'admin') {
        alert('Administrator role is required to access Model Operations.');
        window.location.href = 'dashboard.html';
    }
}

function simpleLogout() {
    localStorage.removeItem(AUTH_KEYS.currentUser);
    localStorage.removeItem(AUTH_KEYS.returnTo);
    window.location.href = 'login.html';
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    if (sunIcon && moonIcon) {
        if (savedTheme === 'dark') {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        } else {
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        }
    }
    if (typeof updateChartsTheme === 'function') {
        updateChartsTheme();
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    if (sunIcon && moonIcon) {
        if (newTheme === 'dark') {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        } else {
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        }
    }

    if (typeof updateChartsTheme === 'function') {
        updateChartsTheme();
    }
}

function removeTechnicalNavEntries() {
    const auth = window.EnergyAIAuth;
    if (auth && auth.isAdmin) return;

    const navItems = document.querySelectorAll('.sidebar-nav a, .sidebar-nav button');
    navItems.forEach((item) => {
        const text = item.textContent?.trim().toLowerCase();
        const href = item.getAttribute('href') || '';
        if (text === 'models' || href.includes('models.html')) {
            item.remove();
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    checkSimpleAuth();
    removeTechnicalNavEntries();
});
