// Authentication check for protected EnergyAI dashboard pages
// Validates session credentials and live admin approval status

function checkSimpleAuth() {
    const currentUserRaw = localStorage.getItem('currentUser');
    
    if (!currentUserRaw) {
        redirectToLogin();
        return;
    }
    
    let user;
    try {
        user = JSON.parse(currentUserRaw);
    } catch (e) {
        redirectToLogin();
        return;
    }

    // Verify current account status against registered users database
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    const liveUser = users.find(u => u.email.toLowerCase() === user.email.toLowerCase());

    if (!liveUser || liveUser.status !== 'approved') {
        alert('Your access permissions have been modified or revoked by the Administrator.');
        localStorage.removeItem('currentUser');
        redirectToLogin();
        return;
    }
    
    // Update user info display in sidebar header
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
}

function redirectToLogin() {
    const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
    if (currentPage !== 'login.html' && currentPage !== 'admin.html') {
        localStorage.setItem('returnTo', currentPage);
        window.location.href = 'login.html';
    }
}

// Logout function
function simpleLogout() {
    localStorage.removeItem('currentUser');
    localStorage.removeItem('returnTo');
    window.location.href = 'login.html';
}

// Universal Light / Dark Theme Management
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
    const navItems = document.querySelectorAll('.sidebar-nav a, .sidebar-nav button');
    navItems.forEach((item) => {
        const text = item.textContent?.trim().toLowerCase();
        const href = item.getAttribute('href') || '';
        if (text === 'models' || href.includes('models.html')) {
            item.remove();
        }
    });
}

// Initialize session check & theme on DOM load
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    checkSimpleAuth();
    removeTechnicalNavEntries();
});
