const API_URL = "";

function getToken() {
    return localStorage.getItem("token");
}

function logout() {
    localStorage.removeItem("token");
    window.location.href = "/";
}

async function loadDashboard() {
    const token = getToken();
    if (!token) {
        window.location.href = "/";
        return;
    }

    try {
        const response = await fetch(`${API_URL}/api/links`, {
            headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
            throw new Error("Failed to load links");
        }

        const data = await response.json();
        document.getElementById("total-links").textContent = data.total;

        const linksList = document.getElementById("links-list");
        linksList.innerHTML = data.links
            .map(
                (link) => `
            <div class="link-item">
                <div class="link-info">
                    <a href="${link.short_url}" target="_blank">${link.short_url}</a>
                    <p>${link.original_url}</p>
                </div>
                <div class="link-stats">
                    <div class="clicks">${link.click_count}</div>
                    <div class="label">clicks</div>
                </div>
            </div>
        `
            )
            .join("");
    } catch (error) {
        console.error(error);
    }
}

document.addEventListener("DOMContentLoaded", loadDashboard);
