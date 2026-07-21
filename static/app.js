const API_URL = "";

function getToken() {
    return localStorage.getItem("token");
}

function setToken(token) {
    localStorage.setItem("token", token);
}

function clearToken() {
    localStorage.removeItem("token");
}

async function shortenUrl() {
    const urlInput = document.getElementById("url-input");
    const aliasInput = document.getElementById("alias-input");
    const resultDiv = document.getElementById("result");
    const shortUrlEl = document.getElementById("short-url");
    const qrCodeEl = document.getElementById("qr-code");

    const url = urlInput.value.trim();
    if (!url) {
        alert("Please enter a URL");
        return;
    }

    const token = getToken();
    if (!token) {
        alert("Please login first");
        return;
    }

    try {
        const body = { url };
        if (aliasInput.value.trim()) {
            body.custom_alias = aliasInput.value.trim();
        }

        const response = await fetch(`${API_URL}/api/links`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Failed to shorten URL");
        }

        const data = await response.json();
        shortUrlEl.textContent = data.short_url;
        qrCodeEl.src = data.qr_code;
        resultDiv.classList.remove("hidden");
    } catch (error) {
        alert(error.message);
    }
}

function copyUrl() {
    const shortUrl = document.getElementById("short-url").textContent;
    navigator.clipboard.writeText(shortUrl);
    alert("Copied to clipboard!");
}

function logout() {
    clearToken();
    window.location.href = "/";
}

document.addEventListener("DOMContentLoaded", () => {
    const authLink = document.getElementById("auth-link");
    if (getToken()) {
        authLink.textContent = "Dashboard";
        authLink.href = "/dashboard";
    }
});
