/* LinkHub - dashboard behaviour. */

let allLinks = [];

function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function linkState(link) {
    if (!link.is_active) return { label: 'disabled', className: 'badge' };
    if (link.expires_at && new Date(link.expires_at) <= new Date()) {
        return { label: 'expired', className: 'badge expired' };
    }
    return { label: 'active', className: 'badge active' };
}

function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function renderLinks(filterText) {
    const list = document.getElementById('links-list');
    if (!list) return;

    const needle = (filterText || '').toLowerCase();
    const links = allLinks.filter((link) =>
        !needle ||
        link.short_code.toLowerCase().includes(needle) ||
        link.original_url.toLowerCase().includes(needle) ||
        (link.title || '').toLowerCase().includes(needle)
    );

    if (!links.length) {
        list.innerHTML = '<div class="empty">No links yet. <a href="/">Create one</a></div>';
        return;
    }

    list.innerHTML = links.map((link) => {
        const state = linkState(link);
        return `
        <div class="link-item">
            <div class="link-info">
                <a href="${escapeHtml(link.short_url)}" target="_blank" rel="noopener">${escapeHtml(link.short_url)}</a>
                <p>${escapeHtml(link.original_url)}</p>
                <div class="link-meta">
                    <span class="${state.className}">${state.label}</span>
                    <span class="badge">${escapeHtml(formatDate(link.created_at))}</span>
                </div>
            </div>
            <div class="link-stats">
                <div class="clicks">${link.click_count}</div>
                <div class="label">clicks</div>
            </div>
            <div class="link-actions">
                <button type="button" data-delete="${escapeHtml(link.id)}">Delete</button>
            </div>
        </div>`;
    }).join('');

    list.querySelectorAll('button[data-delete]').forEach((button) => {
        button.addEventListener('click', () => deleteLink(button.dataset.delete));
    });
}

function updateStats() {
    const totalLinks = document.getElementById('total-links');
    const totalClicks = document.getElementById('total-clicks');
    const activeLinks = document.getElementById('active-links');

    if (totalLinks) totalLinks.textContent = allLinks.length;

    const clicks = allLinks.reduce((sum, link) => sum + (link.click_count || 0), 0);
    if (totalClicks) totalClicks.textContent = clicks;

    const active = allLinks.filter((link) => linkState(link).className === 'badge active').length;
    if (activeLinks) activeLinks.textContent = active;
}

async function loadLinks() {
    const list = document.getElementById('links-list');
    if (!getToken()) {
        window.location.href = '/';
        return;
    }

    try {
        const response = await apiFetch('/api/links?limit=100');
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        if (!response.ok) throw new Error('Could not load links');

        const data = await response.json();
        allLinks = data.links || [];
        updateStats();
        renderLinks(document.getElementById('search-input')?.value || '');
    } catch (error) {
        if (list) list.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    }
}

async function deleteLink(id) {
    if (!window.confirm('Delete this link? The short URL will stop working.')) return;
    try {
        const response = await apiFetch('/api/links/' + id, { method: 'DELETE' });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || 'Could not delete the link');
        }
        await loadLinks();
    } catch (error) {
        alert(error.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const search = document.getElementById('search-input');
    if (search) {
        search.addEventListener('input', (event) => renderLinks(event.target.value));
    }

    const refresh = document.getElementById('refresh-btn');
    if (refresh) refresh.addEventListener('click', loadLinks);

    loadLinks();
});
