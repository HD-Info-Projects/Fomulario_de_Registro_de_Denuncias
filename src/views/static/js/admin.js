(() => {
    const dialog = document.getElementById("management-confirm");
    const approved = new WeakSet();
    const busyForms = new Map();
    let pending = null;

    function validatePasswords(form, showFeedback = false) {
        const password = form.querySelector("[name='senha']");
        const confirmation = form.querySelector("[name='confirmacao_senha']");
        if (!password || !confirmation) return true;

        const error = password.value !== confirmation.value
            ? "As senhas não conferem. Digite a mesma senha nos dois campos."
            : "";
        confirmation.setCustomValidity(error);
        const visible = Boolean(error && (showFeedback || confirmation.value));
        confirmation.setAttribute("aria-invalid", String(visible));
        const feedback = form.querySelector("[data-password-feedback]");
        if (feedback) {
            feedback.textContent = visible ? error : "";
            feedback.hidden = !visible;
        }
        return !error;
    }

    function updateCounter(counter) {
        const input = document.getElementById(counter.dataset.counterFor);
        if (input) counter.textContent = `${input.value.length}/${input.maxLength} caracteres`;
    }

    function markBusy(form, submitter) {
        const buttons = [...form.querySelectorAll('button[type="submit"], input[type="submit"]')];
        busyForms.set(form, buttons.map(button => ({ button, disabled: button.disabled, label: button.textContent })));
        form.setAttribute("aria-busy", "true");
        buttons.forEach(button => { button.disabled = true; });
        if (submitter && submitter.tagName === "BUTTON") {
            submitter.textContent = form.dataset.loadingLabel || "Salvando…";
        }
        const feedback = form.querySelector("[data-submit-feedback]");
        if (feedback) feedback.textContent = form.dataset.loadingLabel || "Salvando alterações…";
    }

    function restoreForms() {
        busyForms.forEach((buttons, form) => {
            buttons.forEach(({ button, disabled, label }) => {
                button.disabled = disabled;
                button.textContent = label;
            });
            form.removeAttribute("aria-busy");
            const feedback = form.querySelector("[data-submit-feedback]");
            if (feedback) feedback.textContent = "";
        });
        busyForms.clear();
    }

    if (dialog && typeof dialog.showModal === "function") {
        dialog.addEventListener("close", () => {
            const submission = pending;
            pending = null;
            if (dialog.returnValue !== "confirm" || !submission) return;
            const { form, submitter } = submission;
            if (!form.reportValidity()) return;
            approved.add(form);
            try {
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit(submitter || undefined);
                } else {
                    markBusy(form, submitter);
                    form.submit();
                }
            } finally {
                approved.delete(form);
            }
        });
    }

    document.addEventListener("submit", (event) => {
        const form = event.target.closest("form[data-management-form], form[data-confirm]");
        if (!form) return;
        if (busyForms.has(form)) {
            event.preventDefault();
            return;
        }
        if (!validatePasswords(form, true)) {
            event.preventDefault();
            form.reportValidity();
            return;
        }
        if (form.dataset.confirm && !approved.has(form)) {
            if (dialog && typeof dialog.showModal === "function") {
                event.preventDefault();
                if (dialog.open) return;
                pending = { form, submitter: event.submitter };
                dialog.querySelector("[data-confirm-title]").textContent = form.dataset.confirmTitle || "Confirmar alteração";
                dialog.querySelector("[data-confirm-message]").textContent = form.dataset.confirm;
                const target = dialog.querySelector("[data-confirm-target]");
                target.textContent = form.dataset.confirmTarget || "";
                target.hidden = !form.dataset.confirmTarget;
                const button = dialog.querySelector("[data-confirm-submit]");
                button.textContent = form.dataset.confirmLabel || "Confirmar";
                button.classList.toggle("danger", form.dataset.confirmDanger === "true");
                button.classList.toggle("primary", form.dataset.confirmDanger !== "true");
                dialog.returnValue = "cancel";
                dialog.showModal();
                return;
            }
            if (!window.confirm(form.dataset.confirm)) {
                event.preventDefault();
                return;
            }
        }
        approved.delete(form);
        markBusy(form, event.submitter);
    });

    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-toggle-password]");
        if (!button) return;
        const input = document.getElementById(button.dataset.togglePassword);
        if (!input) return;
        const visible = input.type === "password";
        input.type = visible ? "text" : "password";
        button.textContent = visible ? "Ocultar" : "Mostrar";
        button.setAttribute("aria-pressed", String(visible));
    });

    document.addEventListener("input", (event) => {
        const form = event.target.closest("form[data-management-form]");
        if (form) validatePasswords(form);
        document.querySelectorAll("[data-counter-for]").forEach(updateCounter);
    });

    document.querySelectorAll("form[data-management-form]").forEach(form => validatePasswords(form));
    document.querySelectorAll("[data-counter-for]").forEach(updateCounter);
    window.addEventListener("pageshow", restoreForms);
})();
