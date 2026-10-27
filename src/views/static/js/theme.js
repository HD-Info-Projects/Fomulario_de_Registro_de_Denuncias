(() => {
    const storageKey = "denuncias-theme";
    const root = document.documentElement;

    function normalizeTheme(theme) {
        return theme === "dark" ? "dark" : "light";
    }

    function savedTheme() {
        try {
            return normalizeTheme(window.localStorage.getItem(storageKey));
        } catch {
            return "light";
        }
    }

    function updateButtons() {
        const dark = root.dataset.theme === "dark";
        const label = dark ? "Tema claro" : "Tema escuro";
        const action = dark ? "Ativar tema claro" : "Ativar tema escuro";

        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.querySelector("[data-theme-label]").textContent = label;
            button.setAttribute("aria-label", action);
            button.title = action;
            button.hidden = false;
        });
    }

    function applyTheme(theme) {
        const normalized = normalizeTheme(theme);
        root.dataset.theme = normalized;
        updateButtons();
        window.dispatchEvent(new CustomEvent("themechange", {
            detail: { theme: normalized }
        }));
    }

    // Script síncrono no <head>: evita exibir o tema errado ao navegar.
    root.dataset.theme = savedTheme();

    document.addEventListener("DOMContentLoaded", updateButtons);
    document.addEventListener("click", (event) => {
        if (!event.target.closest("[data-theme-toggle]")) {
            return;
        }

        const theme = root.dataset.theme === "dark" ? "light" : "dark";
        try {
            window.localStorage.setItem(storageKey, theme);
        } catch {
            // A alternância funciona mesmo quando o navegador bloqueia o armazenamento.
        }
        applyTheme(theme);
    });

    window.addEventListener("storage", (event) => {
        if (event.key === storageKey || event.key === null) {
            applyTheme(event.newValue);
        }
    });
})();
