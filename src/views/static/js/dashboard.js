const graficosDashboard = [];
const temaDashboard = {
  id: "temaDashboard",
  beforeUpdate(grafico) {
    const estilos = getComputedStyle(document.documentElement);
    const texto = estilos.getPropertyValue("--text-secondary").trim();
    const borda = estilos.getPropertyValue("--border").trim();
    const fundo = estilos.getPropertyValue("--surface-muted").trim();

    grafico.options.color = texto;
    grafico.options.plugins.legend.labels.color = texto;
    Object.assign(grafico.options.plugins.tooltip, {
      backgroundColor: estilos.getPropertyValue("--surface").trim(),
      titleColor: estilos.getPropertyValue("--text-primary").trim(),
      bodyColor: estilos.getPropertyValue("--text-primary").trim(),
      borderColor: borda,
      borderWidth: 1
    });

    Object.values(grafico.options.scales || {}).forEach((escala) => {
      escala.ticks.color = texto;
      escala.grid.color = borda;
      escala.border.color = borda;
    });

    if (grafico.config.type === "doughnut") {
      grafico.data.datasets.forEach((dataset) => {
        dataset.borderColor = fundo;
      });
    }

    if (grafico.canvas.id === "graficoMes") {
      const cor = estilos.getPropertyValue("--primary").trim();
      grafico.data.datasets[0].backgroundColor = cor;
      grafico.data.datasets[0].borderColor = cor;
    }
  }
};

window.addEventListener("themechange", () => {
  graficosDashboard.forEach((grafico) => {
    grafico.stop();
    grafico.update("none");
  });
});

async function carregarDashboard() {
  try {
    const params = window.location.search || "";
    const response = await fetch(`/admin/meses-denuncias${params}`);
    const dados = await response.json()    

    const dadosMes = [
      dados.Jan, dados.Fev, dados.Mar, dados.Abr,
      dados.Mai, dados.Jun, dados.Jul, dados.Ago,
      dados.Set, dados.Out, dados.Nov, dados.Dez
    ];

    // GRÁFICO MENSAL
    const graficoMes = document.getElementById("graficoMes");
    if (graficoMes) {
      graficosDashboard.push(new Chart(graficoMes, {
        type: "bar",
        plugins: [temaDashboard],
        data: {
        labels: ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
        datasets: [{
        label: "Total de Denúncias",
        data: dadosMes,
        borderWidth: 1
              }]
        },
        options: {
        responsive: true,
        scales: { y: { beginAtZero: true } }
        }
      }));
    }

    const response1 = await fetch(`/admin/filter/quantidade_status${params}`);
    const dados1 = await response1.json()

    const dadosStatus = [
      dados1.pendente, dados1.em_analise,
      dados1.suspenso, dados1.encerrada
    ]

    // ============================
    // STATUS DAS DENÚNCIAS
    // ============================

    const graficoStatus = document.getElementById("graficoStatus");
    if (graficoStatus) {
      graficosDashboard.push(new Chart(graficoStatus, {
      type: 'bar',
      plugins: [temaDashboard],
      data: {
        labels: ['Pendente', 'Em análise', 'Suspenso', 'Encerradas'],
        datasets: [{
          label: 'Quantidade',
          data: dadosStatus,
          borderWidth: 1,
          backgroundColor: [
            'rgb(240, 180, 0)',
            'rgb(0, 80, 200)',
            'rgb(255, 130, 0)',
            'rgb(30, 160, 60)'
          ]
        }]
      },
      options: {
        indexAxis: 'y',
        scales: {
          x: { beginAtZero: true }
        }
      }
      }));
    }

    const response2 = await fetch(`/admin/filter/severidade${params}`);
    const dados2 = await response2.json();
    const graficoDoughnut = document.getElementById("graficoDoughnut");

    if (graficoDoughnut) {
      graficosDashboard.push(new Chart(graficoDoughnut, {
        type: 'doughnut',
        plugins: [temaDashboard],
        data: {
          labels: dados2.labels,
          datasets: [{
            data: dados2.values,
            backgroundColor: [
              'rgb(3, 188, 169)',
              'rgb(255, 193, 7)',
              'rgb(255, 152, 0)',
              'rgb(244, 67, 54)',
              'rgb(148, 163, 184)'
            ]
          }]
        }
      }));
    }

  } catch (error) {
    console.error("Erro ao carregar dashboard:", error);
  }

}

carregarDashboard();
