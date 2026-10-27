const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const staticDir = path.join(__dirname, "../src/views/static");
const themeSource = readFileSync(path.join(staticDir, "js/theme.js"), "utf8");
const dashboardSource = readFileSync(path.join(staticDir, "js/dashboard.js"), "utf8");
const storageKey = "denuncias-theme";

function eventHandlers() {
    const handlers = new Map();
    return {
        addEventListener(type, handler) {
            const callbacks = handlers.get(type) || [];
            callbacks.push(handler);
            handlers.set(type, callbacks);
        },
        dispatchEvent(event) {
            (handlers.get(event.type) || []).forEach((handler) => handler(event));
        }
    };
}

function themeEnvironment(saved = null, { blockedRead = false, blockedWrite = false } = {}) {
    const root = { dataset: {} };
    const storage = new Map(saved === null ? [] : [[storageKey, saved]]);
    const label = { textContent: "Tema escuro" };
    const attributes = {};
    const button = {
        hidden: true,
        querySelector: () => label,
        setAttribute: (name, value) => { attributes[name] = value; }
    };
    const document = {
        ...eventHandlers(),
        documentElement: root,
        querySelectorAll: () => [button]
    };
    const window = {
        ...eventHandlers(),
        // Mesmo em um sistema escuro, o primeiro acesso deve ser claro.
        matchMedia: () => ({ matches: true }),
        localStorage: {
            getItem(key) {
                if (blockedRead) throw new Error("Storage blocked");
                return storage.get(key) ?? null;
            },
            setItem(key, value) {
                if (blockedWrite) throw new Error("Storage blocked");
                storage.set(key, value);
            }
        }
    };
    const changes = [];
    window.addEventListener("themechange", (event) => changes.push(event.detail.theme));
    vm.runInNewContext(themeSource, {
        document,
        window,
        CustomEvent: class {
            constructor(type, { detail }) {
                this.type = type;
                this.detail = detail;
            }
        }
    });

    return {
        root, storage, label, attributes, button, changes,
        ready: () => document.dispatchEvent({ type: "DOMContentLoaded" }),
        click: (onButton = true) => document.dispatchEvent({
            type: "click",
            target: { closest: () => onButton ? button : null }
        }),
        storageEvent: (key, newValue) => window.dispatchEvent({ type: "storage", key, newValue })
    };
}

test("primeiro acesso é claro, sem salvar uma escolha automaticamente", () => {
    const env = themeEnvironment();
    assert.equal(env.root.dataset.theme, "light");
    assert.equal(env.button.hidden, true);
    assert.equal(env.storage.size, 0);
    env.ready();
    assert.equal(env.button.hidden, false);
    assert.equal(env.label.textContent, "Tema escuro");
    assert.equal(env.attributes["aria-label"], "Ativar tema escuro");
});

test("preferência escura é aplicada antes de inicializar o botão", () => {
    const env = themeEnvironment("dark");
    assert.equal(env.root.dataset.theme, "dark");
    env.ready();
    assert.equal(env.label.textContent, "Tema claro");
    assert.equal(env.attributes["aria-label"], "Ativar tema claro");
    assert.equal(env.button.title, "Ativar tema claro");
});

test("preferências desconhecidas usam o tema claro", () => {
    for (const value of ["", "system", "black", "LIGHT", "<script>"]) {
        assert.equal(themeEnvironment(value).root.dataset.theme, "light");
    }
});

test("cliques alternam, salvam e restauram a escolha ao recarregar", () => {
    const env = themeEnvironment();
    env.ready();
    env.click();
    assert.equal(env.root.dataset.theme, "dark");
    assert.equal(env.storage.get(storageKey), "dark");
    assert.equal(env.label.textContent, "Tema claro");
    assert.equal(themeEnvironment(env.storage.get(storageKey)).root.dataset.theme, "dark");
    env.click();
    assert.equal(env.root.dataset.theme, "light");
    assert.equal(env.storage.get(storageKey), "light");
    assert.equal(env.attributes["aria-label"], "Ativar tema escuro");
    assert.deepEqual(env.changes, ["dark", "light"]);
});

test("cliques fora do botão não alteram o tema", () => {
    const env = themeEnvironment();
    env.ready();
    env.click(false);
    assert.equal(env.root.dataset.theme, "light");
    assert.equal(env.storage.size, 0);
    assert.deepEqual(env.changes, []);
});

test("armazenamento bloqueado não impede a alternância", () => {
    const env = themeEnvironment(null, { blockedRead: true, blockedWrite: true });
    env.ready();
    env.click();
    assert.equal(env.root.dataset.theme, "dark");
    assert.equal(env.attributes["aria-label"], "Ativar tema claro");
    env.click();
    assert.equal(env.root.dataset.theme, "light");
});

test("mudanças em outra aba sincronizam o tema e o botão", () => {
    const env = themeEnvironment();
    env.ready();
    env.storageEvent("unrelated-key", "dark");
    assert.equal(env.root.dataset.theme, "light");
    env.storageEvent(storageKey, "dark");
    assert.equal(env.root.dataset.theme, "dark");
    assert.equal(env.label.textContent, "Tema claro");
    env.storageEvent(storageKey, null);
    assert.equal(env.root.dataset.theme, "light");
    env.storageEvent(storageKey, "dark");
    env.storageEvent(null, null);
    assert.equal(env.root.dataset.theme, "light");
});

test("todos os layouts carregam o tema antes do CSS e incluem o botão compartilhado", () => {
    for (const file of ["base.html", "baseUser.html", "login_adm.html"]) {
        const html = readFileSync(path.join(staticDir, "../templates", file), "utf8");
        assert.match(html, /<html[^>]+data-theme="light"/);
        const script = html.match(/<script[^>]+js\/theme\.js[^>]*><\/script>/);
        assert.ok(script, file);
        assert.doesNotMatch(script[0], /\b(async|defer)\b/);
        assert.ok(script.index < html.indexOf('rel="stylesheet"'), file);
        assert.match(html, /css\/theme\.css/);
        assert.match(html, /include "partials\/theme_toggle\.html"/);
    }
});

async function dashboardEnvironment() {
    const charts = [];
    const window = { ...eventHandlers(), location: { search: "?status=pendente" } };
    let mode = "light";
    const requests = [];
    const responses = [
        { Jan: 2 },
        { pendente: 2, em_analise: 1, suspenso: 0, encerrada: 3 },
        { labels: ["Baixa", "Alta"], values: [2, 4] }
    ];
    class Chart {
        constructor(canvas, config) {
            this.canvas = canvas;
            this.config = config;
            this.data = config.data;
            this.options = {
                ...config.options,
                plugins: { legend: { labels: {} }, tooltip: {} },
                scales: config.type === "doughnut" ? {} : {
                    x: { ticks: {}, grid: {}, border: {} },
                    y: { ticks: {}, grid: {}, border: {} }
                }
            };
            this.updates = [];
            this.stops = 0;
            config.plugins.forEach((plugin) => plugin.beforeUpdate(this));
            charts.push(this);
        }
        stop() {
            this.stops += 1;
        }
        update(animation) {
            this.config.plugins.forEach((plugin) => plugin.beforeUpdate(this));
            this.updates.push(animation);
        }
    }
    await vm.runInNewContext(dashboardSource, {
        window, Chart, console,
        document: { documentElement: {}, getElementById: (id) => ({ id }) },
        getComputedStyle: () => ({ getPropertyValue: (key) => `${mode}:${key}` }),
        fetch: async (url) => {
            requests.push(url);
            return { json: async () => responses.shift() };
        }
    });
    return {
        charts, requests,
        switchTheme(theme) {
            mode = theme;
            window.dispatchEvent({ type: "themechange" });
        }
    };
}

test("gráficos usam as cores do tema sem alterar dados ou filtros", async () => {
    const env = await dashboardEnvironment();
    assert.equal(env.charts.length, 3);
    assert.ok(env.requests.every((url) => url.endsWith("?status=pendente")));
    for (const chart of env.charts) {
        assert.equal(chart.options.plugins.legend.labels.color, "light:--text-secondary");
        assert.equal(chart.options.plugins.tooltip.bodyColor, "light:--text-primary");
        for (const scale of Object.values(chart.options.scales)) {
            assert.equal(scale.ticks.color, "light:--text-secondary");
            assert.equal(scale.grid.color, "light:--border");
        }
    }
    assert.equal(env.charts[0].data.datasets[0].data[0], 2);
    assert.deepEqual(Array.from(env.charts[1].data.datasets[0].data), [2, 1, 0, 3]);
    assert.equal(env.charts[2].data.datasets[0].borderColor, "light:--surface-muted");
});

test("trocar o tema atualiza os gráficos existentes sem recarregar dados", async () => {
    const env = await dashboardEnvironment();
    env.switchTheme("dark");
    for (const chart of env.charts) {
        assert.equal(chart.options.plugins.legend.labels.color, "dark:--text-secondary");
        assert.equal(chart.stops, 1);
        assert.deepEqual(chart.updates, ["none"]);
    }
    assert.equal(env.charts[0].data.datasets[0].backgroundColor, "dark:--primary");
    assert.equal(env.charts[2].data.datasets[0].borderColor, "dark:--surface-muted");
    env.switchTheme("light");
    assert.equal(env.charts[0].options.color, "light:--text-secondary");
    assert.equal(env.requests.length, 3);
});
