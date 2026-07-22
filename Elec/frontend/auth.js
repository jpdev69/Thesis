// Simple authentication check for dashboard pages
// This works with localStorage (no backend needed)

function checkSimpleAuth() {
    const currentUser = localStorage.getItem('currentUser');
    
    if (!currentUser) {
        const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
        localStorage.setItem('returnTo', currentPage);
        window.location.href = 'login.html';
        return;
    }
    
    const user = JSON.parse(currentUser);
    
    // Update user info in sidebar
    const userName = document.querySelector('.user-name');
    const avatar = document.querySelector('.avatar');
    
    if (userName) {
        userName.textContent = user.name;
    }
    
    if (avatar) {
        const initials = user.name
            .split(' ')
            .map(n => n[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);
        avatar.textContent = initials;
    }
}

// Logout function
function simpleLogout() {
    if (confirm('Do you want to logout?')) {
        localStorage.removeItem('currentUser');
        localStorage.removeItem('returnTo');
        window.location.href = 'login.html';
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

// Add logout functionality to user profile
document.addEventListener('DOMContentLoaded', () => {
    // Check auth on page load
    checkSimpleAuth();
    removeTechnicalNavEntries();
    
    // Add click handler to user profile
    const userProfile = document.querySelector('.user-profile');
    if (userProfile) {
        userProfile.style.cursor = 'pointer';
        userProfile.addEventListener('click', simpleLogout);
    }
});
