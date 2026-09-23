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
      new Chart(graficoMes, {
        type: "bar",
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
      });
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
      new Chart(graficoStatus, {
      type: 'bar',
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
      });
    }

    const response2 = await fetch(`/admin/filter/severidade${params}`);
    const dados2 = await response2.json();
    const graficoDoughnut = document.getElementById("graficoDoughnut");

    if (graficoDoughnut) {
      new Chart(graficoDoughnut, {
        type: 'doughnut',
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
      });
    }

  } catch (error) {
    console.error("Erro ao carregar dashboard:", error);
  }

}

carregarDashboard();
