/* LinkHub - shared frontend helpers and landing page behaviour. */

const API = window.location.origin;
const TOKEN_KEY = 'linkhub_token';

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

async function apiFetch(path, options = {}) {
    const headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
    const token = getToken();
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }

    const response = await fetch(API + path, Object.assign({}, options, { headers }));

    // An expired or rejected token means the session is over.
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
        clearToken();
    }
    return response;
}

function setHidden(element, hidden) {
    if (!element) return;
    element.classList.toggle('hidden', hidden);
}

function showAuthError(message) {
    const box = document.getElementById('auth-error');
    if (!box) return;
    box.textContent = message;
    box.classList.remove('hidden');
}

function clearAuthError() {
    const box = document.getElementById('auth-error');
    if (!box) return;
    box.textContent = '';
    box.classList.add('hidden');
}

function syncAuthUi() {
    const authSection = document.getElementById('auth-section');
    const shortenSection = document.getElementById('shorten-section');
    const authLink = document.getElementById('auth-link');

    const signedIn = Boolean(getToken());
    if (signedIn) {
        setHidden(authSection, true);
        setHidden(shortenSection, false);
        if (authLink) {
            authLink.textContent = 'Logout';
            authLink.onclick = logout;
        }
    } else {
        setHidden(authSection, false);
        setHidden(shortenSection, true);
        if (authLink) {
            authLink.textContent = 'Login';
            authLink.onclick = showAuth;
        }
    }
}

function showAuth() {
    setHidden(document.getElementById('auth-section'), false);
    setHidden(document.getElementById('shorten-section'), true);
}

function logout() {
    clearToken();
    window.location.reload();
}

let isRegister = false;

function toggleAuth() {
    isRegister = !isRegister;
    document.getElementById('auth-title').textContent = isRegister ? 'Register' : 'Login';
    document.getElementById('auth-btn').textContent = isRegister ? 'Register' : 'Login';
    setHidden(document.getElementById('register-fields'), !isRegister);
    clearAuthError();
}

async function handleAuth() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const username = document.getElementById('username').value.trim();
    const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login';
    const body = isRegister ? { email, password, username } : { email, password };

    clearAuthError();
    try {
        const response = await fetch(API + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Authentication failed');
        }
        setToken(data.access_token);
        syncAuthUi();
    } catch (error) {
        showAuthError(error.message);
    }
}

async function shortenUrl() {
    const urlInput = document.getElementById('url-input');
    const aliasInput = document.getElementById('alias-input');
    const result = document.getElementById('result');

    const url = urlInput.value.trim();
    if (!url) {
        alert('Please enter a URL');
        return;
    }

    const body = { url };
    const alias = aliasInput.value.trim();
    if (alias) body.custom_alias = alias;

    try {
        const response = await apiFetch('/api/links', {
            method: 'POST',
            body: JSON.stringify(body),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Could not create the link');
        }
        document.getElementById('short-url').textContent = data.short_url;
        document.getElementById('qr-code').src = '/api/qr/' + data.short_code + '.png';
        result.classList.remove('hidden');
    } catch (error) {
        alert(error.message);
    }
}

async function copyUrl() {
    const value = document.getElementById('short-url').textContent;
    try {
        await navigator.clipboard.writeText(value);
    } catch (error) {
        // Clipboard access can be blocked; fall back to a manual selection.
        const range = document.createRange();
        range.selectNodeContents(document.getElementById('short-url'));
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('toggle-auth');
    if (toggle) toggle.addEventListener('click', (event) => {
        event.preventDefault();
        toggleAuth();
    });

    const authBtn = document.getElementById('auth-btn');
    if (authBtn) authBtn.addEventListener('click', handleAuth);

    const shortenBtn = document.getElementById('shorten-btn');
    if (shortenBtn) shortenBtn.addEventListener('click', shortenUrl);

    const copyBtn = document.getElementById('copy-btn');
    if (copyBtn) copyBtn.addEventListener('click', copyUrl);

    const aliasInput = document.getElementById('alias-input');
    if (aliasInput) {
        aliasInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') shortenUrl();
        });
    }

    syncAuthUi();
});
