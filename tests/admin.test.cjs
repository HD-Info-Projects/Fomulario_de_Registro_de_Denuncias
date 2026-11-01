const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../src/views/static/js/admin.js"), "utf8");

function element(properties = {}) {
    const attributes = {};
    const classes = new Set();
    return {
        dataset: {}, textContent: "", disabled: false, hidden: false, attributes, classes,
        setAttribute(name, value) { attributes[name] = value; },
        removeAttribute(name) { delete attributes[name]; },
        classList: { toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); } },
        ...properties
    };
}

function environment({ confirmResult = true, modal = false, counter = false } = {}) {
    const handlers = {};
    const windowHandlers = {};
    const nodes = new Map();
    const prompts = [];
    const submissions = [];
    const dialogNodes = Object.fromEntries(["title", "message", "target", "submit"].map(name => [name, element()]));
    const dialogHandlers = {};
    const dialog = modal ? {
        open: false, returnValue: "",
        addEventListener(name, handler) { dialogHandlers[name] = handler; },
        querySelector(selector) { return dialogNodes[selector.match(/data-confirm-(\w+)/)[1]]; },
        showModal() { this.open = true; },
        close(value) {
            if (value !== undefined) this.returnValue = value;
            this.open = false;
            dialogHandlers.close();
        }
    } : null;
    if (dialog) nodes.set("management-confirm", dialog);
    const description = element({ id: "descricao", value: "Texto inicial", maxLength: 2000 });
    const characterCounter = element({ dataset: { counterFor: "descricao" } });
    if (counter) nodes.set("descricao", description);

    vm.runInNewContext(source, {
        document: {
            addEventListener(name, handler) { handlers[name] = handler; },
            getElementById: id => nodes.get(id) || null,
            querySelectorAll: selector => selector === "[data-counter-for]" && counter ? [characterCounter] : []
        },
        window: {
            confirm(message) { prompts.push(message); return confirmResult; },
            addEventListener(name, handler) { windowHandlers[name] = handler; }
        }
    });

    const env = { handlers, windowHandlers, nodes, prompts, submissions, dialog, dialogNodes, description, characterCounter };
    env.submit = (form, submitter = form.button) => {
        let prevented = false;
        handlers.submit({ target: { closest: () => form }, submitter, preventDefault() { prevented = true; } });
        if (!prevented) submissions.push(form);
        return prevented;
    };
    env.form = (dataset = {}, values = {}) => {
        const button = element({ tagName: "BUTTON", textContent: "Salvar alterações" });
        const feedback = element();
        const passwordFeedback = element();
        const fields = {};
        const form = element({
            dataset, button, feedback, passwordFeedback, fields,
            querySelector(selector) {
                if (selector === "[data-submit-feedback]") return feedback;
                if (selector === "[data-password-feedback]") return passwordFeedback;
                return fields[selector.match(/name='([^']+)'/)[1]] || null;
            },
            querySelectorAll: () => [button],
            reportValidity() { return Object.values(fields).every(input => !input.validationMessage); },
            requestSubmit(submitter) { env.submit(form, submitter); },
            submit() { submissions.push(form); }
        });
        for (const [name, value] of Object.entries(values)) {
            fields[name] = element({
                id: name, value, type: "password", validationMessage: "",
                setCustomValidity(message) { this.validationMessage = message; },
                closest: () => form
            });
            nodes.set(name, fields[name]);
        }
        return form;
    };
    return env;
}

test("cancelar confirmação de fallback impede a alteração", () => {
    const env = environment({ confirmResult: false });
    const form = env.form({ confirm: "Desativar esta conta?" });
    assert.equal(env.submit(form), true);
    assert.equal(form.button.disabled, false);
    assert.deepEqual(env.prompts, ["Desativar esta conta?"]);
    assert.equal(env.submissions.length, 0);
});

test("fallback confirmado preserva os campos e bloqueia reenvio", () => {
    const env = environment();
    const form = env.form({ confirm: "Reativar?" }, { csrf_token: "csrf-original", ativo: "1" });
    assert.equal(env.submit(form), false);
    assert.equal(form.fields.csrf_token.value, "csrf-original");
    assert.equal(form.fields.ativo.value, "1");
    assert.equal(env.submit(form), true);
    assert.equal(env.submissions.length, 1);
});

test("modal mostra o alvo como texto e aguarda confirmação", () => {
    const env = environment({ modal: true });
    const form = env.form({ confirm: "As sessões serão revogadas.", confirmTitle: "Desativar conta", confirmTarget: "<script>nome</script>", confirmDanger: "true" });
    assert.equal(env.submit(form), true);
    assert.equal(env.dialog.open, true);
    assert.equal(env.dialogNodes.title.textContent, "Desativar conta");
    assert.equal(env.dialogNodes.target.textContent, "<script>nome</script>");
    assert.ok(env.dialogNodes.submit.classes.has("danger"));
    assert.equal(form.button.disabled, false);
    assert.equal(env.submissions.length, 0);
});

test("cancelar modal não envia o formulário", () => {
    const env = environment({ modal: true });
    const form = env.form({ confirm: "Desativar?" });
    env.submit(form);
    env.dialog.close("cancel");
    assert.equal(env.submissions.length, 0);
    assert.equal(form.button.disabled, false);
});

test("confirmar modal envia uma vez sem reabrir a confirmação", () => {
    const env = environment({ modal: true });
    const form = env.form({ confirm: "Desativar?", loadingLabel: "Alterando…" }, { csrf_token: "token", ativo: "0" });
    env.submit(form);
    env.dialog.close("confirm");
    assert.equal(env.dialog.open, false);
    assert.equal(env.submissions.length, 1);
    assert.equal(form.button.disabled, true);
    assert.equal(form.button.textContent, "Alterando…");
    assert.equal(form.fields.csrf_token.value, "token");
    assert.equal(form.fields.ativo.value, "0");
});

test("segundo clique não troca o alvo de um modal já aberto", () => {
    const env = environment({ modal: true });
    const first = env.form({ confirm: "Confirmar primeiro?", confirmTarget: "Primeiro" });
    const second = env.form({ confirm: "Confirmar segundo?", confirmTarget: "Segundo" });
    env.submit(first);
    env.submit(second);
    env.dialog.close("confirm");
    assert.equal(env.submissions[0], first);
    assert.equal(second.button.disabled, false);
});

test("voltar pelo navegador restaura botões e permite novo envio", () => {
    const env = environment();
    const form = env.form({ managementForm: "", loadingLabel: "Salvando…" });
    env.submit(form);
    assert.equal(form.attributes["aria-busy"], "true");
    assert.equal(form.feedback.textContent, "Salvando…");
    env.windowHandlers.pageshow();
    assert.equal(form.button.disabled, false);
    assert.equal(form.button.textContent, "Salvar alterações");
    assert.equal(form.feedback.textContent, "");
    assert.equal(form.attributes["aria-busy"], undefined);
    assert.equal(env.submit(form), false);
});

test("Escape após uma confirmação anterior não aprova nova ação", () => {
    const env = environment({ modal: true });
    const form = env.form({ confirm: "Confirmar?" });
    env.submit(form);
    env.dialog.close("confirm");
    env.windowHandlers.pageshow();
    env.submit(form);
    assert.equal(env.dialog.returnValue, "cancel");
    env.dialog.close();
    assert.equal(env.submissions.length, 1);
});

test("senhas diferentes impedem envio e exibem feedback acessível", () => {
    const env = environment();
    const form = env.form({ managementForm: "" }, { senha: "password-original", confirmacao_senha: "password-diferente" });
    assert.equal(env.submit(form), true);
    assert.equal(form.passwordFeedback.hidden, false);
    assert.equal(form.fields.confirmacao_senha.attributes["aria-invalid"], "true");
    assert.match(form.fields.confirmacao_senha.validationMessage, /não conferem/);
    assert.equal(form.button.disabled, false);
});

test("corrigir a confirmação remove o erro e permite salvar", () => {
    const env = environment();
    const form = env.form({ managementForm: "" }, { senha: "password-original", confirmacao_senha: "outro" });
    env.submit(form);
    form.fields.confirmacao_senha.value = "password-original";
    env.handlers.input({ target: form.fields.confirmacao_senha });
    assert.equal(form.fields.confirmacao_senha.validationMessage, "");
    assert.equal(form.passwordFeedback.hidden, true);
    assert.equal(env.submit(form), false);
});

test("edição permite manter os campos de senha vazios", () => {
    const env = environment();
    const form = env.form({ managementForm: "" }, { senha: "", confirmacao_senha: "" });
    assert.equal(env.submit(form), false);
});

test("mostrar e ocultar senha atualiza o estado acessível", () => {
    const env = environment();
    const form = env.form({}, { senha: "password-original" });
    const button = element({ dataset: { togglePassword: "senha" }, textContent: "Mostrar" });
    const event = { target: { closest: () => button } };
    env.handlers.click(event);
    assert.equal(form.fields.senha.type, "text");
    assert.equal(button.textContent, "Ocultar");
    assert.equal(button.attributes["aria-pressed"], "true");
    env.handlers.click(event);
    assert.equal(form.fields.senha.type, "password");
    assert.equal(button.attributes["aria-pressed"], "false");
});

test("contador da descrição atualiza sem enviar dados", () => {
    const env = environment({ counter: true });
    assert.equal(env.characterCounter.textContent, "13/2000 caracteres");
    env.description.value = "Nova descrição";
    env.handlers.input({ target: { closest: () => null } });
    assert.equal(env.characterCounter.textContent, "14/2000 caracteres");
    assert.equal(env.submissions.length, 0);
});

test("formulários e cliques sem os atributos de gestão não são afetados", () => {
    const env = environment();
    env.handlers.submit({ target: { closest: () => null }, preventDefault() { assert.fail("Envio não deveria ser bloqueado"); } });
    env.handlers.click({ target: { closest: () => null } });
    assert.deepEqual(env.prompts, []);
});
