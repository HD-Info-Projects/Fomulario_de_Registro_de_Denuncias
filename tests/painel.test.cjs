const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../src/views/static/js/painel.js"), "utf8");

function painelEnvironment(status = "em_analise", confirmResult = true) {
    const values = {
        status,
        severidade: "critica",
        responsavel: "Equipe de análise",
        depoimento_vitima: "Relato da vítima",
        depoimento_acusado: "Relato do acusado",
        depoimento_testemunha: "Relato da testemunha",
        depoimento_admin: "Observações internas"
    };
    const requests = [];
    const form = {
        querySelector(selector) {
            const name = selector.match(/name='([^']+)'/)[1];
            assert.ok(Object.hasOwn(values, name), name);
            return { value: values[name] };
        }
    };
    const button = { getAttribute: () => "7", closest: () => form };
    const context = {
        document: { querySelector: () => ({ content: "test-csrf-token" }) },
        confirm: () => confirmResult,
        console: { log() {}, error: console.error },
        fetch(url, options) {
            requests.push({ url, options });
            return Promise.resolve({ json: async () => ({ sucesso: true }) });
        },
        setTimeout() {}
    };
    vm.createContext(context);
    vm.runInContext(source, context);
    context.mostrarToast = () => {};
    return { values, requests, save: () => context.salvarDenuncia(button) };
}

test("salvar envia severidade, depoimentos e token CSRF da denúncia correta", () => {
    const env = painelEnvironment();
    env.save();
    assert.equal(env.requests.length, 1);
    const { url, options } = env.requests[0];
    assert.equal(url, "/admin/denuncia/7/atualizar");
    assert.equal(options.method, "POST");
    assert.equal(options.headers["X-CSRFToken"], "test-csrf-token");
    assert.deepEqual(JSON.parse(options.body), env.values);
});

test("cancelar finalização não envia alterações", () => {
    const env = painelEnvironment("finalizado", false);
    env.save();
    assert.equal(env.requests.length, 0);
});

test("confirmar finalização mantém severidade e os demais campos", () => {
    const env = painelEnvironment("finalizado");
    env.save();
    assert.equal(env.requests.length, 1);
    assert.deepEqual(JSON.parse(env.requests[0].options.body), env.values);
});
