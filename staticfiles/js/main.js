const signupBtn = document.getElementById('signupBtn');
const signinBtn = document.getElementById('signinBtn');
const modalBackdrop = document.getElementById('modalBackdrop');
const signinModal = document.getElementById('signinModal');
const signupModal = document.getElementById('signupModal');
const forgotModal = document.getElementById('forgotModal');
const profileModal = document.getElementById('profileModal');
const modalCloseButtons = document.querySelectorAll('[data-close]');
const switchModalButtons = document.querySelectorAll('.switch-modal');
const forgotLink = document.getElementById('forgotLink');
const signinUsernameInput = document.getElementById('signin-username');
const forgotUsernameInput = document.getElementById('forgot-username');

function openModal(modal) {
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('show');
    modalBackdrop.classList.remove('hidden');
    modalBackdrop.classList.add('show');
}

function closeModal(modal) {
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.remove('show');
    modal.classList.add('close-animation');
    modalBackdrop.classList.remove('show');
    modalBackdrop.classList.add('hidden');
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.classList.remove('close-animation');
    }, 250);
}

function closeAllModals() {
    [signinModal, signupModal, forgotModal, profileModal].forEach((modal) => closeModal(modal));
}

if (signupBtn) {
    signupBtn.addEventListener('click', () => {
        closeAllModals();
        openModal(signupModal);
    });
}

if (signinBtn) {
    signinBtn.addEventListener('click', () => {
        closeAllModals();
        openModal(signinModal);
    });
}

modalCloseButtons.forEach((button) => {
    button.addEventListener('click', () => {
        closeAllModals();
    });
});

modalBackdrop.addEventListener('click', (e) => {
    // only close when clicking directly on the backdrop, not when clicks bubble from modal content
    if (e.target === modalBackdrop) closeAllModals();
});

if (forgotLink) {
    forgotLink.addEventListener('click', () => {
        if (signinUsernameInput && forgotUsernameInput) {
            forgotUsernameInput.value = signinUsernameInput.value.trim();
        }
    });
}

switchModalButtons.forEach((button) => {
    button.addEventListener('click', () => {
        const target = button.dataset.target;
        closeAllModals();
        if (target === 'signup') {
            openModal(signupModal);
        } else if (target === 'forgot') {
            openModal(forgotModal);
        } else {
            openModal(signinModal);
        }
    });
});

window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeAllModals();
    }
});

function scheduleToastAutoHide(toast, delay = 3500) {
    if (!toast) return;
    if (toast._autoHideTimer) {
        clearTimeout(toast._autoHideTimer);
    }
    toast._autoHideTimer = setTimeout(() => {
        toast.classList.remove('show');
        delete toast._autoHideTimer;
    }, delay);
}

function showToastMessage(toast, delay = 3500) {
    if (!toast) return;
    toast.classList.add('show');
    scheduleToastAutoHide(toast, delay);
}

function initToasts() {
    document.querySelectorAll('.toast.show').forEach((toast) => {
        scheduleToastAutoHide(toast, 3500);
    });
}

function applyTheme(theme) {
    const isDark = theme === 'dark';
    document.body.classList.toggle('dark-mode', isDark);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    document.querySelectorAll('.toggle-mode').forEach((button) => {
        const icon = button.querySelector('.toggle-mode-icon');
        if (icon) {
            icon.textContent = isDark ? '☀' : '🌙';
        }
        button.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    });
}

function initTheme() {
    const storedTheme = localStorage.getItem('mealbuddy-theme');
    const preferredTheme = storedTheme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(preferredTheme);
}

function initPasswordToggles() {
    document.querySelectorAll('.password-field').forEach((field) => {
        const input = field.querySelector('input[type="password"], input[type="text"]');
        const toggle = field.querySelector('[data-toggle-password]');

        if (!input || !toggle) return;

        toggle.addEventListener('click', () => {
            const isPasswordVisible = input.type === 'text';
            input.type = isPasswordVisible ? 'password' : 'text';
            const icon = toggle.querySelector('.password-toggle-icon');
            if (icon) {
                icon.textContent = isPasswordVisible ? '👁' : '🙈';
            }
            toggle.setAttribute('aria-label', isPasswordVisible ? 'Show password' : 'Hide password');
        });
    });
}

document.querySelectorAll('.toggle-mode').forEach((button) => {
    button.addEventListener('click', () => {
        const nextTheme = document.body.classList.contains('dark-mode') ? 'light' : 'dark';
        localStorage.setItem('mealbuddy-theme', nextTheme);
        applyTheme(nextTheme);
    });
});

if (window.initialOpenModal) {
    const initialModalMap = {
        signin: signinModal,
        signup: signupModal,
        forgot: forgotModal,
    };
    const initialModal = initialModalMap[window.initialOpenModal];
    if (initialModal) {
        openModal(initialModal);
    }
}

function initProfileDropdown() {
    const wrappers = document.querySelectorAll('.profile-menu-wrapper');

    wrappers.forEach((wrapper) => {
        const trigger = wrapper.querySelector('.profile-trigger');
        const menu = wrapper.querySelector('.profile-dropdown-menu');
        if (!trigger || !menu) return;

        trigger.addEventListener('click', (event) => {
            event.stopPropagation();
            const isOpen = wrapper.classList.contains('open');
            wrappers.forEach((item) => item.classList.remove('open'));
            if (!isOpen) {
                wrapper.classList.add('open');
                trigger.setAttribute('aria-expanded', 'true');
            } else {
                trigger.setAttribute('aria-expanded', 'false');
            }
        });

        menu.querySelectorAll('.profile-dropdown-item').forEach((item) => {
            item.addEventListener('click', () => {
                if (item.dataset.profileAction === 'view') {
                    const profileModal = document.getElementById('profileModal');
                    if (profileModal) {
                        openModal(profileModal);
                    }
                }
                wrapper.classList.remove('open');
                trigger.setAttribute('aria-expanded', 'false');
            });
        });
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.profile-menu-wrapper')) {
            wrappers.forEach((wrapper) => {
                wrapper.classList.remove('open');
                const trigger = wrapper.querySelector('.profile-trigger');
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'false');
                }
            });
        }
    });
}

const heroVideo = document.getElementById('heroVideo');
const heroVideoSources = window.heroVideoSources || [];
let currentHeroVideoIndex = 0;

if (heroVideo && heroVideoSources.length) {
    heroVideo.loop = false;

    heroVideo.addEventListener('ended', () => {
        currentHeroVideoIndex = (currentHeroVideoIndex + 1) % heroVideoSources.length;
        heroVideo.src = heroVideoSources[currentHeroVideoIndex];
        heroVideo.load();
        heroVideo.play().catch(() => {});
    });

    heroVideo.addEventListener('loadeddata', () => {
        if (heroVideo.paused) {
            heroVideo.play().catch(() => {});
        }
    });
}

initTheme();
initToasts();
initPasswordToggles();
initProfileDropdown();
